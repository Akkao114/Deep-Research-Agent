"""State and Checkpoint Manager for Research Agent."""

import json
from datetime import date
from pathlib import Path

from config import (
    COST_PER_1M_INPUT_TOKENS,
    COST_PER_1M_OUTPUT_TOKENS,
    DATA_DIR,
    REPORTS_DIR,
)
from schemas import PartResearch, ReportMeta, ResearchState, ResearchTarget, Signal
from utils import log


class StateManager:
    """Handles checkpoints, report saving, and metadata tracking."""

    def __init__(self, target: ResearchTarget, mode: str):
        self.target = target
        self.state = ResearchState(target=target, mode=mode)
        self.report_parts: dict[int, str] = {}
        self.failed_part_ids: list[int] = []

    def _checkpoint_path(self) -> Path:
        """Return the checkpoint file path for the current target."""
        name = self.target.ticker or self.target.raw_input.replace(" ", "_")
        today = date.today().isoformat()
        return DATA_DIR / f"checkpoint_{name}_{today}.json"

    def save_checkpoint(self, completed_part_ids: list[int]):
        """Save current progress to a checkpoint file."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cp = {
            "target": self.state.target.model_dump(),
            "mode": self.state.mode,
            "date": self.state.research_date.isoformat(),
            "total_input_tokens": self.state.total_input_tokens,
            "total_output_tokens": self.state.total_output_tokens,
            "completed_part_ids": completed_part_ids,
            "parts": [p.model_dump() for p in self.state.parts],
            "report_parts": {str(k): v for k, v in self.report_parts.items()},
            "failed_part_ids": self.failed_part_ids,
            "models_used": dict(self.state.models_used),
        }
        path = self._checkpoint_path()
        path.write_text(json.dumps(cp, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"Checkpoint saved: {path.name} (Parts {completed_part_ids})", "done")

    def load_checkpoint(self, resume: bool) -> list[int]:
        """Try to restore from checkpoint. Returns list of completed part IDs."""
        if not resume:
            return []

        path = self._checkpoint_path()
        if not path.exists():
            return []

        try:
            cp = json.loads(path.read_text(encoding="utf-8"))
            completed = cp.get("completed_part_ids", [])
            log(f"Checkpoint found: {path.name} (Parts {completed})", "info")

            if not completed:
                return []

            # Restore state
            self.state.total_input_tokens = cp.get("total_input_tokens", 0)
            self.state.total_output_tokens = cp.get("total_output_tokens", 0)

            # Restore parts
            for p_data in cp.get("parts", []):
                part = PartResearch(**p_data)
                self.state.parts.append(part)

            # Restore report_parts
            for k, v in cp.get("report_parts", {}).items():
                self.report_parts[int(k)] = v
            
            # Restore failed parts
            self.failed_part_ids = cp.get("failed_part_ids", [])

            # Restore models_used
            self.state.models_used = cp.get("models_used", {})

            log(f"Resumed from checkpoint. Completed parts: {completed}", "done")
            return completed

        except Exception as e:
            log(f"Failed to load checkpoint: {e}", "warn")
            return []

    def assemble_report_body(self) -> str:
        """Assemble completed parts into a report body."""
        sections = []
        for part_id in sorted(self.report_parts.keys()):
            if part_id != 11:  # Part 11 is appended separately
                sections.append(self.report_parts[part_id])
        return "\n\n---\n\n".join(sections)

    def generate_final_report_text(self, body: str, judgment: str, signal: Signal | None, confidence: float | None) -> str:
        """Build the complete report with header."""
        company = self.target.company_name or self.target.raw_input
        ticker_str = f" ({self.target.ticker})" if self.target.ticker else ""
        signal_str = f"{signal.value} | Confidence: {confidence*100:.0f}%" if signal and confidence else "N/A"
        today = date.today().isoformat()

        failed_note = ""
        if self.failed_part_ids:
            parts_str = ", ".join(str(p) for p in self.failed_part_ids)
            failed_note = f"\n> ⚠️ **Warning:** Part(s) {parts_str} failed during research and are missing from this report.\n"

        header = f"""\
# {company}{ticker_str} — Deep Research & Review

**Date:** {today}
**Signal:** {signal_str}
**Mode:** {self.state.mode.replace('_', ' ').title()}
{failed_note}
---

"""
        return header + body + "\n\n---\n\n" + judgment

    def save_report(self, report: str) -> Path:
        """Save report as markdown file."""
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        name = self.target.ticker or self.target.raw_input.replace(" ", "_")
        today = date.today().isoformat()
        filename = f"{name}_{today}.md"
        path = REPORTS_DIR / filename
        path.write_text(report, encoding="utf-8")
        return path

    def save_metadata(self, signal: Signal | None, confidence: float | None, report_path: Path):
        """Save structured JSON metadata alongside the report."""
        meta = ReportMeta(
            target=self.target,
            signal=signal,
            confidence=confidence,
            cost_usd=self.estimate_cost(),
            models_used=dict(self.state.models_used),
        )
        json_path = report_path.with_suffix(".json")
        json_path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")

    def estimate_cost(self) -> float:
        """Rough cost estimate based on token usage."""
        inp = self.state.total_input_tokens
        out = self.state.total_output_tokens
        input_cost = inp * COST_PER_1M_INPUT_TOKENS / 1_000_000
        output_cost = out * COST_PER_1M_OUTPUT_TOKENS / 1_000_000
        return input_cost + output_cost
