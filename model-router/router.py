"""Multi-model router that dispatches tasks to Claude/OpenAI based on complexity."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic
import openai
from dotenv import load_dotenv

from router_config import (
    API_BASE_URL,
    CLASSIFY_MAX_TOKENS,
    CLASSIFY_MODEL,
    CLASSIFY_PROMPT,
    MODEL_MAP,
    TIER_LABELS,
)


@dataclass
class RoutedResponse:
    """Standardized response format across all providers."""
    content: str
    model: str
    tier: str
    input_tokens: int
    output_tokens: int
    tool_calls: list[dict] | None = None
    raw_response: Any = None


class ModelRouter:
    """Routes prompts to the appropriate model based on task complexity."""

    def __init__(self, anthropic_client: anthropic.Anthropic | None = None, openai_client: openai.OpenAI | None = None):
        # Automatically load global .env from ~/.agents/.env or current directory
        env_path = Path.home() / ".agents" / ".env"
        load_dotenv(dotenv_path=env_path)
        load_dotenv() # Fallback to local .env if it exists

        base_url = os.environ.get("API_BASE_URL", API_BASE_URL)
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY", anthropic_key)
        gemini_key = os.environ.get("GEMINI_API_KEY")

        # Anthropic SDK automatically appends /v1/messages to the base URL, 
        # so we need to strip /v1 if the proxy base_url includes it.
        anthropic_base_url = base_url
        if anthropic_base_url.endswith("/v1"):
            anthropic_base_url = anthropic_base_url[:-3]
        elif anthropic_base_url.endswith("/v1/"):
            anthropic_base_url = anthropic_base_url[:-4]

        self.anthropic_client = anthropic_client or anthropic.Anthropic(base_url=anthropic_base_url)
        # For OpenAI client (AIHUBMIX proxy), we also need an API key, we fallback to OPENAI_API_KEY
        self.openai_client = openai_client or openai.OpenAI(base_url=base_url, api_key=openai_key)
        
        # Dedicated client for Gemini straight API via OpenAI compatibility layer
        if gemini_key:
            self.gemini_client = openai.OpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/", 
                api_key=gemini_key
            )
        else:
            self.gemini_client = self.openai_client  # Fallback to general base_url if no dedicated key

    def preflight_check(self, tiers: list[str] | None = None) -> dict[str, str]:
        """Verify all models can be called before starting expensive work.

        Args:
            tiers: Which tiers to test. Defaults to all tiers in MODEL_MAP.

        Returns:
            Dict of {tier: model_name} for each successfully verified model.

        Raises:
            RuntimeError: If any model fails to respond, with a descriptive error.
        """
        from router_config import TIER_LABELS
        tiers_to_check = tiers or list(MODEL_MAP.keys())
        
        # Deduplicate: only test each unique (model, provider) pair once
        seen: dict[tuple[str, str], str] = {}  # (model, provider) -> first_tier
        for tier in tiers_to_check:
            info = MODEL_MAP.get(tier)
            if info:
                key = (info["model"], info["provider"])
                if key not in seen:
                    seen[key] = tier

        print(f"\n🔍 Pre-flight API check ({len(seen)} unique model(s))...")
        verified: dict[str, str] = {}
        failed: list[str] = []

        for (model_name, provider), tier in seen.items():
            label = TIER_LABELS.get(tier, tier)
            try:
                probe = "Reply with one word: ok"
                if provider == "anthropic":
                    resp = self.anthropic_client.messages.create(
                        model=model_name,
                        max_tokens=5,
                        messages=[{"role": "user", "content": probe}],
                    )
                    _ = resp.content[0].text
                else:
                    client = self.gemini_client if "gemini" in model_name.lower() else self.openai_client
                    resp = client.chat.completions.create(
                        model=model_name,
                        max_tokens=5,
                        messages=[{"role": "user", "content": probe}],
                    )
                    _ = resp.choices[0].message.content
                print(f"  ✅ {label} ({model_name}) — OK")
                verified[tier] = model_name
            except Exception as e:
                err_summary = str(e)[:120]
                print(f"  ❌ {label} ({model_name}) — FAILED: {err_summary}")
                failed.append(f"[{label}] {model_name}: {err_summary}")

        if failed:
            raise RuntimeError(
                "Pre-flight check failed. Fix the following before running:\n"
                + "\n".join(failed)
            )

        print("✅ All models verified. Starting research...\n")
        return verified

    def _convert_tools_to_openai(self, tools: list[dict]) -> list[dict]:
        """Convert Anthropic tool format to OpenAI format."""
        openai_tools = []
        for t in tools:
            # Check if already OpenAI format
            if "type" in t and t["type"] == "function":
                openai_tools.append(t)
                continue
                
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t.get("name", ""),
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}})
                }
            })
        return openai_tools

    def classify(self, prompt: str) -> str:
        """Use the classification model to determine complexity tier."""
        model_info = CLASSIFY_MODEL
        model_name = model_info["model"]
        provider = model_info["provider"]

        try:
            if provider == "anthropic":
                response = self.anthropic_client.messages.create(
                    model=model_name,
                    max_tokens=CLASSIFY_MAX_TOKENS,
                    messages=[{"role": "user", "content": f"{CLASSIFY_PROMPT}\n\nTask: {prompt}"}],
                )
                tier = response.content[0].text.strip().lower()
            else: # openai / gemini
                client = self.gemini_client if "gemini" in model_name.lower() else self.openai_client
                response = client.chat.completions.create(
                    model=model_name,
                    max_tokens=CLASSIFY_MAX_TOKENS,
                    messages=[{"role": "user", "content": f"{CLASSIFY_PROMPT}\n\nTask: {prompt}"}],
                )
                tier = response.choices[0].message.content.strip().lower()
        except (anthropic.AuthenticationError, openai.AuthenticationError) as e:
            from router_config import ENABLE_FALLBACK, FALLBACK_MODEL
            if ENABLE_FALLBACK and model_name != FALLBACK_MODEL["model"]:
                print(f"⚠️  [Router] Aihubmix/Auth Error: {e}. Falling back to Gemini...")
                # Call again with the fallback model
                fb_model = FALLBACK_MODEL["model"]
                response = self.gemini_client.chat.completions.create(
                    model=fb_model,
                    max_tokens=CLASSIFY_MAX_TOKENS,
                    messages=[{"role": "user", "content": f"{CLASSIFY_PROMPT}\n\nTask: {prompt}"}],
                )
                tier = response.choices[0].message.content.strip().lower()
            else:
                raise e

        if tier not in MODEL_MAP:
            tier = "medium"  # default fallback
        return tier

    def route_raw(
        self,
        *,
        model_tier: str,
        messages: list[dict],
        max_tokens: int = 16000,
        system: str | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> RoutedResponse:
        """Send a full messages list (with optional tools) to a specific model tier."""
        model_override = kwargs.pop("model_override", None)
        
        if model_override:
            model_name = model_override
            provider = "openai" # Gemini always uses openai-compat via native gateway for fallback
        else:
            model_info = MODEL_MAP.get(model_tier, MODEL_MAP["medium"])
            model_name = model_info["model"]
            provider = model_info["provider"]

        try:
            if provider == "anthropic":
                create_params: dict = {
                    "model": model_name,
                    "max_tokens": max_tokens,
                    "messages": messages,
                    **kwargs,
                }
                if system:
                    create_params["system"] = system
                if tools:
                    create_params["tools"] = tools
                
                # Adaptive thinking for Opus/Sonnet
                if model_tier != "low" and "claude" in model_name:
                    create_params["thinking"] = {"type": "adaptive"}

                raw_resp = self.anthropic_client.messages.create(**create_params)
                
                # Extract content and tool calls
                content_text = ""
                tool_calls = []
                for block in raw_resp.content:
                    if block.type == "text":
                        content_text += block.text
                    elif block.type == "tool_use":
                        tool_calls.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input
                        })
                
                return RoutedResponse(
                    content=content_text,
                    model=raw_resp.model,
                    tier=model_tier,
                    input_tokens=raw_resp.usage.input_tokens,
                    output_tokens=raw_resp.usage.output_tokens,
                    tool_calls=tool_calls if tool_calls else None,
                    raw_response=raw_resp
                )

            else: # openai / generic proxy
                # For OpenAI, system prompt is just a message at the start
                openai_messages = []
                if system:
                    openai_messages.append({"role": "system", "content": system})
                openai_messages.extend(messages)
                
                create_params: dict = {
                    "model": model_name,
                    "max_tokens": max_tokens,
                    "messages": openai_messages,
                    **kwargs,
                }
                if tools:
                    create_params["tools"] = self._convert_tools_to_openai(tools)

                client = self.gemini_client if "gemini" in model_name.lower() else self.openai_client
                raw_resp = client.chat.completions.create(**create_params)
                choice = raw_resp.choices[0]
                msg = choice.message
                
                tool_calls = []
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        if tc.type == "function":
                            tool_calls.append({
                                "id": tc.id,
                                "name": tc.function.name,
                                "input": json.loads(tc.function.arguments)
                            })

                return RoutedResponse(
                    content=msg.content or "",
                    model=raw_resp.model,
                    tier=model_tier,
                    input_tokens=getattr(raw_resp.usage, 'prompt_tokens', 0) or 0,
                    output_tokens=getattr(raw_resp.usage, 'completion_tokens', 0) or 0,
                    tool_calls=tool_calls if tool_calls else None,
                    raw_response=raw_resp
                )
        except (anthropic.AuthenticationError, openai.AuthenticationError) as e:
            from router_config import ENABLE_FALLBACK, FALLBACK_MODEL
            if ENABLE_FALLBACK and model_name != FALLBACK_MODEL["model"]:
                print(f"⚠️  [Router] Aihubmix funds exhausted or auth error. Falling back to Gemini ({FALLBACK_MODEL['model']})...")
                # Retry with fallback model (always using Gemini client/OpenAI protocol)
                return self.route_raw(
                    model_tier="low", # Force low tier characteristics or we can pass a custom model
                    messages=messages,
                    max_tokens=max_tokens,
                    system=system,
                    tools=tools,
                    **{**kwargs, "model_override": FALLBACK_MODEL["model"]} # Internal flag to override
                )
            raise e

    def route(
        self,
        prompt: str,
        *,
        model_tier: str | None = None,
        max_tokens: int = 4096,
        system: str | None = None,
        **kwargs,
    ) -> RoutedResponse:
        """Classify the prompt and dispatch to the appropriate model."""
        tier = model_tier if model_tier in MODEL_MAP else self.classify(prompt)
        return self.route_raw(
            model_tier=tier, 
            messages=[{"role": "user", "content": prompt}], 
            max_tokens=max_tokens, 
            system=system, 
            **kwargs
        )
