"""app/inference/contract.py

Pydantic schemas for the Grounded-Answer Contract (Foundation Locks 1, 3, 10, 11).
Defines input facts passed to local small models and structured output contracts.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    INSUFFICIENT_DATA = "insufficient_data"
    CONFLICT_NOTED = "conflict_noted"
    OK_EXTRACTIVE = "ok_extractive"

    # Aliases for backwards compatibility with test harnesses and prompts
    OK = "answered"
    REFUSED = "insufficient_data"
    MISSING_DATA = "insufficient_data"
    UNSUPPORTED = "insufficient_data"


class InputFact(BaseModel):
    """A verified factual input extracted from SQL KPIs or chunk retrieval."""
    fact_id: str = Field(..., description="Unique deterministic identifier, e.g. 'fact_kpi_1', 'ARG_2022Q2_CF#t1'")
    fact_type: str = Field("kpi_value", description="Type: 'kpi_value', 'table_chunk', 'text_chunk'")
    company_id: Optional[str] = None
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    metric_name: Optional[str] = None
    value: Optional[Union[float, int, str]] = None
    text: str = Field(..., description="Verbatim or formatted factual assertion provided to the model")

    def to_prompt_text(self) -> str:
        """Formats the fact for LLM prompt context."""
        parts = [f"[{self.fact_id}]"]
        if self.company_id:
            parts.append(self.company_id)
        if self.fiscal_year and self.fiscal_quarter:
            parts.append(f"FY{self.fiscal_year}Q{self.fiscal_quarter}")
        if self.metric_name:
            parts.append(f"{self.metric_name}:")
        parts.append(self.text)
        return " ".join(parts)


class GroundedAnswer(BaseModel):
    """Structured response contract for local LLM generation."""
    status: AnswerStatus = Field(..., description="Status: 'answered', 'insufficient_data', or 'conflict_noted'")
    answer: str = Field(..., description="Executive narrative answer for the CFO")
    facts_used: List[str] = Field(default_factory=list, description="List of fact IDs used to construct the answer")
    caveats: List[str] = Field(default_factory=list, description="Noted caveats, restatements, or limitations")

    @field_validator("status", mode="before")
    def parse_status(cls, v):
        if isinstance(v, str):
            v_clean = v.strip().lower()
            mapping = {
                "ok": "answered",
                "answered": "answered",
                "success": "answered",
                "refused": "insufficient_data",
                "missing_data": "insufficient_data",
                "insufficient_data": "insufficient_data",
                "unsupported": "insufficient_data",
                "conflict_noted": "conflict_noted",
            }
            if v_clean in mapping:
                return AnswerStatus(mapping[v_clean])
            return AnswerStatus(v_clean)
        return v

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "answer": self.answer,
            "facts_used": self.facts_used,
            "caveats": self.caveats,
        }


def get_grounded_answer_json_schema() -> Dict[str, Any]:
    """Returns strict JSON schema for OpenAI response_format or llama-server grammar."""
    return GroundedAnswer.model_json_schema()
