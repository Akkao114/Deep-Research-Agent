"""Two-phase agentic loop for equity research."""

from __future__ import annotations

import json
import re
import time

from router import ModelRouter
from router_config import ENABLE_PREFLIGHT_CHECK

from config import (
    EXTRACTION_MAX_TOKENS,
    EXTRACTION_RAW_CHARS,
    JUDGMENT_MAX_TOKENS,
    JUDGMENT_REPORT_CHARS,
    MAX_MESSAGES_PER_PART,
    MAX_TOOL_CALLS_PER_PART,
    MODES_DIR,
    RESEARCH_MAX_TOKENS,
    TOOL_RESULT_LLM_CHARS,
    TOOL_RESULT_RAW_CHARS,
    WRITING_MAX_TOKENS,
)
from prompts import (
    EXTRACTION_PROMPT,
    FINAL_JUDGMENT_PROMPT,
    PARTS,
    REPORT_WRITING_PROMPT,
    RESEARCH_SYSTEM_PROMPT,
)
from schemas import PartResearch, ResearchTarget, Signal
from state import StateManager
from tools import TOOL_DEFINITIONS, execute_tool
from utils import format_tool_results_message, log, serialize_assistant_message


class ResearchAgent:
    def __init__(self, target: ResearchTarget, mode: str = "deep_research_review", resume: bool = True):
        self.router = ModelRouter()
        self.target = target
        self.mode = mode
        self.mode_content = self._load_mode_config()
        self.manager = StateManager(target, mode)
        self.resume = resume

    def _record_model(self, response):
        """Record the actual model used from the API response."""
        tier = response.tier
        model = response.model
        if tier not in self.manager.state.models_used:
            self.manager.state.models_used[tier] = model

    def _load_mode_config(self) -> str:
        """Load mode configuration markdown file."""
        mode_file = MODES_DIR / f"{self.mode}.md"
        if not mode_file.exists():
            log(f"Mode config not found: {mode_file}", "warn")
            return ""
        return mode_file.read_text(encoding="utf-8")

    def _target_description(self) -> str:
        parts = [f"Input: {self.target.raw_input}"]
        if self.target.ticker:
            parts.append(f"Ticker: {self.target.ticker}")
        if self.target.company_name:
            parts.append(f"Company: {self.target.company_name}")
        if not self.target.is_listed:
            parts.append("Note: This may be an unlisted company. Use web_search as primary data source.")
        return "\n".join(parts)

    def _research_part(self, part_id: int, part_title: str, part_desc: str) -> PartResearch:
        """Run a research loop for one part."""
        log(f"Researching Part {part_id}: {part_title}")

        system_prompt = RESEARCH_SYSTEM_PROMPT.format(
            target_description=self._target_description(),
            mode_name=self.mode.replace("_", " ").title(),
            mode_content=self.mode_content,
            part_id=part_id,
            part_title=part_title,
        )

        context_summary = ""
        if self.manager.state.parts:
            summaries = [f"Part {p.part_id} ({p.part_title}): {p.summary[:500]}" for p in self.manager.state.parts]
            context_summary = "\n\n已完成的研究:\n" + "\n".join(summaries)

        messages = [{
            "role": "user",
            "content": (
                f"请开始研究 Part {part_id}: {part_title}\n"
                f"具体要求: {part_desc}\n"
                f"研究对象: {self._target_description()}{context_summary}\n\n"
                f"⚠️ 提醒: 你只研究 {self.target.company_name or self.target.raw_input}"
                f"{'(' + self.target.ticker + ')' if self.target.ticker else ''}，不要偏离到其他公司。"
            )
        }]

        raw_data_chunks: list[str] = []
        tool_call_count = 0

        for _ in range(MAX_MESSAGES_PER_PART):
            response = self.router.route_raw(
                model_tier="medium",
                messages=messages,
                system=system_prompt,
                tools=TOOL_DEFINITIONS,
                max_tokens=RESEARCH_MAX_TOKENS,
            )

            self.manager.state.total_input_tokens += response.input_tokens
            self.manager.state.total_output_tokens += response.output_tokens
            self._record_model(response)

            if not response.tool_calls:
                log(f"Part {part_id} research complete ({tool_call_count} tool calls)", "done")
                raw_data_chunks.append(response.content)
                break

            messages.append(serialize_assistant_message(response))

            tool_results = []
            for tc in response.tool_calls:
                tool_call_count += 1
                log(f"  [{tool_call_count}] {tc['name']}({json.dumps(tc['input'], ensure_ascii=False)[:80]})", "tool")
                result = execute_tool(tc["name"], tc["input"])
                raw_data_chunks.append(f"[{tc['name']}] {result[:TOOL_RESULT_RAW_CHARS]}")
                tool_results.append({
                    "tool_use_id": tc["id"],
                    "content": result[:TOOL_RESULT_LLM_CHARS],
                })

            is_openai = hasattr(response.raw_response, "choices")
            formatted_results = format_tool_results_message(tool_results, is_openai)
            if isinstance(formatted_results, list):
                messages.extend(formatted_results)
            else:
                messages.append(formatted_results)

            if tool_call_count >= MAX_TOOL_CALLS_PER_PART:
                log(f"Part {part_id} hit tool call limit ({MAX_TOOL_CALLS_PER_PART})", "warn")
                messages.append({
                    "role": "user",
                    "content": "You have reached the tool call limit. Summarize findings. Start with 'RESEARCH COMPLETE:'"
                })
                final_resp = self.router.route_raw(
                    model_tier="medium",
                    messages=messages,
                    system=system_prompt,
                    max_tokens=EXTRACTION_MAX_TOKENS,
                )
                self.manager.state.total_input_tokens += final_resp.input_tokens
                self.manager.state.total_output_tokens += final_resp.output_tokens
                self._record_model(final_resp)
                raw_data_chunks.append(final_resp.content)
                break

        return PartResearch(part_id=part_id, part_title=part_title, raw_data="\n\n---\n\n".join(raw_data_chunks))

    def _extract_data(self, part: PartResearch) -> str:
        log(f"Extracting data for Part {part.part_id}...")
        prompt = EXTRACTION_PROMPT.format(
            target_description=self._target_description(),
            part_title=part.part_title,
            raw_data=part.raw_data[:EXTRACTION_RAW_CHARS],
        )
        response = self.router.route_raw(model_tier="low", messages=[{"role": "user", "content": prompt}], max_tokens=EXTRACTION_MAX_TOKENS)
        self.manager.state.total_input_tokens += response.input_tokens
        self.manager.state.total_output_tokens += response.output_tokens
        self._record_model(response)
        return response.content

    def _write_part(self, part: PartResearch, part_section: str) -> str:
        log(f"Writing Part {part.part_id}: {part.part_title}...")
        prompt = REPORT_WRITING_PROMPT.format(
            target_description=self._target_description(),
            part_section=part_section,
            extracted_data=part.summary,
        )
        response = self.router.route_raw(model_tier="high", messages=[{"role": "user", "content": prompt}], max_tokens=WRITING_MAX_TOKENS)
        self.manager.state.total_input_tokens += response.input_tokens
        self.manager.state.total_output_tokens += response.output_tokens
        self._record_model(response)
        return response.content

    def _final_judgment(self, full_report: str) -> tuple[str, Signal | None, float | None]:
        log("Generating final investment judgment...", "info")
        company = self.target.company_name or self.target.raw_input
        prompt = FINAL_JUDGMENT_PROMPT.format(company=company, full_report=full_report[:JUDGMENT_REPORT_CHARS])
        response = self.router.route_raw(model_tier="high", messages=[{"role": "user", "content": prompt}], max_tokens=JUDGMENT_MAX_TOKENS)
        self.manager.state.total_input_tokens += response.input_tokens
        self.manager.state.total_output_tokens += response.output_tokens
        self._record_model(response)
        
        signal, confidence = self._parse_signal(response.content)
        return response.content, signal, confidence

    def _parse_signal(self, text: str) -> tuple[Signal | None, float | None]:
        signal = None
        confidence = None
        header = text[:300]
        # Use word boundary to avoid matching "BUYBACK" etc.
        if re.search(r"\bBUY\b", header): signal = Signal.BUY
        elif re.search(r"\bSELL\b", header): signal = Signal.SELL
        elif re.search(r"\bHOLD\b", header): signal = Signal.HOLD
        conf_match = re.search(r"Confidence:\s*(\d+)%", header)
        if conf_match: confidence = float(conf_match.group(1)) / 100
        return signal, confidence

    def _get_section_from_config(self, part_id: int, part_title: str) -> str:
        lines = self.mode_content.split("\n")
        section_lines = []
        in_section = False
        part_marker = f"## Part {part_id}:"
        for line in lines:
            if line.strip().startswith(part_marker): in_section = True
            if in_section:
                if line.strip().startswith("## Part ") and not line.strip().startswith(part_marker): break
                section_lines.append(line)
        if not section_lines:
            for i, line in enumerate(lines):
                if part_title.split("（")[0] in line or f"Part {part_id}" in line:
                    in_section = True
                    continue
                if in_section:
                    if line.strip().startswith("## Part ") or line.strip().startswith("---"): break
                    section_lines.append(line)
        return "\n".join(section_lines) if section_lines else f"Part {part_id}: {part_title}"

    def run(self) -> str:
        # Pre-flight check: ensure all model tiers can be reached before starting
        if ENABLE_PREFLIGHT_CHECK:
            self.router.preflight_check()

        start_time = time.time()
        log(f"Starting research: {self.target.raw_input} (mode: {self.mode})")
        completed_part_ids = self.manager.load_checkpoint(self.resume)
        
        # Identify Part 4 (Company Fundamentals) for preview
        preview_part_id = 4
        preview_part = next((p for p in PARTS if p[0] == preview_part_id), None)
        
        parts_to_run = PARTS[:10]
        
        if preview_part and preview_part_id not in completed_part_ids:
            log(f"Executing Preview Phase: {preview_part[1]}", "info")
            try:
                part = self._research_part(preview_part[0], preview_part[1], preview_part[2])
                part.summary = self._extract_data(part)
                self.manager.state.parts.append(part)
                
                section_text = self._get_section_from_config(preview_part[0], preview_part[1])
                self.manager.report_parts[preview_part[0]] = self._write_part(part, section_text)
                
                completed_part_ids.append(preview_part[0])
                self.manager.save_checkpoint(completed_part_ids)
                log(f"Preview Part {preview_part[0]} done. Tokens: {self.manager.state.total_input_tokens:,} in / {self.manager.state.total_output_tokens:,} out", "done")
                
                print(f"\n--- PREVIEW: {preview_part[1]} ---")
                print(self.manager.report_parts[preview_part[0]])
                print("-----------------------------------\n")
                
                user_ok = input("Preview completed. Does this look OK? Continue with full research? [y/N]: ").strip().lower()
                if user_ok not in ['y', 'yes']:
                    log("User aborted after preview.", "warn")
                    return ""
                
            except KeyboardInterrupt:
                log("Interrupted by user during preview. Progress saved.", "warn")
                self.manager.save_checkpoint(completed_part_ids)
                raise
            except Exception as e:
                log(f"Error in Preview Part {preview_part[0]}: {e}. Saving checkpoint.", "warn")
                self.manager.failed_part_ids.append(preview_part[0])
                self.manager.save_checkpoint(completed_part_ids)
                user_ok = input("Preview failed. Continue with full research anyway? [y/N]: ").strip().lower()
                if user_ok not in ['y', 'yes']:
                    log("User aborted after preview failure.", "warn")
                    return ""

        for part_id, part_title, part_desc in parts_to_run:
            if part_id in completed_part_ids:
                log(f"Part {part_id} already completed, skipping.", "info")
                continue
            try:
                part = self._research_part(part_id, part_title, part_desc)
                part.summary = self._extract_data(part)
                self.manager.state.parts.append(part)
                
                section_text = self._get_section_from_config(part_id, part_title)
                self.manager.report_parts[part_id] = self._write_part(part, section_text)
                
                completed_part_ids.append(part_id)
                self.manager.save_checkpoint(completed_part_ids)
                log(f"Part {part_id} done. Tokens: {self.manager.state.total_input_tokens:,} in / {self.manager.state.total_output_tokens:,} out", "done")
            except KeyboardInterrupt:
                log("Interrupted by user. Progress saved.", "warn")
                self.manager.save_checkpoint(completed_part_ids)
                raise
            except Exception as e:
                log(f"Error in Part {part_id}: {e}. Saving checkpoint and continuing.", "warn")
                self.manager.failed_part_ids.append(part_id)
                self.manager.save_checkpoint(completed_part_ids)

        report_body = self.manager.assemble_report_body()
        
        if 11 not in completed_part_ids:
            judgment_text, signal, confidence = self._final_judgment(report_body)
            self.manager.report_parts[11] = judgment_text
            completed_part_ids.append(11)
            self.manager.save_checkpoint(completed_part_ids)
        else:
            judgment_text = self.manager.report_parts.get(11, "")
            signal, confidence = self._parse_signal(judgment_text)

        full_report = self.manager.generate_final_report_text(report_body, judgment_text, signal, confidence)
        report_path = self.manager.save_report(full_report)
        self.manager.save_metadata(signal, confidence, report_path)
        
        log(f"Research complete! Time: {time.time() - start_time:.0f}s | Cost: ~${self.manager.estimate_cost():.2f}", "done")
        log(f"Report saved: {report_path}", "done")
        return str(report_path)
