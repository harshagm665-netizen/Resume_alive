"""
functions/agents/base_agent.py — Base Agent implementation with tool calling support.
"""

from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

from llm.client import llm
from llm.temperature import TaskType

class AgentTool(BaseModel):
    name: str
    description: str
    func: Callable

class BaseAgent:
    """Base class for all specific AI agents in the system."""
    
    def __init__(self, name: str, role: str, goal: str, task_type: TaskType = TaskType.JSON_OUTPUT):
        self.name = name
        self.role = role
        self.goal = goal
        self.task_type = task_type
        self.tools: Dict[str, AgentTool] = {}
        
    def register_tool(self, name: str, description: str, func: Callable):
        self.tools[name] = AgentTool(name=name, description=description, func=func)

    def get_system_prompt(self) -> str:
        prompt = f"You are {self.name}. Role: {self.role}\nGoal: {self.goal}\n"
        if self.tools:
            prompt += "You have access to the following tools:\n"
            for t in self.tools.values():
                prompt += f"- {t.name}: {t.description}\n"
        return prompt

    def execute(self, task: str, **kwargs) -> Any:
        logger.info(f"[{self.name}] Executing task...")
        system_prompt = self.get_system_prompt()
        return llm.chat(system_prompt, task, self.task_type)
