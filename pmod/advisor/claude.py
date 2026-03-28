"""Claude AI advisor — contextual finance Q&A that feeds back into portfolio strategy.

Uses the local ``claude`` CLI (Claude Code) so no separate ANTHROPIC_API_KEY
is needed — it reuses whatever OAuth credentials the CLI already has.
Falls back to the Anthropic SDK (ANTHROPIC_API_KEY) if the CLI is not on PATH.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

import structlog

log = structlog.get_logger()

# Valid values accepted by the DB / preferences system
_VALID_RISK = {"low", "medium", "high", "degen"}
_VALID_STRATEGY = {"growth", "value", "dividend", "momentum", "balanced"}

_SYSTEM_PROMPT = """\
You are an expert financial advisor embedded in a personal portfolio management tool called
PrintMoneyOrDie.  The user will share their current portfolio, risk profile, and watchlist
before asking a question.  Give clear, direct, actionable analysis.

When you have concrete recommendations — specific tickers to watch, or a suggested change to
risk tolerance or investment strategy — include them in a structured block at the very end of
your response using this exact format:

<actions>
{
  "add_to_watchlist": [
    {"ticker": "NVDA", "reason": "One-sentence rationale"}
  ],
  "risk_tolerance": null,
  "strategy": null
}
</actions>

Rules:
- Only populate a field when you have a definite recommendation; otherwise leave it null.
- "add_to_watchlist" may contain 0–5 items; tickers must be valid US equity symbols.
- Valid risk_tolerance values: "low", "medium", "high", "degen"
- Valid strategy values: "growth", "value", "dividend", "momentum", "balanced"
- The <actions> block must always be present, even if all fields are null.
- Do NOT explain the JSON — just emit it.
"""

_EMPTY_ACTIONS: dict = {"add_to_watchlist": [], "risk_tolerance": None, "strategy": None}


def _cli_env() -> dict:
    """Return a subprocess environment safe for the ``claude`` CLI.

    When pmod runs inside Claude Code / Claude Desktop the host injects
    ``ANTHROPIC_API_KEY=""`` (empty string).  The CLI sees that, treats it as
    "API key provided but blank", and exits 1.  We strip it so the CLI falls
    back to its own stored OAuth credentials.
    """
    env = dict(os.environ)
    if not env.get("ANTHROPIC_API_KEY", "").strip():
        env.pop("ANTHROPIC_API_KEY", None)
    return env


def _ask_via_cli(user_message: str) -> str:
    """Call the local ``claude`` CLI and return its stdout.

    - Passes the prompt via stdin to avoid shell argument-length limits.
    - Strips empty ANTHROPIC_API_KEY so the CLI uses its OAuth credentials.
    - Sets cwd to $HOME so the repo's CLAUDE.md is not auto-discovered.
    """
    result = subprocess.run(
        [
            "claude",
            "--print",
            "--system-prompt", _SYSTEM_PROMPT,
            "--output-format", "text",
        ],
        input=user_message,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=os.path.expanduser("~"),
        env=_cli_env(),
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "(no stderr)"
        raise RuntimeError(f"claude CLI exited {result.returncode}: {stderr[:300]}")
    return result.stdout.strip()


def _ask_via_sdk(user_message: str) -> str:
    """Fallback: Anthropic SDK with ANTHROPIC_API_KEY from .env."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set.  Add it to your .env file, "
            "or run pmod inside Claude Code (which supplies its own auth)."
        )
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def _build_context(portfolio_context: dict) -> str:
    """Render portfolio_context as a readable summary."""
    lines: list[str] = []

    prefs = portfolio_context.get("preferences", {})
    if prefs:
        lines.append(f"Risk tolerance : {prefs.get('risk_tolerance', 'medium')}")
        lines.append(f"Strategy       : {prefs.get('strategy', 'balanced')}")
        lines.append(f"Max position   : {prefs.get('max_position_pct', 5.0)}% per ticker")

    positions = portfolio_context.get("positions", [])
    if positions:
        lines.append("\nCurrent positions:")
        for p in positions:
            lines.append(
                f"  {p['ticker']:<6}  {p.get('shares', 0)} shares  "
                f"@ ${p.get('current_price', 0):,.2f}  "
                f"= ${p.get('market_value', 0):,.0f}  "
                f"({p.get('weight', 0):.1f}% of portfolio)"
            )
        lines.append(f"  Total value : ${portfolio_context.get('total_value', 0):,.0f}")
        lines.append(f"  Cash        : ${portfolio_context.get('cash_balance', 0):,.0f}")
    else:
        lines.append("\nNo live portfolio data (Schwab not connected).")

    watchlist = portfolio_context.get("watchlist", [])
    if watchlist:
        lines.append(f"\nWatchlist: {', '.join(watchlist)}")

    return "\n".join(lines)


