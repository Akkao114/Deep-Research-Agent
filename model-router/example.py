"""Usage examples for the multi-model router."""

from router import ModelRouter, RoutedResponse
from router_config import MODEL_MAP, TIER_LABELS


def print_result(label: str, prompt: str, response: RoutedResponse):
    tier = response.tier
    model = response.model
    # Extract text blocks
    text = response.content
    print(f"\n{'='*60}")
    print(f"[{label}]")
    print(f"  Prompt:  {prompt[:80]}...")
    print(f"  Tier:    {tier} → {TIER_LABELS[tier]} ({model})")
    print(f"  Tokens:  {response.input_tokens} in / {response.output_tokens} out")
    print(f"  Response (first 300 chars):\n    {text[:300]}")
    print(f"{'='*60}")


def main():
    import os
    if not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "sk-placeholder" # Prevent openai client crash if no key set, aihubmix typically requires ANTHROPIC_API_KEY for everything or a standard API_KEY
    if not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = "sk-placeholder"
    
    router = ModelRouter()

    # 1. Architecture question → should route to Opus
    p1 = "Design a scalable event-driven architecture for a real-time collaborative document editor supporting 10M concurrent users. Include data flow, consistency model, and failure handling."
    tier1 = router.classify(p1)
    print(f"\nClassified '{p1[:50]}...' as: {tier1}")
    r1 = router.route(p1)
    print_result("Architecture Design", p1, r1)

    # 2. Coding task → should route to Sonnet
    p2 = "Write a Python function that implements a trie data structure with insert, search, and prefix-match methods."
    tier2 = router.classify(p2)
    print(f"\nClassified '{p2[:50]}...' as: {tier2}")
    r2 = router.route(p2)
    print_result("Coding Task", p2, r2)


if __name__ == "__main__":
    main()
