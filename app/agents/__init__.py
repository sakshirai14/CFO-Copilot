"""app/agents/__init__.py

Google Agent Development Kit (ADK) agent suite for CFO Copilot.
"""

from app.agents.router_agent import RouterAgent
from app.agents.facts_agent import FactsAgent
from app.agents.answer_writer import AnswerWriterAgent
from app.agents.verifier_agent import VerifierAgent
from app.agents.root_agent import CfoCopilotRootAgent

__all__ = [
    "RouterAgent",
    "FactsAgent",
    "AnswerWriterAgent",
    "VerifierAgent",
    "CfoCopilotRootAgent",
]