def _parse_actions(raw: str) -> dict:
    """Extract and validate the <actions> JSON block from Claude's response."""
    match = re.search(r"<actions>\s*(\{.*?\})\s*</actions>", raw, re.DOTALL)
    if not match:
        return dict(_EMPTY_ACTIONS)

    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        log.warning("advisor_actions_parse_error", raw=match.group(1)[:200])
        return dict(_EMPTY_ACTIONS)

    watchlist_raw = parsed.get("add_to_watchlist") or []
    watchlist = [
        item for item in watchlist_raw
        if isinstance(item, dict) and re.fullmatch(r"[A-Z]{1,5}", item.get("ticker", ""))
    ]
    risk = parsed.get("risk_tolerance")
    strategy = parsed.get("strategy")

    return {
        "add_to_watchlist": watchlist,
        "risk_tolerance": risk if risk in _VALID_RISK else None,
        "strategy": strategy if strategy in _VALID_STRATEGY else None,
    }


def _get_portfolio_context() -> dict:
    """Build live portfolio context from Schwab + user preferences."""
    context: dict = {}

    try:
        from pmod.broker.schwab import get_account_summary
        summary = get_account_summary()
        if summary:
            context["total_value"] = summary.total_value
            context["cash_balance"] = summary.cash_balance
            context["positions"] = [
                {
                    "ticker": p.ticker,
                    "shares": p.shares,
                    "current_price": p.current_price,
                    "market_value": p.market_value,
                    "weight": p.weight,
                }
                for p in summary.positions
            ]
    except Exception as exc:
        log.warning("advisor_portfolio_fetch_failed", error=str(exc))

    try:
        from pmod.preferences.profile import load_preferences_dict
        context["preferences"] = load_preferences_dict()
    except Exception as exc:
        log.warning("advisor_prefs_fetch_failed", error=str(exc))

    try:
        from pmod.data.models import WatchlistItem, get_session
        with get_session() as session:
            items = session.query(WatchlistItem).all()
            context["watchlist"] = [item.ticker for item in items]
    except Exception as exc:
        log.warning("advisor_watchlist_fetch_failed", error=str(exc))

    return context


def ask_claude(question: str) -> tuple[str, dict]:
    """Ask Claude a finance question with full portfolio context.

    Tries the local ``claude`` CLI first (uses its own stored OAuth auth),
    then falls back to the Anthropic SDK if the CLI is unavailable.

    Returns:
        (display_text, actions) where actions is a dict with keys:
            add_to_watchlist  — list of {ticker, reason} dicts
            risk_tolerance    — new risk level string, or None
            strategy          — new strategy string, or None
    """
    portfolio_context = _get_portfolio_context()
    context_block = _build_context(portfolio_context)
    user_message = f"Portfolio context:\n{context_block}\n\nQuestion: {question}"

    raw = ""
    try:
        raw = _ask_via_cli(user_message)
        log.info("advisor_used_cli")
    except FileNotFoundError:
        log.info("advisor_cli_not_found_trying_sdk")
        try:
            raw = _ask_via_sdk(user_message)
            log.info("advisor_used_sdk")
        except Exception as exc:
            log.error("advisor_sdk_error", error=str(exc))
            return (str(exc), dict(_EMPTY_ACTIONS))
    except subprocess.TimeoutExpired:
        return ("Request timed out after 120 s — try a shorter question.", dict(_EMPTY_ACTIONS))
    except Exception as exc:
        log.error("advisor_cli_error", error=str(exc))
        return (f"Error contacting Claude: {exc}", dict(_EMPTY_ACTIONS))

    actions = _parse_actions(raw)
    display_text = re.sub(r"\s*<actions>.*?</actions>", "", raw, flags=re.DOTALL).strip()

    log.info(
        "advisor_response",
        question_len=len(question),
        response_len=len(display_text),
        watchlist_suggestions=len(actions["add_to_watchlist"]),
        risk_suggestion=actions["risk_tolerance"],
        strategy_suggestion=actions["strategy"],
    )
    return display_text, actions
