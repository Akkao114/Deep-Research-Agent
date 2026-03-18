"""CLI entry point for the equity research agent."""

from __future__ import annotations

import argparse
import sys

from schemas import ResearchTarget
from agent import ResearchAgent


MODE_MAP = {
    "deep": "deep_research_review",
    "review": "history_review",
}


def resolve_target(raw_input: str) -> ResearchTarget:
    """Determine if input is a ticker or keyword, and resolve accordingly."""
    raw = raw_input.strip().upper()

    # Heuristics for ticker detection:
    # - All caps, 1-5 chars, possibly with .SS / .HK suffix
    # - Contains digits + dot (e.g. 600519.SS, 0700.HK)
    import re
    ticker_pattern = re.compile(r"^[A-Z]{1,5}$|^\d{4,6}\.[A-Z]{1,2}$")

    if ticker_pattern.match(raw):
        # Likely a ticker — try to get company name via yfinance
        try:
            import yfinance as yf
            info = yf.Ticker(raw).info
            name = info.get("shortName") or info.get("longName")
            if name:
                return ResearchTarget(
                    raw_input=raw_input.strip(),
                    ticker=raw,
                    company_name=name,
                    is_listed=True,
                )
        except Exception:
            pass
        # Fallback: treat as ticker even without name resolution
        return ResearchTarget(
            raw_input=raw_input.strip(),
            ticker=raw,
            is_listed=True,
        )

    # Keyword / unlisted company
    return ResearchTarget(
        raw_input=raw_input.strip(),
        ticker=None,
        is_listed=False,
    )


def interactive_mode():
    """Interactive CLI: select mode and enter target."""
    print("\n=== Equity Research Agent ===\n")
    print("Available modes:")
    print("  1. Deep Research & Review  (全面深度研究)")
    print("  2. History Review          (历史研报回顾) [coming soon]")
    print()

    choice = input("Select mode [1]: ").strip() or "1"
    mode_key = {"1": "deep", "2": "review"}.get(choice, "deep")

    if mode_key == "review":
        print("History Review mode is not yet implemented.")
        sys.exit(0)

    target_input = input("Enter ticker or company name: ").strip()
    if not target_input:
        print("No input provided.")
        sys.exit(1)

    return mode_key, target_input


def main():
    parser = argparse.ArgumentParser(description="Equity Research Agent")
    parser.add_argument("--mode", "-m", choices=["deep", "review"], default=None,
                        help="Research mode: deep (Deep Research & Review), review (History Review)")
    parser.add_argument("target", nargs="?", default=None,
                        help="Ticker symbol (e.g. AAPL, 600519.SS) or company name/keyword")
    parser.add_argument("--no-resume", action="store_true",
                        help="Start fresh, ignoring any existing checkpoint")

    args = parser.parse_args()

    if args.mode and args.target:
        mode_key = args.mode
        target_input = args.target
    else:
        mode_key, target_input = interactive_mode()

    mode = MODE_MAP[mode_key]
    target = resolve_target(target_input)

    print(f"\nTarget: {target.raw_input}")
    if target.ticker:
        print(f"Ticker: {target.ticker}")
    if target.company_name:
        print(f"Company: {target.company_name}")
    print(f"Listed: {'Yes' if target.is_listed else 'No (keyword search mode)'}")
    print(f"Mode: {mode.replace('_', ' ').title()}")
    print(f"Resume: {'No (fresh start)' if args.no_resume else 'Yes (auto)'}")
    print()

    agent = ResearchAgent(target=target, mode=mode, resume=not args.no_resume)
    report_path = agent.run()

    if not report_path:
        print("\nResearch aborted by user.")
        sys.exit(0)

    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
