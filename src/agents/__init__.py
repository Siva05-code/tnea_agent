"""Agents package - Direct Python implementation without Mastra"""

from .college_agent import college_agent
from .sql_generation_agent import sql_generation_agent, sql_agent

__all__ = [
    "college_agent",
    "sql_generation_agent",
    "sql_agent",
]
