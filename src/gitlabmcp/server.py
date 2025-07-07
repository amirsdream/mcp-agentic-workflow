
from typing import Optional, Dict, Any, List
from fastmcp import FastMCP
from openai import AsyncOpenAI

from ..config.settings import AppConfig
from ..services.event_service import EventService
from ..models.event import EventFilters, EventType, WorkType

class GitLabMCPServer:
    """FastMCP server for GitLab events processing with LLM integration."""
    
    def __init__(self, config: AppConfig, user_token: Optional[str] = None):
        self.config = config
        self.user_token = user_token
        self.openai_client = AsyncOpenAI(api_key=config.openai.api_key)
        self.event_service = EventService(config.gitlab, self.openai_client, user_token)
        self.mcp = FastMCP("GitLab Events Server")
        self._register_tools()
    
    def update_user_token(self, user_token: str):
        """Update the user token for authentication."""
        self.user_token = user_token
        self.event_service = EventService(self.config.gitlab, self.openai_client, user_token)
    
    def _register_tools(self):
        """Register MCP tools for event processing."""
        
        @self.mcp.tool()
        async def get_user_events(
            month: Optional[str] = None,
            year: Optional[str] = None,
            event_types: Optional[List[str]] = None,
            project_ids: Optional[List[str]] = None,
            limit: int = 200,
            user_id: Optional[str] = None,
            user_token: Optional[str] = None
        ) -> Dict[str, Any]:
            """Get GitLab events for current user with filtering, classification, and LLM summarization."""
            
            # Update the event service with the user token if provided
            if user_token and user_token != self.user_token:
                self.update_user_token(user_token)
            print(month, year, event_types, project_ids, limit, user_id, user_token)
            # Convert string event types to EventType enums
            parsed_event_types = None
            if event_types:
                parsed_event_types = []
                for et in event_types:
                    try:
                        parsed_event_types.append(EventType(et))
                    except ValueError:
                        continue  # Skip invalid event types
            
            filters = EventFilters(
                month=month,
                year=year,
                event_types=parsed_event_types,
                project_ids=project_ids,
                limit=limit
            )
            
            search_result = await self.event_service.get_user_events(filters, user_id)
            print(f"Search result: {search_result}")
            if not search_result.success:
                return {
                    "success": False,
                    "error": search_result.error,
                    "total_events": 0,
                    "total_commits": 0,
                    "total_work_hours": 0.0,
                    "events": [],
                    "classifications": [],
                    "summaries": []
                }
            
            # Create summary text
            summary_text = self._create_events_summary(search_result)
            
            # Create table data for display
            table_data = self._create_events_table(search_result)
            
            return {
                "success": True,
                "total_events": search_result.total_events,
                "total_commits": search_result.total_commits,
                "total_work_hours": search_result.total_work_hours,
                "month_filter": search_result.month_filter,
                "summary": summary_text,
                "table_data": table_data,
                "events": [event.to_dict() for event in search_result.events[:20]],  # Limit for performance
                "classifications": [classification.to_dict() for classification in search_result.classifications],
                "summaries": [summary.to_dict() for summary in search_result.summaries]
            }
        
        @self.mcp.tool()
        async def classify_work_events(
            month: Optional[str] = None,
            project_ids: Optional[List[str]] = None,
            user_id: Optional[str] = None,
            user_token: Optional[str] = None
        ) -> Dict[str, Any]:
            """Classify user's GitLab events into work categories with detailed analysis."""
            
            # Update the event service with the user token if provided
            if user_token and user_token != self.user_token:
                self.update_user_token(user_token)
            
            filters = EventFilters(
                month=month,
                project_ids=project_ids,
                event_types=[EventType.PUSH, EventType.MERGE, EventType.COMMIT],
                limit=100
            )
            
            search_result = await self.event_service.get_user_events(filters, user_id)
            
            if not search_result.success:
                return {"success": False, "error": search_result.error}
            
            # Group classifications by work type
            work_breakdown = {}
            for classification in search_result.classifications:
                work_type = classification.work_type.value
                if work_type not in work_breakdown:
                    work_breakdown[work_type] = {
                        "count": 0,
                        "total_commits": 0,
                        "branches": [],
                        "merge_requests": []
                    }
                
                work_breakdown[work_type]["count"] += 1
                work_breakdown[work_type]["total_commits"] += len(classification.commits)
                
                if classification.branch_name:
                    work_breakdown[work_type]["branches"].append(classification.branch_name)
                if classification.merge_request_id:
                    work_breakdown[work_type]["merge_requests"].append(classification.merge_request_id)
            
            return {
                "success": True,
                "total_classifications": len(search_result.classifications),
                "work_breakdown": work_breakdown,
                "classifications": [classification.to_dict() for classification in search_result.classifications],
                "month_filter": search_result.month_filter
            }
        
        @self.mcp.tool()
        async def get_work_summaries(
            month: Optional[str] = None,
            work_type: Optional[str] = None,
            min_hours: Optional[float] = None,
            user_id: Optional[str] = None,
            user_token: Optional[str] = None
        ) -> Dict[str, Any]:
            """Get LLM-generated work summaries with time estimations."""
            
            # Update the event service with the user token if provided
            if user_token and user_token != self.user_token:
                self.update_user_token(user_token)
            
            filters = EventFilters(
                month=month,
                event_types=[EventType.PUSH, EventType.MERGE, EventType.COMMIT],
                limit=150
            )
            
            search_result = await self.event_service.get_user_events(filters, user_id)
            
            if not search_result.success:
                return {"success": False, "error": search_result.error}
            
            # Filter summaries based on criteria
            filtered_summaries = search_result.summaries
            
            if work_type:
                try:
                    work_type_enum = WorkType(work_type)
                    filtered_summaries = [s for s in filtered_summaries if s.work_type == work_type_enum]
                except ValueError:
                    pass  # Invalid work type, keep all summaries
            
            if min_hours is not None:
                filtered_summaries = [s for s in filtered_summaries if s.estimated_hours >= min_hours]
            
            # Create summary statistics
            total_hours = sum(s.estimated_hours for s in filtered_summaries)
            work_type_breakdown = {}
            
            for summary in filtered_summaries:
                wt = summary.work_type.value
                if wt not in work_type_breakdown:
                    work_type_breakdown[wt] = {"count": 0, "hours": 0.0}
                work_type_breakdown[wt]["count"] += 1
                work_type_breakdown[wt]["hours"] += summary.estimated_hours
            
            # Create table data
            table_data = []
            for summary in filtered_summaries:
                table_data.append({
                    "Name": summary.name,
                    "Type": summary.work_type.value.title(),
                    "Hours": f"{summary.estimated_hours:.1f}h",
                    "Confidence": f"{summary.confidence:.0%}",
                    "Description": summary.description
                })
            
            summary_text = f"""
## Work Summary Report

**Time Period:** {search_result.month_filter or 'All time'}
**Total Work Items:** {len(filtered_summaries)}
**Total Estimated Hours:** {total_hours:.1f}h
**Average Hours per Item:** {total_hours/len(filtered_summaries):.1f}h

**Work Type Breakdown:**
{chr(10).join(f"- {wt.title()}: {data['count']} items ({data['hours']:.1f}h)" for wt, data in work_type_breakdown.items())}

**Key Achievements:**
{chr(10).join(f"- {summary.name}: {', '.join(summary.key_achievements[:2])}" for summary in filtered_summaries[:5] if summary.key_achievements)}
"""
            
            return {
                "success": True,
                "total_summaries": len(filtered_summaries),
                "total_hours": total_hours,
                "work_type_breakdown": work_type_breakdown,
                "summary": summary_text,
                "table_data": table_data,
                "summaries": [summary.to_dict() for summary in filtered_summaries],
                "month_filter": search_result.month_filter
            }
        
        @self.mcp.tool()
        async def analyze_productivity(
            month: Optional[str] = None,
            compare_previous: bool = False,
            user_id: Optional[str] = None,
            user_token: Optional[str] = None
        ) -> Dict[str, Any]:
            """Analyze productivity metrics from GitLab events and work summaries."""
            
            # Update the event service with the user token if provided
            if user_token and user_token != self.user_token:
                self.update_user_token(user_token)
            
            filters = EventFilters(
                month=month,
                event_types=[EventType.PUSH, EventType.MERGE, EventType.COMMIT],
                limit=200
            )
            
            search_result = await self.event_service.get_user_events(filters, user_id)
            
            if not search_result.success:
                return {"success": False, "error": search_result.error}
            
            # Calculate productivity metrics
            metrics = {
                "total_events": search_result.total_events,
                "total_commits": search_result.total_commits,
                "total_work_hours": search_result.total_work_hours,
                "unique_projects": len(set(event.project_id for event in search_result.events)),
                "unique_branches": len(set(event.branch_name for event in search_result.events if event.branch_name)),
                "merge_requests": len([c for c in search_result.classifications if c.merge_request_id]),
                "work_types": len(set(s.work_type for s in search_result.summaries)),
                "avg_commits_per_work": search_result.total_commits / max(1, len(search_result.classifications)),
                "avg_hours_per_work": search_result.total_work_hours / max(1, len(search_result.summaries))
            }
            
            # Create productivity insights
            insights = []
            
            if metrics["total_commits"] > 50:
                insights.append("🚀 High commit activity - very productive period")
            elif metrics["total_commits"] < 10:
                insights.append("📈 Low commit activity - consider increasing development frequency")
            
            if metrics["avg_hours_per_work"] > 8:
                insights.append("🎯 Working on complex tasks requiring significant time investment")
            elif metrics["avg_hours_per_work"] < 2:
                insights.append("⚡ Focusing on quick wins and small improvements")
            
            if metrics["merge_requests"] > 5:
                insights.append("🔄 Good merge request discipline - following proper review process")
            
            if metrics["unique_projects"] > 3:
                insights.append("🌐 Multi-project contributor - broad impact across codebase")
            
            # Work type analysis
            work_type_analysis = {}
            for summary in search_result.summaries:
                wt = summary.work_type.value
                if wt not in work_type_analysis:
                    work_type_analysis[wt] = {"count": 0, "hours": 0.0, "avg_confidence": 0.0}
                work_type_analysis[wt]["count"] += 1
                work_type_analysis[wt]["hours"] += summary.estimated_hours
                work_type_analysis[wt]["avg_confidence"] += summary.confidence
            
            for wt_data in work_type_analysis.values():
                if wt_data["count"] > 0:
                    wt_data["avg_confidence"] = wt_data["avg_confidence"] / wt_data["count"]
            
            productivity_summary = f"""
## Productivity Analysis

**Period:** {search_result.month_filter or 'All time'}

**Key Metrics:**
- Total Events: {metrics['total_events']}
- Total Commits: {metrics['total_commits']}
- Estimated Work Hours: {metrics['total_work_hours']:.1f}h
- Projects Involved: {metrics['unique_projects']}
- Branches Worked On: {metrics['unique_branches']}
- Merge Requests: {metrics['merge_requests']}

**Efficiency Metrics:**
- Commits per Work Item: {metrics['avg_commits_per_work']:.1f}
- Hours per Work Item: {metrics['avg_hours_per_work']:.1f}h

**Work Focus:**
{chr(10).join(f"- {wt.title()}: {data['count']} items ({data['hours']:.1f}h)" for wt, data in work_type_analysis.items())}

**Insights:**
{chr(10).join(f"- {insight}" for insight in insights)}
"""
            
            return {
                "success": True,
                "metrics": metrics,
                "work_type_analysis": work_type_analysis,
                "insights": insights,
                "summary": productivity_summary,
                "month_filter": search_result.month_filter
            }
        
        @self.mcp.tool()
        async def health_check(user_token: Optional[str] = None) -> Dict[str, Any]:
            """Check the health of GitLab connection and event processing capabilities."""
            try:
                # Update the event service with the user token if provided
                if user_token and user_token != self.user_token:
                    self.update_user_token(user_token)
                
                gitlab_healthy = self.event_service.gitlab_manager.test_connection()
                
                # Test current user access
                current_user = None
                user_events_accessible = False
                
                try:
                    # Use user-authenticated client if available
                    effective_token = user_token or self.user_token
                    if effective_token:
                        import gitlab
                        user_gl = gitlab.Gitlab(self.config.gitlab.url, oauth_token=effective_token)
                        user_gl.auth()
                        current_user = user_gl.user
                    else:
                        gl = self.event_service.gitlab_manager.client
                        current_user = gl.user
                    
                    # Try to get a few recent events
                    events = current_user.events.list(per_page=5)
                    user_events_accessible = True
                except Exception as e:
                    print(f"Error accessing user events: {e}")
                    user_events_accessible = False
                
                # Test OpenAI connection
                openai_healthy = False
                try:
                    # Quick test of OpenAI API
                    response = await self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": "test"}],
                        max_tokens=5
                    )
                    openai_healthy = True
                except Exception:
                    openai_healthy = False
                
                return {
                    "success": True,
                    "gitlab_connection": gitlab_healthy,
                    "user_events_access": user_events_accessible,
                    "openai_connection": openai_healthy,
                    "current_user": current_user.name if current_user else None,
                    "capabilities": {
                        "event_processing": True,
                        "work_classification": True,
                        "llm_summarization": openai_healthy,
                        "time_estimation": openai_healthy
                    }
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "gitlab_connection": False,
                    "user_events_access": False,
                    "openai_connection": False
                }
    
    def _create_events_summary(self, result) -> str:
        """Create summary text for events."""
        work_breakdown = {}
        for classification in result.classifications:
            work_type = classification.work_type.value
            work_breakdown[work_type] = work_breakdown.get(work_type, 0) + 1
        
        project_breakdown = {}
        for event in result.events:
            project_breakdown[event.project_name] = project_breakdown.get(event.project_name, 0) + 1
        
        return f"""
## GitLab Activity Summary

**Time Period:** {result.month_filter or 'All time'}
**Total Events:** {result.total_events}
**Total Commits:** {result.total_commits}
**Estimated Work Hours:** {result.total_work_hours:.1f}h

**Work Type Breakdown:**
{chr(10).join(f"- {wt.title()}: {count} items" for wt, count in work_breakdown.items())}

**Project Activity:**
{chr(10).join(f"- {project}: {count} events" for project, count in list(project_breakdown.items())[:5])}

**Summary Highlights:**
{chr(10).join(f"- {summary.name} ({summary.estimated_hours:.1f}h)" for summary in result.summaries[:5])}
"""
    
    def _create_events_table(self, result) -> List[Dict[str, Any]]:
        """Create table data for events display."""
        table_data = []
        
        # Create table from work summaries (more meaningful than raw events)
        for summary in result.summaries:
            # Find associated classification
            classification = None
            for c in result.classifications:
                if c.work_type == summary.work_type:
                    classification = c
                    break
            
            table_data.append({
                "Work Item": summary.name,
                "Type": summary.work_type.value.title(),
                "Hours": f"{summary.estimated_hours:.1f}h",
                "Commits": classification.total_commits if classification else 0,
                "Branch": classification.branch_name if classification else "N/A",
                "MR": f"#{classification.merge_request_id}" if classification and classification.merge_request_id else "N/A",
                "Confidence": f"{summary.confidence:.0%}"
            })
        
        return table_data
    
    def run_stdio(self):
        """Run server with stdio transport (development)."""
        print("🚀 Starting GitLab Events MCP Server (stdio)...")
        self.mcp.run(transport="stdio")
    
    def run_http(self, host: str = "0.0.0.0", port: int = 8000):
        """Run server with HTTP/SSE transport (production)."""
        print(f"🚀 Starting GitLab Events MCP Server (HTTP) on {host}:{port}...")
        self.mcp.run(transport="sse", host=host, port=port)