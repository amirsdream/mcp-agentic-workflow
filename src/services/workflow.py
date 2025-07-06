from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..models.gitlab import AgentState, GitLabIssueFilter
from ..services.agents import AgentOrchestrator


class WorkflowService:
    """LangGraph workflow service for multi-agent processing"""
    
    def __init__(self, agent_orchestrator: AgentOrchestrator):
        self.orchestrator = agent_orchestrator
        self.workflow = self._create_workflow()
    
    def _create_workflow(self) -> StateGraph:
        """Create the multi-agent workflow using LangGraph"""
        
        async def user_proxy_node(state: AgentState) -> AgentState:
            """User proxy agent node"""
            query = state["user_query"]
            
            # Analyze the query
            analysis = await self.orchestrator.user_proxy.process(query)
            
            if analysis.get("clarification_needed"):
                return {
                    **state,
                    "needs_gitlab_tool": False,
                    "final_response": analysis["clarification_needed"],
                    "tokens_used": state.get("tokens_used", 0) + 100
                }
            
            if analysis.get("needs_gitlab_tool"):
                return {
                    **state,
                    "needs_gitlab_tool": True,
                    "gitlab_filters": analysis.get("filters", {}),
                    "user_intent": analysis.get("intent", "")
                }
            else:
                return {
                    **state,
                    "needs_gitlab_tool": False,
                    "final_response": "I can help you with GitLab issues. Please specify what you'd like to see (e.g., 'show me issues from this month', 'high priority bugs', etc.)",
                    "tokens_used": state.get("tokens_used", 0) + 50
                }
        
        async def gitlab_agent_node(state: AgentState) -> AgentState:
            """GitLab agent node"""
            if not state.get("needs_gitlab_tool"):
                return state
            
            filters = state.get("gitlab_filters", {})
            
            # Call GitLab agent directly with filters dict
            result = await self.orchestrator.gitlab_agent.process(filters)
            
            return {
                **state,
                "gitlab_response": result,
                "tokens_used": state.get("tokens_used", 0) + 200
            }
        
        async def response_formatter_node(state: AgentState) -> AgentState:
            """Format the final response"""
            if state.get("final_response"):
                return state
            
            gitlab_response = state.get("gitlab_response")
            user_intent = state.get("user_intent", "")
            
            formatted_response = self.orchestrator._format_response(gitlab_response, user_intent)
            
            return {
                **state,
                "final_response": formatted_response,
                "tokens_used": state.get("tokens_used", 0) + 100
            }
        
        # Define routing logic
        def should_call_gitlab(state: AgentState) -> str:
            return "gitlab_agent" if state.get("needs_gitlab_tool") else "response_formatter"
        
        # Build the workflow graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("user_proxy", user_proxy_node)
        workflow.add_node("gitlab_agent", gitlab_agent_node) 
        workflow.add_node("response_formatter", response_formatter_node)
        
        # Add edges
        workflow.set_entry_point("user_proxy")
        workflow.add_conditional_edges(
            "user_proxy",
            should_call_gitlab,
            {
                "gitlab_agent": "gitlab_agent",
                "response_formatter": "response_formatter"
            }
        )
        workflow.add_edge("gitlab_agent", "response_formatter")
        workflow.add_edge("response_formatter", END)
        
        # Compile the workflow
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)
    
    async def process_workflow(self, user_message: str) -> Dict[str, Any]:
        """Process user message through the workflow"""
        try:
            # Initial state
            initial_state = {
                "messages": [],
                "user_query": user_message,
                "gitlab_response": None,
                "needs_gitlab_tool": False,
                "final_response": "",
                "tokens_used": 0
            }
            
            # Run the workflow
            config = {"configurable": {"thread_id": "user_session"}}
            result = await self.workflow.ainvoke(initial_state, config)
            print(f"Workflow result: {result}")
            return {
                "type": "workflow_response",
                "content": result["final_response"],
                "gitlab_response": result.get("gitlab_response"),
                "tokens_used": result.get("tokens_used", 0)
            }
            
        except Exception as e:
            return {
                "type": "error",
                "content": f"Error in workflow: {str(e)}",
                "tokens_used": 0
            }