# 🔬 Equity Deep Research Agent

An agentic equity research pipeline that **autonomously gathers data** via web search, yfinance, and SEC filings, then produces a **structured 11-part investment research report** with a final BUY / HOLD / SELL judgment.

## ✨ Features

- **Fully autonomous** — the agent iteratively calls 6 built-in tools to research each section
- **11-part report structure** — covering industry landscape, company fundamentals, financials, governance, valuation, and more
- **Preview mode** — Part 4 (Company Fundamentals) runs first for sanity check before the full research begins
- **Checkpoint & resume** — each completed part is saved to disk; interrupted runs can be seamlessly resumed
- **Configurable model tiers** — supports Gemini, Claude, or any OpenAI-compatible API via a pluggable model router
- **Pre-flight API check** — verifies all model endpoints before starting long runs
- **Anti-hallucination guardrails** — target-lock and anti-fabrication rules built into prompts

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Research Agent                         │
│                                                          │
│  ┌──────────┐   ┌───────────┐   ┌────────┐   ┌───────┐ │
│  │ Research  │──▶│ Extraction│──▶│ Writing│──▶│ Judge │ │
│  │   Loop    │   │  (low)    │   │ (high) │   │(high) │ │
│  │ (medium)  │   └───────────┘   └────────┘   └───────┘ │
│  └────┬──────┘                                           │
│       │                                                  │
│  ┌────▼──────────────────────────────────┐               │
│  │            6 Built-in Tools            │               │
│  │ web_search │ stock_info │ financials   │               │
│  │ sec_filings│ read_url   │ read_local   │               │
│  └───────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
```

### Report Structure (11 Parts)

| Part | Title | Key Content |
|:---:|---|---|
| 1 | Core Narrative | Industry changes, company response, market perception |
| 2 | Industry Landscape | Market size, competition landscape |
| 3 | Comparable Company Study | Peer selection, returns, business quality |
| 4 | **Company Fundamentals** ⭐ | Company intro, competitive advantages *(preview first)* |
| 5 | Financial Deep Dive | Revenue, margins, cash flow analysis |
| 6 | Capacity & CAPEX | Capital expenditure analysis |
| 7 | Governance & Returns | Management credibility, shareholder returns |
| 8 | Growth Drivers | Growth drivers across stages |
| 9 | Price Review | Stock price movement analysis |
| 10 | Valuation & Timing | Valuation methods, buy/sell points |
| 11 | Synthesis | **BUY / HOLD / SELL** judgment |

## 🚀 Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/luwtao/research-agent.git
cd research-agent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> The `model-router/` directory is included in the repo and installed in editable mode.

### 3. Set up environment variables

```bash
cp .env.example .env
# Edit .env with your actual API keys
```

**Required:**
| Variable | Description |
|---|---|
| `GOOGLE_API_KEY` | Google AI API key (for Gemini models) |
| `AIHUBMIX_API_KEY` | AIHUBMIX API key (proxy for Claude/Gemini) |

**Optional:**
| Variable | Description |
|---|---|
| `SEC_USER_AGENT` | SEC EDGAR identity (e.g. `YourName email@example.com`) |

### 4. Run

```bash
# Interactive mode
python main.py

# CLI mode
python main.py --mode deep AAPL
python main.py --mode deep 2698.HK
python main.py --mode deep "some company name"

# Resume after interruption (automatic)
python main.py --mode deep AAPL

# Force fresh start
python main.py --mode deep AAPL --no-resume
```

## ⚙️ Configuration

### Research Parameters (`config.py`)

| Variable | Default | Description |
|---|---|---|
| `MAX_TOOL_CALLS_PER_PART` | `30` | Max tool calls per research part |
| `MAX_MESSAGES_PER_PART` | `30` | Max LLM round-trips per part |
| `RESEARCH_MAX_TOKENS` | `8000` | Max tokens for research loop |
| `WRITING_MAX_TOKENS` | `8000` | Max tokens for report writing |
| `JUDGMENT_MAX_TOKENS` | `8000` | Max tokens for final judgment |

### Model Routing (`model-router/router_config.py`)

| Tier | Default Model | Usage |
|---|---|---|
| `high` | `gemini-3.1-pro-preview` | Report writing, final judgment |
| `medium` | `gemini-3.1-pro-preview` | Research loop (tool-calling) |
| `low` | `gemini-3-flash-preview` | Data extraction |

To switch to Claude, uncomment the backup `MODEL_MAP` block in `router_config.py`.

## 📁 Project Structure

```
research-agent/
├── main.py                 # CLI entry point & target resolution
├── agent.py                # Core agentic loop
├── config.py               # Centralized configuration
├── prompts.py              # Prompt templates & part definitions
├── schemas.py              # Pydantic data models
├── state.py                # Checkpoint & report management
├── tools.py                # 6 research tools + dispatcher
├── utils.py                # Logging & message formatting
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── modes/
│   └── deep_research_review.md  # Research framework (customizable)
├── model-router/           # Pluggable model routing layer
│   ├── router.py
│   ├── router_config.py
│   └── setup.py
├── reports/                # Generated reports (gitignored)
└── data/                   # Checkpoints (gitignored)
```

## 🔧 Customization

### Research Framework
Edit `modes/deep_research_review.md` to customize:
- Add, remove, or reorder research parts
- Change the industry focus or constraints
- Modify language or objectivity rules

Changes take effect immediately — no code modifications needed.

### Adding New Tools
Add tool definitions to `TOOL_DEFINITIONS` in `tools.py` and implement the corresponding function. Register it in `TOOL_DISPATCH`.

## 📄 Output

Reports are saved as Markdown + JSON metadata:
```
reports/AAPL_2026-03-18.md     # Full research report
reports/AAPL_2026-03-18.json   # Signal, cost, models used
```

## ⚠️ Disclaimer

This tool is for **research and educational purposes only**. It does not constitute investment advice. The AI-generated analysis may contain errors or hallucinations despite built-in guardrails. Always verify findings with primary sources before making any investment decisions.

## 📜 License

MIT
