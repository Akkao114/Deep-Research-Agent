"""Pydantic data models for the equity research agent."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class Signal(str, Enum):
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


class ResearchTarget(BaseModel):
    """The research subject — can be a ticker or a keyword (e.g. unlisted company)."""
    raw_input: str
    ticker: str | None = None  # None if unlisted / keyword-only
    company_name: str | None = None
    is_listed: bool = True


class ToolCallRecord(BaseModel):
    """Single tool invocation record for logging."""
    tool_name: str
    input_args: dict
    output_summary: str = ""
    tokens_used: int = 0


class PartResearch(BaseModel):
    """Collected research data for one Part of the report."""
    part_id: int
    part_title: str
    raw_data: str = ""  # concatenated tool results
    summary: str = ""   # Haiku-extracted structured summary


class ResearchState(BaseModel):
    """Tracks the full state of a research session."""
    target: ResearchTarget
    mode: str = "deep_research_review"
    research_date: date = Field(default_factory=date.today)
    parts: list[PartResearch] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)  # conversation history
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    models_used: dict[str, str] = Field(default_factory=dict)  # {tier: model_name}


class ReportMeta(BaseModel):
    """Metadata for the final report."""
    target: ResearchTarget
    signal: Signal | None = None
    confidence: float | None = None  # 0-1
    report_date: date = Field(default_factory=date.today)
    cost_usd: float = 0.0
    models_used: dict[str, str] = Field(default_factory=dict)  # {tier: model_name}
    sources: list[str] = Field(default_factory=list)
