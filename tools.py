"""6 research tools + Claude API tool definitions."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from config import HTTP_USER_AGENT, SEC_USER_AGENT

# ---------------------------------------------------------------------------
# Tool definitions for Claude API (function-calling schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": "Search the web via DuckDuckGo for news, analyst opinions, industry reports, etc. Returns top results with titles, URLs and snippets. Supports English and Chinese queries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (use English for global data, Chinese for A-share / HK specific data)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 8)",
                    "default": 8,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_stock_info",
        "description": "Get basic stock info: price, market cap, PE, PB, sector, industry, beta, 52-week range, dividend yield, etc. Works for listed companies only.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g. AAPL, 600519.SS, 0700.HK)",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_financials",
        "description": "Get financial statements (income statement, balance sheet, cash flow) for a listed company. Returns annual data by default.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol",
                },
                "statement": {
                    "type": "string",
                    "enum": ["income", "balance", "cashflow"],
                    "description": "Which financial statement to retrieve",
                },
                "quarterly": {
                    "type": "boolean",
                    "description": "If true, return quarterly data instead of annual",
                    "default": False,
                },
            },
            "required": ["ticker", "statement"],
        },
    },
    {
        "name": "get_sec_filings",
        "description": "Get recent SEC EDGAR filings (10-K, 10-Q, 8-K, etc.) for a US-listed company. Returns filing type, date, and URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "US stock ticker symbol (e.g. AAPL)",
                },
                "filing_type": {
                    "type": "string",
                    "description": "Filing type filter (e.g. '10-K', '10-Q'). Leave empty for all types.",
                    "default": "",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of filings to return (default 10)",
                    "default": 10,
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "read_url",
        "description": "Fetch and extract main text content from a web URL. Use this to read news articles, SEC filings, analyst reports, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL to fetch",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Max characters to return (default 15000)",
                    "default": 15000,
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "read_local_file",
        "description": "Read a local file (PDF, markdown, text). Use this to read previous research reports or local documents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the local file (absolute or relative to project root)",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Max characters to return (default 15000)",
                    "default": 15000,
                },
            },
            "required": ["file_path"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": HTTP_USER_AGENT
}


def web_search(query: str, max_results: int = 8) -> str:
    """Search via DuckDuckGo using the ddgs library."""
    try:
        from ddgs import DDGS
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "No results found."
        
        formatted_results = []
        for i, r in enumerate(results):
            title = r.get('title', '')
            link = r.get('href', '')
            snippet = r.get('body', '')
            if title or link:
                formatted_results.append(f"[{i+1}] {title}\n    URL: {link}\n    {snippet}")
        
        return "\n\n".join(formatted_results) if formatted_results else "No results found."
    except Exception as e:
        return f"Search error: {e}"


def get_stock_info(ticker: str) -> str:
    """Get basic stock info via yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info
        if not info or "shortName" not in info:
            return f"No data found for ticker: {ticker}"
        fields = [
            "shortName", "symbol", "exchange", "currency", "sector", "industry",
            "marketCap", "enterpriseValue",
            "currentPrice", "previousClose", "fiftyTwoWeekLow", "fiftyTwoWeekHigh",
            "trailingPE", "forwardPE", "priceToBook", "priceToSalesTrailing12Months",
            "trailingEps", "forwardEps",
            "dividendYield", "payoutRatio",
            "beta", "returnOnEquity", "returnOnAssets",
            "revenueGrowth", "earningsGrowth",
            "totalRevenue", "grossMargins", "operatingMargins", "profitMargins",
            "totalCash", "totalDebt", "debtToEquity",
            "freeCashflow", "operatingCashflow",
            "fullTimeEmployees",
        ]
        lines = []
        for f in fields:
            v = info.get(f)
            if v is not None:
                lines.append(f"{f}: {v}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error fetching stock info: {e}"


def get_financials(ticker: str, statement: str = "income", quarterly: bool = False) -> str:
    """Get financial statements via yfinance."""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        stmt_map = {
            "income": (t.quarterly_income_stmt if quarterly else t.income_stmt),
            "balance": (t.quarterly_balance_sheet if quarterly else t.balance_sheet),
            "cashflow": (t.quarterly_cashflow if quarterly else t.cashflow),
        }
        df = stmt_map.get(statement)
        if df is None or df.empty:
            return f"No {statement} statement data for {ticker}"
        return df.to_string()
    except Exception as e:
        return f"Error fetching financials: {e}"


def get_sec_filings(ticker: str, filing_type: str = "", count: int = 10) -> str:
    """Get SEC EDGAR filings list."""
    try:
        headers = {
            "User-Agent": SEC_USER_AGENT,
            "Accept": "application/json",
        }
        # Use the company tickers endpoint to resolve CIK
        tickers_url = "https://www.sec.gov/files/company_tickers.json"
        resp = requests.get(tickers_url, headers=headers, timeout=10)
        resp.raise_for_status()
        tickers_data = resp.json()

        cik = None
        for entry in tickers_data.values():
            if entry.get("ticker", "").upper() == ticker.upper():
                cik = str(entry["cik_str"]).zfill(10)
                break

        if not cik:
            return f"Could not find CIK for ticker: {ticker}"

        # Get filings
        filings_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        resp = requests.get(filings_url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        descriptions = recent.get("primaryDocDescription", [])
        docs = recent.get("primaryDocument", [])

        results = []
        for i in range(min(len(forms), 100)):
            if filing_type and forms[i] != filing_type:
                continue
            acc_clean = accessions[i].replace("-", "")
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{acc_clean}/{docs[i]}" if i < len(docs) else ""
            results.append(
                f"[{len(results)+1}] {forms[i]} | {dates[i]} | {descriptions[i] if i < len(descriptions) else ''}\n    URL: {doc_url}"
            )
            if len(results) >= count:
                break

        return "\n\n".join(results) if results else f"No filings found for {ticker}"
    except Exception as e:
        return f"Error fetching SEC filings: {e}"


def read_url(url: str, max_chars: int = 15000) -> str:
    """Fetch and extract text content from a URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove script/style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:max_chars]
    except Exception as e:
        return f"Error reading URL: {e}"


def read_local_file(file_path: str, max_chars: int = 15000) -> str:
    """Read a local file (PDF, markdown, text)."""
    path = Path(file_path).expanduser()
    if not path.exists():
        # Try relative to project
        alt = Path(__file__).parent / file_path
        if alt.exists():
            path = alt
        else:
            return f"File not found: {file_path}"

    try:
        if path.suffix.lower() == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(path))
                text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
                return text[:max_chars]
            except ImportError:
                return "pypdf not installed. Run: pip install pypdf"
        else:
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except Exception as e:
        return f"Error reading file: {e}"


# ---------------------------------------------------------------------------
# Dispatcher: name → function
# ---------------------------------------------------------------------------

TOOL_DISPATCH = {
    "web_search": web_search,
    "get_stock_info": get_stock_info,
    "get_financials": get_financials,
    "get_sec_filings": get_sec_filings,
    "read_url": read_url,
    "read_local_file": read_local_file,
}


def execute_tool(name: str, args: dict) -> str:
    """Execute a tool by name with given arguments. Returns string result."""
    fn = TOOL_DISPATCH.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    try:
        return fn(**args)
    except Exception as e:
        return f"Tool execution error ({name}): {e}"
