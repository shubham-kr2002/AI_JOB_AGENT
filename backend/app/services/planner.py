"""
Project JobHunter V3 - Task Planner Service
Implements FR-04: DAG Generation

Converts a Goal into a Directed Acyclic Graph (DAG) of dependent tasks.
The DAG represents the execution plan for the autonomous agent.

Pipeline: Search → Filter → Scrape JD → Custom Resume → Apply

Reference: BackendTechnicalDesign.md Phase 1 (The Planner)
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Set
from uuid import uuid4
from enum import Enum

from app.services.intent import Goal, ActionType
from app.models.task import ActionType as TaskActionType


class NodeStatus(str, Enum):
    """Status of a DAG node."""
    PENDING = "pending"
    READY = "ready"  # All dependencies met
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DAGNode:
    """
    A single node in the execution DAG.
    
    Each node represents an atomic action the agent can perform.
    """
    # Unique identifier
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    
    # Human-readable name
    name: str = ""
    
    # Action type (matches TaskStep action types)
    action: str = "navigate"
    
    # Dependencies (list of node IDs that must complete first)
    depends_on: List[str] = field(default_factory=list)
    
    # Execution payload
    payload: Dict[str, Any] = field(default_factory=dict)
    
    # Expected outputs (for downstream nodes)
    outputs: List[str] = field(default_factory=list)
    
    # Status
    status: NodeStatus = NodeStatus.PENDING
    
    # Metadata
    estimated_duration_seconds: int = 5
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "action": self.action,
            "depends_on": self.depends_on,
            "payload": self.payload,
            "outputs": self.outputs,
            "status": self.status.value,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


@dataclass
class TaskGraph:
    """
    A Directed Acyclic Graph representing an execution plan.
    
    The graph is topologically sorted so nodes can be executed
    in order, respecting dependencies.
    """
    # All nodes in the graph
    nodes: List[DAGNode] = field(default_factory=list)
    
    # The goal this graph was generated for
    goal_summary: str = ""
    
    # Metadata
    total_estimated_seconds: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "goal_summary": self.goal_summary,
            "total_nodes": len(self.nodes),
            "total_estimated_seconds": self.total_estimated_seconds,
            "nodes": [n.to_dict() for n in self.nodes],
        }
    
    def get_ready_nodes(self) -> List[DAGNode]:
        """Get nodes that are ready to execute (all dependencies met)."""
        completed_ids = {n.id for n in self.nodes if n.status == NodeStatus.COMPLETED}
        ready = []
        for node in self.nodes:
            if node.status == NodeStatus.PENDING:
                if all(dep_id in completed_ids for dep_id in node.depends_on):
                    ready.append(node)
        return ready
    
    def mark_completed(self, node_id: str) -> None:
        """Mark a node as completed."""
        for node in self.nodes:
            if node.id == node_id:
                node.status = NodeStatus.COMPLETED
                break


class TaskPlanner:
    """
    Generates execution DAGs from Goals.
    
    The planner creates a structured plan that the executor can follow
    to accomplish the user's goal autonomously.
    """
    
    def __init__(self):
        """Initialize the planner."""
        pass
    
    def generate_task_graph(self, goal: Goal) -> TaskGraph:
        """
        Generate a DAG from a Goal.
        
        Args:
            goal: The parsed Goal object
            
        Returns:
            TaskGraph with all nodes and dependencies
        """
        nodes: List[DAGNode] = []
        
        # Phase 1: Search nodes (one per platform)
        search_node_ids = []
        for platform in goal.platforms:
            search_node = self._create_search_node(goal, platform)
            nodes.append(search_node)
            search_node_ids.append(search_node.id)
        
        # Phase 2: Aggregate results (depends on all searches)
        aggregate_node = DAGNode(
            name="Aggregate Search Results",
            action="parse",
            depends_on=search_node_ids,
            payload={
                "operation": "merge_job_lists",
                "deduplicate": True,
            },
            outputs=["raw_job_list"],
            estimated_duration_seconds=2,
        )
        nodes.append(aggregate_node)
        
        # Phase 3: Filter jobs based on constraints
        filter_node = DAGNode(
            name="Apply Filters",
            action="filter",
            depends_on=[aggregate_node.id],
            payload={
                "constraints": goal.constraints.to_dict(),
                "target_count": goal.target_count * 2,  # Get more than needed for fallbacks
            },
            outputs=["filtered_job_list"],
            estimated_duration_seconds=3,
        )
        nodes.append(filter_node)
        
        # Phase 4: Rank and select top candidates
        rank_node = DAGNode(
            name="Rank Jobs by Fit",
            action="analyze",
            depends_on=[filter_node.id],
            payload={
                "operation": "rank_by_match",
                "role_keywords": goal.role_keywords,
                "limit": goal.target_count,
            },
            outputs=["ranked_job_list"],
            estimated_duration_seconds=5,
        )
        nodes.append(rank_node)
        
        # Phase 5: For each job (represented as a loop control node)
        # In reality, this spawns child nodes dynamically during execution
        if goal.action == ActionType.APPLY:
            # Application pipeline for each job
            loop_node = DAGNode(
                name=f"Process Top {goal.target_count} Jobs",
                action="loop",
                depends_on=[rank_node.id],
                payload={
                    "source": "ranked_job_list",
                    "limit": goal.target_count,
                    "pipeline": self._get_application_pipeline_template(),
                },
                outputs=["application_results"],
                estimated_duration_seconds=goal.target_count * 180,  # ~3 min per app
            )
            nodes.append(loop_node)
            
            # Final summary node
            summary_node = DAGNode(
                name="Generate Report",
                action="summarize",
                depends_on=[loop_node.id],
                payload={
                    "operation": "generate_completion_report",
                },
                outputs=["final_report"],
                estimated_duration_seconds=2,
            )
            nodes.append(summary_node)
        
        # Calculate total estimated time
        total_seconds = sum(n.estimated_duration_seconds for n in nodes)
        
        # Create the graph
        graph = TaskGraph(
            nodes=nodes,
            goal_summary=self._generate_goal_summary(goal),
            total_estimated_seconds=total_seconds,
        )
        
        return graph
    
    def _create_search_node(self, goal: Goal, platform: str) -> DAGNode:
        """Create a search node for a specific platform."""
        return DAGNode(
            name=f"Search {platform.title()}",
            action="search",
            depends_on=[],
            payload={
                "platform": platform,
                "query": goal.role,
                "keywords": goal.role_keywords,
                "location": goal.constraints.locations[0] if goal.constraints.locations else None,
                "remote": goal.constraints.remote_only,
                "max_results": 50,  # Fetch more, filter later
            },
            outputs=[f"{platform}_job_list"],
            estimated_duration_seconds=30,
        )
    
    def _get_application_pipeline_template(self) -> List[Dict[str, Any]]:
        """
        Get the template for processing a single job application.
        
        This is a sub-DAG that gets instantiated for each job.
        """
        return [
            {
                "name": "Navigate to Job",
                "action": "navigate",
                "payload": {"url": "{{job.url}}"},
                "duration": 5,
            },
            {
                "name": "Scrape Job Details",
                "action": "scrape",
                "payload": {"extract": ["description", "requirements", "company_info"]},
                "duration": 3,
            },
            {
                "name": "Tailor Resume",
                "action": "generate",
                "payload": {
                    "type": "tailored_resume",
                    "jd_context": "{{job.description}}",
                    "keywords": "{{job.requirements}}",
                },
                "duration": 10,
            },
            {
                "name": "Start Application",
                "action": "click",
                "payload": {"target": "apply_button"},
                "duration": 3,
            },
            {
                "name": "Fill Application Form",
                "action": "fill_form",
                "payload": {"use_tailored_resume": True},
                "duration": 60,
            },
            {
                "name": "Critic Review",
                "action": "verify",
                "payload": {"check": "hallucination_guard"},
                "duration": 5,
            },
            {
                "name": "Submit Application",
                "action": "submit",
                "payload": {"confirm": True},
                "duration": 5,
            },
            {
                "name": "Capture Confirmation",
                "action": "screenshot",
                "payload": {"save_to": "{{job.id}}_confirmation.png"},
                "duration": 2,
            },
        ]
    
    def _generate_goal_summary(self, goal: Goal) -> str:
        """Generate a human-readable summary of the goal."""
        action = "Apply to" if goal.action == ActionType.APPLY else "Search for"
        location = ""
        if goal.constraints.locations:
            location = f" in {', '.join(goal.constraints.locations)}"
        elif goal.constraints.remote_only:
            location = " (remote)"
        
        platforms = ", ".join(p.title() for p in goal.platforms)
        
        return f"{action} {goal.target_count} {goal.role} roles{location} on {platforms}"


def generate_task_graph(goal: Goal) -> TaskGraph:
    """
    Convenience function to generate a task graph from a goal.
    
    Args:
        goal: The parsed Goal object
        
    Returns:
        TaskGraph with execution plan
    """
    planner = TaskPlanner()
    return planner.generate_task_graph(goal)


def plan_from_prompt(prompt: str, use_llm: bool = True) -> Dict[str, Any]:
    """
    End-to-end planning from a raw prompt.
    
    Args:
        prompt: User's natural language prompt
        use_llm: Whether to use LLM for intent parsing
        
    Returns:
        Dictionary with goal and task graph
    """
    from app.services.intent import compile_intent
    
    # Step 1: Parse intent
    goal = compile_intent(prompt, use_llm=use_llm)
    
    # Step 2: Generate task graph
    graph = generate_task_graph(goal)
    
    return {
        "goal": goal.to_dict(),
        "plan": graph.to_dict(),
    }
