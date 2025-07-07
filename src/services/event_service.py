from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re
from openai import AsyncOpenAI

from ..core.gitlab_client import GitLabClientManager
from ..core.date_parser import DateParser
from ..models.event import (
    GitLabEvent, GitLabCommit, EventType, WorkType, WorkClassification,
    WorkSummary, EventFilters, EventSearchResult
)
from ..config.settings import GitLabConfig

class EventService:
    """Service for GitLab event operations and processing."""
    
    def __init__(self, config: GitLabConfig, openai_client: AsyncOpenAI, user_token: Optional[str] = None):
        self.gitlab_manager = GitLabClientManager(config)
        self.config = config
        self.openai_client = openai_client
        self.user_token = user_token  # OAuth token from authenticated user
        self._user_client = None  # Separate client for user operations
    
    def _get_user_client(self):
        """Get GitLab client authenticated with user's OAuth token."""
        if self._user_client is None and self.user_token:
            try:
                import gitlab
                self._user_client = gitlab.Gitlab(self.config.url, oauth_token=self.user_token)
                self._user_client.auth()
            except Exception as e:
                print(f"Error creating user client: {e}")
                # Fallback to main client
                self._user_client = self.gitlab_manager.client
        return self._user_client or self.gitlab_manager.client
    
    async def get_user_events(self, filters: EventFilters, user_id: Optional[str] = None) -> EventSearchResult:
        """Get GitLab events for the current user with filtering."""
        try:
            # Use user-authenticated client
            gl = self._get_user_client()
            
            # Get current user or specified user
            if user_id:
                try:
                    current_user = gl.users.get(user_id)
                except Exception:
                    # Fallback to authenticated user
                    current_user = gl.user
            else:
                current_user = gl.user
            
            # Parse date range
            start_date, end_date = DateParser.parse_month(filters.month)
            
            # Get user events from GitLab API
            events_params = {
                'per_page': filters.limit,
                'page': 1
            }
            
            if start_date:
                events_params['after'] = start_date.strftime('%Y-%m-%d')
            if end_date:
                events_params['before'] = end_date.strftime('%Y-%m-%d')
            
            # Get events from GitLab
            user_events = current_user.events.list(**events_params)
            
            # Process events
            processed_events = []
            for i, event in enumerate(user_events):
                # Debug first few events to understand structure
                if i < 2:  # Only debug first 2 events to avoid spam
                    self._debug_gitlab_event_structure(event, i + 1)
                
                processed_event = self._process_gitlab_event(event)
                if processed_event and self._should_include_event(processed_event, filters):
                    processed_events.append(processed_event)
            
            # Get commits for push events
            self._enrich_events_with_commits(processed_events)
            
            # Classify events into work groups
            classifications = self._classify_events(processed_events)
            
            # Generate summaries using LLM (async)
            summaries = []
            for classification in classifications:
                if classification.commits:  # Only summarize if there are commits
                    try:
                        summary = await self._generate_work_summary(classification)
                        if summary:
                            summaries.append(summary)
                    except Exception as e:
                        print(f"Error generating summary for classification: {e}")
                        # Create fallback summary
                        fallback_summary = self._create_fallback_summary(classification)
                        summaries.append(fallback_summary)
            
            return EventSearchResult(
                success=True,
                total_events=len(processed_events),
                events=processed_events,
                classifications=classifications,
                summaries=summaries,
                month_filter=filters.month
            )
            
        except Exception as e:
            return EventSearchResult(
                success=False,
                total_events=0,
                events=[],
                classifications=[],
                summaries=[],
                error=str(e)
            )
    
    def _debug_gitlab_event_structure(self, gitlab_event, event_number: int = 0):
        """Debug helper to understand GitLab event structure."""
        print(f"\n🔍 DEBUG: GitLab Event #{event_number}")
        print(f"Type: {type(gitlab_event)}")
        print(f"Available attributes: {[attr for attr in dir(gitlab_event) if not attr.startswith('_')]}")
        
        # Print key attributes if they exist
        key_attrs = ['id', 'action_name', 'created_at', 'project_id', 'target_type', 'target_id', 'author']
        for attr in key_attrs:
            if hasattr(gitlab_event, attr):
                value = getattr(gitlab_event, attr)
                print(f"{attr}: {value} (type: {type(value)})")
        
        # Check for project-related attributes
        project_attrs = ['project', 'project_name', 'project_id']
        for attr in project_attrs:
            if hasattr(gitlab_event, attr):
                value = getattr(gitlab_event, attr)
                print(f"{attr}: {value} (type: {type(value)})")
                if isinstance(value, dict):
                    print(f"  {attr} keys: {list(value.keys())}")
        
    def _create_fallback_summary(self, classification: WorkClassification) -> WorkSummary:
        """Create a fallback summary when LLM generation fails."""
        return WorkSummary(
            name=f"{classification.work_type.value.title()} Work",
            description=f"Work on {classification.branch_name or 'project'} with {len(classification.commits)} commits",
            estimated_hours=len(classification.commits) * 0.5,  # Simple estimate
            confidence=0.3,  # Low confidence for fallback
            work_type=classification.work_type,
            key_achievements=[f"Completed {len(classification.commits)} commits"],
            technical_details=[f"Branch: {classification.branch_name or 'Unknown'}"]
        )
    
    def _process_gitlab_event(self, gitlab_event) -> Optional[GitLabEvent]:
        """Convert GitLab API event to our model."""
        try:
            # Map GitLab action to our EventType
            action = gitlab_event.action_name.lower()
            event_type = self._map_action_to_event_type(action)
            
            created_at = datetime.fromisoformat(
                gitlab_event.created_at.replace('Z', '+00:00')
            )
            
            # Extract branch name from push data or target
            branch_name = None
            merge_request_id = None
            
            # Handle push data
            if hasattr(gitlab_event, 'push_data') and gitlab_event.push_data:
                branch_name = gitlab_event.push_data.get('ref')
                
            # Handle target data
            if hasattr(gitlab_event, 'target') and gitlab_event.target:
                if gitlab_event.target.get('target_type') == 'MergeRequest':
                    merge_request_id = gitlab_event.target.get('iid')
                    branch_name = gitlab_event.target.get('source_branch')
            
            # Handle project information - UserEvent might have different structure
            project_id = str(gitlab_event.project_id) if hasattr(gitlab_event, 'project_id') else 'unknown'
            project_name = 'Unknown Project'
            
            # Try different ways to get project name
            if hasattr(gitlab_event, 'project') and gitlab_event.project:
                if isinstance(gitlab_event.project, dict):
                    project_name = gitlab_event.project.get('name', f'Project {project_id}')
                else:
                    # If it's an object, try to get name attribute
                    project_name = getattr(gitlab_event.project, 'name', f'Project {project_id}')
            elif hasattr(gitlab_event, 'project_name'):
                project_name = gitlab_event.project_name
            else:
                project_name = f'Project {project_id}'
            
            # Handle author information
            author_name = 'Unknown'
            if hasattr(gitlab_event, 'author') and gitlab_event.author:
                if isinstance(gitlab_event.author, dict):
                    author_name = gitlab_event.author.get('name', 'Unknown')
                else:
                    author_name = getattr(gitlab_event.author, 'name', 'Unknown')
            elif hasattr(gitlab_event, 'author_name'):
                author_name = gitlab_event.author_name
            
            return GitLabEvent(
                id=gitlab_event.id,
                event_type=event_type,
                created_at=created_at,
                author_name=author_name,
                project_id=project_id,
                project_name=project_name,
                target_type=getattr(gitlab_event, 'target_type', None),
                target_id=getattr(gitlab_event, 'target_id', None),
                target_title=getattr(gitlab_event, 'target_title', None),
                push_data=getattr(gitlab_event, 'push_data', None),
                merge_request_id=merge_request_id,
                branch_name=branch_name
            )
            
        except Exception as e:
            print(f"Error processing GitLab event: {e}")
            print(f"Event type: {type(gitlab_event)}")
            print(f"Available attributes: {dir(gitlab_event)}")
            return None
    
    def _map_action_to_event_type(self, action: str) -> EventType:
        """Map GitLab action to our EventType enum."""
        action_mapping = {
            'pushed': EventType.PUSH,
            'pushed to': EventType.PUSH,
            'pushed new': EventType.PUSH,
            'merged': EventType.MERGE,
            'accepted': EventType.MERGE,
            'opened': EventType.ISSUE_CREATE,
            'created': EventType.BRANCH_CREATE,
            'closed': EventType.ISSUE_CLOSE,
            'commented': EventType.COMMENT,
            'committed': EventType.COMMIT
        }
        
        for key, event_type in action_mapping.items():
            if key in action:
                return event_type
        
        return EventType.OTHER
    
    def _should_include_event(self, event: GitLabEvent, filters: EventFilters) -> bool:
        """Check if event should be included based on filters."""
        # Filter by event types
        if filters.event_types and event.event_type not in filters.event_types:
            return False
        
        # Filter by project IDs
        if filters.project_ids and event.project_id not in filters.project_ids:
            return False
        
        # Only include events with meaningful work (push, merge, commits)
        meaningful_types = [EventType.PUSH, EventType.MERGE, EventType.COMMIT]
        return event.event_type in meaningful_types
    
    def _enrich_events_with_commits(self, events: List[GitLabEvent]):
        """Add commit data to push events."""
        gl = self._get_user_client()
        
        for event in events:
            if event.event_type == EventType.PUSH and event.push_data:
                try:
                    project = gl.projects.get(event.project_id)
                    
                    # Get commits from push data
                    if 'commits' in event.push_data:
                        for commit_data in event.push_data['commits']:
                            commit = self._create_commit_from_data(
                                commit_data, event.project_id, event.project_name
                            )
                            if commit:
                                event.commits.append(commit)
                    else:
                        # Fallback: get recent commits from branch
                        try:
                            commits = project.commits.list(
                                ref_name=event.branch_name,
                                since=(event.created_at - timedelta(hours=1)).isoformat(),
                                until=(event.created_at + timedelta(hours=1)).isoformat(),
                                per_page=20
                            )
                            
                            for commit in commits:
                                gitlab_commit = self._create_commit_from_gitlab(
                                    commit, event.project_id, event.project_name
                                )
                                if gitlab_commit:
                                    event.commits.append(gitlab_commit)
                                    
                        except Exception:
                            pass  # Skip if we can't get commits
                            
                except Exception as e:
                    print(f"Error enriching event {event.id} with commits: {e}")
    
    def _create_commit_from_data(self, commit_data: Dict, project_id: str, project_name: str) -> Optional[GitLabCommit]:
        """Create GitLabCommit from push data."""
        try:
            return GitLabCommit(
                id=commit_data['id'],
                title=commit_data['title'],
                message=commit_data.get('message', commit_data['title']),
                author_name=commit_data.get('author', {}).get('name', 'Unknown'),
                author_email=commit_data.get('author', {}).get('email', ''),
                created_at=datetime.fromisoformat(commit_data['timestamp'].replace('Z', '+00:00')),
                web_url=commit_data.get('url', ''),
                project_id=project_id,
                project_name=project_name
            )
        except Exception:
            return None
    
    def _create_commit_from_gitlab(self, gitlab_commit, project_id: str, project_name: str) -> Optional[GitLabCommit]:
        """Create GitLabCommit from GitLab API commit."""
        try:
            return GitLabCommit(
                id=gitlab_commit.id,
                title=gitlab_commit.title,
                message=gitlab_commit.message,
                author_name=gitlab_commit.author_name,
                author_email=gitlab_commit.author_email,
                created_at=datetime.fromisoformat(gitlab_commit.created_at.replace('Z', '+00:00')),
                web_url=gitlab_commit.web_url,
                project_id=project_id,
                project_name=project_name
            )
        except Exception:
            return None
    
    def _classify_events(self, events: List[GitLabEvent]) -> List[WorkClassification]:
        """Classify events into work groups based on merge requests and branches."""
        classifications = []
        
        # Group by merge request first
        mr_groups = {}
        branch_groups = {}
        standalone_events = []
        
        for event in events:
            if event.merge_request_id:
                if event.merge_request_id not in mr_groups:
                    mr_groups[event.merge_request_id] = []
                mr_groups[event.merge_request_id].append(event)
            elif event.branch_name and event.branch_name not in ['main', 'master']:
                if event.branch_name not in branch_groups:
                    branch_groups[event.branch_name] = []
                branch_groups[event.branch_name].append(event)
            else:
                standalone_events.append(event)
        
        # Create classifications for merge request groups
        for mr_id, mr_events in mr_groups.items():
            classification = self._create_mr_classification(mr_id, mr_events)
            if classification:
                classifications.append(classification)
        
        # Create classifications for branch groups
        for branch_name, branch_events in branch_groups.items():
            classification = self._create_branch_classification(branch_name, branch_events)
            if classification:
                classifications.append(classification)
        
        # Handle standalone events
        for event in standalone_events:
            if event.commits:  # Only classify if there are commits
                classification = self._create_standalone_classification(event)
                if classification:
                    classifications.append(classification)
        
        return classifications
    
    def _create_mr_classification(self, mr_id: int, events: List[GitLabEvent]) -> Optional[WorkClassification]:
        """Create classification for merge request group."""
        all_commits = []
        branch_name = None
        mr_title = None
        
        for event in events:
            all_commits.extend(event.commits)
            if event.branch_name:
                branch_name = event.branch_name
            if event.target_title:
                mr_title = event.target_title
        
        if not all_commits:
            return None
        
        work_type = self._detect_work_type(branch_name, mr_title, all_commits)
        
        return WorkClassification(
            work_type=work_type,
            confidence=0.9,  # High confidence for MR-based classification
            branch_name=branch_name,
            merge_request_id=mr_id,
            merge_request_title=mr_title,
            commits=all_commits,
            events=events
        )
    
    def _create_branch_classification(self, branch_name: str, events: List[GitLabEvent]) -> Optional[WorkClassification]:
        """Create classification for branch group."""
        all_commits = []
        
        for event in events:
            all_commits.extend(event.commits)
        
        if not all_commits:
            return None
        
        work_type = self._detect_work_type(branch_name, None, all_commits)
        
        return WorkClassification(
            work_type=work_type,
            confidence=0.7,  # Medium confidence for branch-based classification
            branch_name=branch_name,
            commits=all_commits,
            events=events
        )
    
    def _create_standalone_classification(self, event: GitLabEvent) -> Optional[WorkClassification]:
        """Create classification for standalone event."""
        if not event.commits:
            return None
        
        work_type = self._detect_work_type(event.branch_name, None, event.commits)
        
        return WorkClassification(
            work_type=work_type,
            confidence=0.5,  # Lower confidence for standalone classification
            branch_name=event.branch_name,
            commits=event.commits,
            events=[event]
        )
    
    def _detect_work_type(self, branch_name: Optional[str], mr_title: Optional[str], commits: List[GitLabCommit]) -> WorkType:
        """Detect work type based on naming patterns and commit content."""
        # Check branch name patterns
        if branch_name:
            branch_lower = branch_name.lower()
            if any(pattern in branch_lower for pattern in ['feature', 'feat']):
                return WorkType.FEATURE
            elif any(pattern in branch_lower for pattern in ['fix', 'bug', 'hotfix']):
                return WorkType.BUGFIX
            elif any(pattern in branch_lower for pattern in ['hotfix', 'urgent']):
                return WorkType.HOTFIX
            elif any(pattern in branch_lower for pattern in ['refactor', 'cleanup']):
                return WorkType.REFACTOR
            elif any(pattern in branch_lower for pattern in ['doc', 'readme']):
                return WorkType.DOCUMENTATION
            elif any(pattern in branch_lower for pattern in ['experiment', 'test', 'poc']):
                return WorkType.EXPERIMENT
        
        # Check MR title patterns
        if mr_title:
            mr_lower = mr_title.lower()
            if any(pattern in mr_lower for pattern in ['feature', 'add', 'implement']):
                return WorkType.FEATURE
            elif any(pattern in mr_lower for pattern in ['fix', 'bug', 'resolve']):
                return WorkType.BUGFIX
            elif any(pattern in mr_lower for pattern in ['hotfix', 'urgent']):
                return WorkType.HOTFIX
            elif any(pattern in mr_lower for pattern in ['refactor', 'cleanup', 'improve']):
                return WorkType.REFACTOR
            elif any(pattern in mr_lower for pattern in ['doc', 'documentation']):
                return WorkType.DOCUMENTATION
        
        # Check commit patterns
        feature_count = 0
        bugfix_count = 0
        doc_count = 0
        
        for commit in commits:
            title_lower = commit.title.lower()
            if any(pattern in title_lower for pattern in ['feat', 'add', 'implement', 'create']):
                feature_count += 1
            elif any(pattern in title_lower for pattern in ['fix', 'bug', 'resolve']):
                bugfix_count += 1
            elif any(pattern in title_lower for pattern in ['doc', 'readme', 'comment']):
                doc_count += 1
        
        # Determine type based on commit patterns
        total_commits = len(commits)
        if bugfix_count > total_commits * 0.6:
            return WorkType.BUGFIX
        elif feature_count > total_commits * 0.6:
            return WorkType.FEATURE
        elif doc_count > total_commits * 0.6:
            return WorkType.DOCUMENTATION
        elif feature_count > bugfix_count:
            return WorkType.FEATURE
        elif bugfix_count > feature_count:
            return WorkType.BUGFIX
        
        return WorkType.UNKNOWN
    
    async def _generate_work_summary(self, classification: WorkClassification) -> Optional[WorkSummary]:
        """Generate work summary using LLM."""
        try:
            # Prepare commit data for LLM
            commit_info = []
            for commit in classification.commits:
                commit_info.append({
                    "title": commit.clean_title,
                    "message": commit.message[:200],  # Truncate long messages
                    "date": commit.created_at.strftime("%Y-%m-%d")
                })
            
            # Create prompt for LLM
            prompt = self._create_summary_prompt(classification, commit_info)
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Use cheaper model for summaries
                messages=[
                    {"role": "system", "content": "You are a technical project manager who creates concise work summaries from commit data."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            # Parse LLM response
            return self._parse_summary_response(response.choices[0].message.content, classification)
            
        except Exception as e:
            print(f"Error generating work summary: {e}")
            return None
    
    def _create_summary_prompt(self, classification: WorkClassification, commit_info: List[Dict]) -> str:
        """Create prompt for LLM summary generation."""
        commits_text = "\n".join([
            f"- {commit['title']} ({commit['date']})"
            for commit in commit_info
        ])
        
        context = ""
        if classification.branch_name:
            context += f"Branch: {classification.branch_name}\n"
        if classification.merge_request_title:
            context += f"Merge Request: {classification.merge_request_title}\n"
        
        return f"""
Analyze these Git commits and provide a work summary:

{context}
Work Type: {classification.work_type.value}

Commits:
{commits_text}

Please provide:
1. A concise name for this work (max 50 characters)
2. A brief description of what was accomplished (max 150 characters)
3. Estimated hours this work took (be realistic: 0.5-40 hours)
4. Key achievements (2-3 bullet points)
5. Technical details (1-2 bullet points)

Format your response as:
NAME: [work name]
DESCRIPTION: [description]
HOURS: [number]
ACHIEVEMENTS:
- [achievement 1]
- [achievement 2]
TECHNICAL:
- [technical detail 1]
- [technical detail 2]
"""
    
    def _parse_summary_response(self, response: str, classification: WorkClassification) -> Optional[WorkSummary]:
        """Parse LLM response into WorkSummary object."""
        try:
            lines = response.strip().split('\n')
            
            name = ""
            description = ""
            hours = 1.0
            achievements = []
            technical = []
            
            current_section = None
            
            for line in lines:
                line = line.strip()
                if line.startswith("NAME:"):
                    name = line[5:].strip()
                elif line.startswith("DESCRIPTION:"):
                    description = line[12:].strip()
                elif line.startswith("HOURS:"):
                    try:
                        hours_str = line[6:].strip()
                        hours = float(re.findall(r'\d+\.?\d*', hours_str)[0])
                    except:
                        hours = 1.0
                elif line.startswith("ACHIEVEMENTS:"):
                    current_section = "achievements"
                elif line.startswith("TECHNICAL:"):
                    current_section = "technical"
                elif line.startswith("- ") and current_section:
                    if current_section == "achievements":
                        achievements.append(line[2:])
                    elif current_section == "technical":
                        technical.append(line[2:])
            
            # Fallback values
            if not name:
                name = f"{classification.work_type.value.title()} Work"
            if not description:
                description = f"Work on {classification.branch_name or 'project'}"
            
            return WorkSummary(
                name=name[:50],  # Ensure max length
                description=description[:150],  # Ensure max length
                estimated_hours=max(0.5, min(40.0, hours)),  # Clamp hours
                confidence=0.8,
                work_type=classification.work_type,
                key_achievements=achievements[:3],  # Max 3 achievements
                technical_details=technical[:2]  # Max 2 technical details
            )
            
        except Exception as e:
            print(f"Error parsing summary response: {e}")
            # Return basic summary as fallback
            return WorkSummary(
                name=f"{classification.work_type.value.title()} Work",
                description=f"Work on {classification.branch_name or 'project'}",
                estimated_hours=2.0,
                confidence=0.5,
                work_type=classification.work_type
            )