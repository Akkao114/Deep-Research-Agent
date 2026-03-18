"""Centralized configuration for model-router.

All tunable parameters are defined here so that changes only need to be made
in one place.
"""

# ---------------------------------------------------------------------------
# API Configuration
# ---------------------------------------------------------------------------

# Base URL for the Anthropic/OpenAI-compatible API endpoint
API_BASE_URL = "https://aihubmix.com/v1"

# Whether to test all API models before starting a long research task
ENABLE_PREFLIGHT_CHECK = True

# Fallback configuration (if primary model fails)
ENABLE_FALLBACK = True
FALLBACK_MODEL = {"model": "gemini-3-flash-preview", "provider": "openai"}

# ---------------------------------------------------------------------------
# Model Mapping (tier → model info)
# ---------------------------------------------------------------------------
# "provider" can be "anthropic" or "openai"

# ===== Active: Gemini =====
MODEL_MAP = {
    "high": {"model": "gemini-3.1-pro-preview", "provider": "openai"},
    "medium": {"model": "gemini-3.1-pro-preview", "provider": "openai"},
    "low": {"model": "gemini-3-flash-preview", "provider": "openai"},
}

# ===== Backup: Claude (uncomment to switch back) =====
# MODEL_MAP = {
#     "high": {"model": "claude-opus-4-6", "provider": "anthropic"},
#     "medium": {"model": "claude-sonnet-4-6", "provider": "anthropic"},
#     "low": {"model": "gemini-3-flash-preview", "provider": "openai"},
# }

# Model used for the initial complexity classification call
CLASSIFY_MODEL = {"model": "gemini-3-flash-preview", "provider": "openai"}

# Human-readable labels for each tier (used in logging / display)
TIER_LABELS = {
    "high": "Gemini 3.1 Pro",
    "medium": "Gemini 3.1 Pro",
    "low": "Gemini 3 Flash",
}

# ---------------------------------------------------------------------------
# Classification Prompt
# ---------------------------------------------------------------------------

CLASSIFY_PROMPT = (
    "Classify this task's complexity as exactly one of: high, medium, low.\n"
    "- high: architecture design, complex reasoning, multi-step planning\n"
    "- medium: coding, debugging, moderate analysis\n"
    "- low: simple Q&A, classification, extraction, translation\n"
    "Respond with only the word."
)

# ---------------------------------------------------------------------------
# Default Parameters
# ---------------------------------------------------------------------------

DEFAULT_MAX_TOKENS = 4096
CLASSIFY_MAX_TOKENS = 10

