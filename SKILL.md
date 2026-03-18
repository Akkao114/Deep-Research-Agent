---
name: Equity Deep Research Agent
description: Agentic equity research pipeline that autonomously gathers data via web search, yfinance, and SEC filings, then produces a structured 11-part investment research report with a final BUY/HOLD/SELL judgment
---

# Equity Deep Research Agent

## Overview
An agentic research pipeline that autonomously researches a company (listed or unlisted) and produces a comprehensive 11-part investment research report in Markdown format.

**Architecture:**
- **Phase 1 — Research Loop**: For each of the 11 report parts, an LLM agent iteratively calls 6 built-in tools (web search, stock info, financials, SEC filings, URL reader, local file reader) to collect raw data.
- **Phase 2 — Extraction**: A lightweight LLM distills raw data into a structured summary per part.
- **Phase 3 — Writing**: A high-tier LLM writes each report section from the extracted data.
- **Phase 4 — Judgment**: A high-tier LLM reads the full report and issues a BUY / HOLD / SELL signal with confidence %.

**Preview Mode**: Part 4 (Company Fundamentals) is executed first and shown to the user for confirmation before the full research begins. This acts as a sanity check to ensure the correct company is being researched.

**Key Features:**
- Checkpoint / resume support — each completed part is saved to disk; interrupted runs can be resumed
- Configurable model tiers via `model-router` (supports Gemini, Claude, or any OpenAI-compatible API)
- Pre-flight API connectivity check before long runs
- Anti-hallucination and target-lock guardrails in prompts

## Prerequisites

### 1. Environment Variables (Required)
Set the following in `~/.agents/.env` (or a local `.env` in the project directory):

```bash
# API key for the model provider (Gemini via Google AI, or AIHUBMIX proxy)
export GOOGLE_API_KEY="your-google-api-key"

# If using AIHUBMIX as a proxy for Claude/Gemini
export AIHUBMIX_API_KEY="your-aihubmix-api-key"

# (Optional) SEC EDGAR identity for US filings
export SEC_USER_AGENT="YourName your_email@example.com"
```

### 2. Python Dependencies
```bash
cd ~/.agents/skills/research-agent
pip install -r requirements.txt
```

> **Note:** `requirements.txt` includes `-e ../model-router`, which installs the shared `model-router` package in editable mode. Ensure `~/.agents/skills/model-router/` exists.

### 3. Model Router Configuration
Model selection is configured in `~/.agents/skills/model-router/router_config.py`:

| Setting | Default | Description |
|---|---|---|
| `MODEL_MAP["high"]` | `gemini-3.1-pro-preview` | Used for report writing & final judgment |
| `MODEL_MAP["medium"]` | `gemini-3.1-pro-preview` | Used for the research loop (tool-calling) |
| `MODEL_MAP["low"]` | `gemini-3-flash-preview` | Used for data extraction |
| `API_BASE_URL` | `https://aihubmix.com/v1` | API endpoint for all models |
| `ENABLE_PREFLIGHT_CHECK` | `True` | Test all models before starting |

To switch to Claude, uncomment the backup `MODEL_MAP` block in `router_config.py`.

## How to Run

### Interactive Mode
```bash
cd ~/.agents/skills/research-agent
python main.py
```
Prompts for:
1. **Mode** — Deep Research & Review (default) or History Review (coming soon)
2. **Target** — Ticker (e.g. `AAPL`, `0700.HK`, `600519.SS`) or company name/keyword

### CLI Mode
```bash
python main.py --mode deep AAPL
python main.py --mode deep 2698.HK
python main.py --mode deep "some unlisted company"
```

### Resume Mode (after interruption)
Checkpoints are saved automatically after each part. Simply re-run the same command — completed parts will be skipped:
```bash
python main.py --mode deep 2698.HK
```
To force a fresh start:
```bash
python main.py --mode deep 2698.HK --no-resume
```

## Output
Reports and metadata are saved to:
```
research-agent/reports/<TICKER>_<DATE>.md    # Full Markdown report
research-agent/reports/<TICKER>_<DATE>.json  # Structured metadata (signal, cost, models used)
research-agent/data/checkpoint_<TICKER>_<DATE>.json  # Checkpoint for resume
```

