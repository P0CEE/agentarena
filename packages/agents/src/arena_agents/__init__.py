"""Agents AgentArena : la couche applicative off-chain (LLM), jamais dans le consensus."""

from arena_agents.base import Agent, AgentError
from arena_agents.mistral import MistralAgent
from arena_agents.runner import AgentRunner, normalize_scores
from arena_agents.stub import StubAgent

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentError",
    "AgentRunner",
    "MistralAgent",
    "StubAgent",
    "normalize_scores",
]
