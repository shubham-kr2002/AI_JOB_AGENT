"""
Project JobHunter V3 - Agents Package
Multi-agent system for autonomous job application.

Agents:
- BrowserAgent (Executor): Playwright-based browser automation
- PlannerAgent: DAG generation and task planning
- CriticAgent: Hallucination detection and validation
- RecoveryAgent: Error handling and self-healing

Services:
- WorldModelService: Selector lookup from World Model
- LearningService: Captures successful selectors for learning
"""

from app.agents.executor import BrowserAgent, StepResult, ActionType
from app.agents.world_model_service import WorldModelService
from app.services.learning import LearningService, get_learning_service, update_world_model

__all__ = [
    "BrowserAgent",
    "StepResult",
    "ActionType",
    "WorldModelService",
    "LearningService",
    "get_learning_service",
    "update_world_model",
]
