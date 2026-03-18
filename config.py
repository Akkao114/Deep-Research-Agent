"""Centralized configuration for research-agent.

All tunable parameters are defined here so that changes only need to be made
in one place.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Directory Layout
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_DIR = PROJECT_ROOT / "data"
MODES_DIR = PROJECT_ROOT / "modes"

# ---------------------------------------------------------------------------
# Agent Limits
# ---------------------------------------------------------------------------

# Maximum number of tool calls the agent may make for a single Part
MAX_TOOL_CALLS_PER_PART = 30

# Maximum number of LLM round-trips per Part research loop
MAX_MESSAGES_PER_PART = 30

# ---------------------------------------------------------------------------
# Token / Truncation Limits
# ---------------------------------------------------------------------------

# Max characters of a single tool result stored in raw_data_chunks
TOOL_RESULT_RAW_CHARS = 3000

# Max characters of a single tool result sent back to the LLM
TOOL_RESULT_LLM_CHARS = 8000

# Max characters of raw_data fed into the extraction prompt
EXTRACTION_RAW_CHARS = 12000

# Max tokens for the research loop LLM calls
RESEARCH_MAX_TOKENS = 8000

# Max tokens for extraction calls
EXTRACTION_MAX_TOKENS = 4000

# Max tokens for writing calls
WRITING_MAX_TOKENS = 8000

# Max tokens for the final judgment (Opus) call
JUDGMENT_MAX_TOKENS = 8000

# Max characters of the full report passed to the final judgment prompt
JUDGMENT_REPORT_CHARS = 50000

# ---------------------------------------------------------------------------
# Cost Estimation (USD per 1M tokens)
# ---------------------------------------------------------------------------

# Blended average rates — update when model pricing changes
COST_PER_1M_INPUT_TOKENS = 4.0
COST_PER_1M_OUTPUT_TOKENS = 18.0

# ---------------------------------------------------------------------------
# HTTP / Scraping
# ---------------------------------------------------------------------------

import os
from dotenv import load_dotenv

env_path = Path.home() / ".agents" / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv() # Fallback to local .env

HTTP_USER_AGENT = os.environ.get("HTTP_USER_AGENT", (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
))

SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "ResearchAgent research@example.com")

# ---------------------------------------------------------------------------
# Mode Configuration
# ---------------------------------------------------------------------------

DEFAULT_MODE = "deep_research_review"