## Report Structure (11 Parts)
| Part | Title | Key Content |
|---|---|---|
| 1 | Core Narrative | Industry changes, company response, interaction, market perception, peer lessons |
| 2 | Industry Landscape | Market size, competition landscape |
| 3 | Comparable Company Study | Peer selection, long-term returns, business quality, historical review |
| 4 | Company Fundamentals ⭐ | Company intro, competitive advantages, market share *(preview first)* |
| 5 | Financial Deep Dive | Revenue/profit trends, business mix, clients/suppliers, volume-price-profit drivers, cash flow |
| 6 | Capacity & CAPEX | Capacity analysis, capital expenditure |
| 7 | Governance & Returns | Management credibility, shareholder returns |
| 8 | Growth Drivers | Growth drivers across stages |
| 9 | Price Review | Key contradictions, price movement drivers |
| 10 | Valuation & Timing | Valuation methods, historical ranges, buy/sell points |
| 11 | Synthesis | Final BUY/HOLD/SELL judgment, key risks, assumptions |

## Configuration
All research parameters are in `config.py`:

| Variable | Default | Description |
|---|---|---|
| `MAX_TOOL_CALLS_PER_PART` | `30` | Max tool calls per research part |
| `MAX_MESSAGES_PER_PART` | `30` | Max LLM round-trips per part |
| `TOOL_RESULT_RAW_CHARS` | `3000` | Max chars stored per tool result |
| `TOOL_RESULT_LLM_CHARS` | `8000` | Max chars sent back to LLM per tool result |
| `RESEARCH_MAX_TOKENS` | `8000` | Max tokens for research loop calls |
| `WRITING_MAX_TOKENS` | `8000` | Max tokens for report writing calls |
| `JUDGMENT_MAX_TOKENS` | `8000` | Max tokens for final judgment call |

## Available Tools
The agent has access to 6 built-in tools:

| Tool | Description |
|---|---|
| `web_search` | DuckDuckGo web search (supports EN & CN queries) |
| `get_stock_info` | Stock info via yfinance (price, PE, PB, margins, etc.) |
| `get_financials` | Financial statements via yfinance (income, balance, cashflow) |
| `get_sec_filings` | SEC EDGAR filings for US-listed companies |
| `read_url` | Fetch & extract text from any web URL |
| `read_local_file` | Read local files (PDF, Markdown, text) |

## File Structure
```
research-agent/
├── SKILL.md                # This file
├── main.py                 # CLI entry point & target resolution
├── agent.py                # Core agentic loop (research → extract → write → judge)
├── config.py               # Centralized configuration
├── prompts.py              # All prompt templates & part definitions
├── schemas.py              # Pydantic data models
├── state.py                # Checkpoint & report management
├── tools.py                # 6 research tools + dispatcher
├── utils.py                # Logging & message formatting
├── requirements.txt        # Python dependencies
├── modes/                  # Research mode configurations
│   └── deep_research_review.md  # Default mode: 11-part deep research framework
├── reports/                # Generated reports (Markdown + JSON)
└── data/                   # Checkpoints for resume
```

## Customizing Research Modes
Edit `modes/deep_research_review.md` to:
- Change the research framework (add/remove/reorder parts)
- Adjust the industry focus (currently set for Mining & Metal, but works for any sector)
- Modify constraints (e.g., language, data sources, objectivity rules)

The mode file is loaded at runtime — changes take effect immediately without code modifications.

## Troubleshooting

| Issue | Solution |
|---|---|
| `API key not set` | Set `GOOGLE_API_KEY` or `AIHUBMIX_API_KEY` in `~/.agents/.env` |
| Pre-flight check fails | Verify API keys and `API_BASE_URL` in `router_config.py` |
| Wrong company researched | Check yfinance ticker resolution; use `--no-resume` to start fresh |
| Checkpoint not loading | Ensure the checkpoint date matches today; delete old checkpoints if needed |
| `ModuleNotFoundError: router` | Install model-router: `pip install -e ~/.agents/skills/model-router` |
| Report sections missing | Check `failed_part_ids` in the checkpoint JSON for error details |
