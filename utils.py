"""Utility functions for Research Agent."""

from typing import Any


def log(msg: str, style: str = "info"):
    """Simple colored console logging."""
    colors = {"info": "\033[36m", "tool": "\033[33m", "done": "\033[32m", "warn": "\033[31m"}
    reset = "\033[0m"
    prefix = colors.get(style, "")
    print(f"{prefix}[{style.upper()}]{reset} {msg}")


def serialize_assistant_message(routed_response: Any) -> dict:
    """Format the raw API response for inclusion in the conversation history."""
    raw = routed_response.raw_response
    if hasattr(raw, "choices"):
        # OpenAI format
        msg = raw.choices[0].message
        return msg.model_dump(exclude_unset=True)
    else:
        # Anthropic format
        result = []
        for block in raw.content:
            if hasattr(block, "model_dump"):
                result.append(block.model_dump())
            else:
                result.append(block)
        return {"role": "assistant", "content": result}


def format_tool_results_message(tool_results: list[dict], is_openai: bool) -> dict | list[dict]:
    """Format tool results back to the model based on provider format."""
    if is_openai:
        # OpenAI expects each tool result as a separate message with role "tool"
        messages = []
        for tr in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": tr["tool_use_id"],
                "content": str(tr["content"])
            })
        return messages
    else:
        # Anthropic expects a single message with role "user" and a list of tool_result blocks
        blocks = []
        for tr in tool_results:
            blocks.append({
                "type": "tool_result",
                "tool_use_id": tr["tool_use_id"],
                "content": str(tr["content"])
            })
        return {"role": "user", "content": blocks}
