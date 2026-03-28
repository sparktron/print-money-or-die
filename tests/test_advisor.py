"""Tests for the AI advisor module.

Focuses on the subprocess plumbing that caused the "CLI exited 1" bug:
- stdin=DEVNULL is set (prevents hang in threaded Dash callbacks)
- cwd is not the repo root (prevents CLAUDE.md from overriding system prompt)
- fallback to SDK when CLI is not on PATH
- error text returned gracefully on timeout / non-zero exit
- _parse_actions correctly extracts structured data
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_completed(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ── _ask_via_cli ───────────────────────────────────────────────────────────────

class TestAskViaCli:
    def test_uses_devnull_stdin(self):
        """subprocess.DEVNULL must be passed as stdin — prevents Dash-thread hang."""
        from pmod.advisor.claude import _ask_via_cli

        with patch("subprocess.run", return_value=_make_completed(0, "hello")) as mock_run:
            _ask_via_cli("test question")

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs.get("stdin") == subprocess.DEVNULL, (
            "stdin must be subprocess.DEVNULL to prevent the 3-second hang "
            "when called from a Dash callback thread"
        )

    def test_cwd_is_not_repo_root(self):
        """cwd must not be the repo root — CLAUDE.md would override system prompt."""
        from pmod.advisor.claude import _ask_via_cli

        repo_root = str(Path(__file__).parent.parent.resolve())

        with patch("subprocess.run", return_value=_make_completed(0, "hello")) as mock_run:
            _ask_via_cli("test question")

        call_kwargs = mock_run.call_args.kwargs
        cwd = call_kwargs.get("cwd", "")
        assert str(cwd) != repo_root, (
            f"cwd must not be the repo root ({repo_root}) — the claude CLI "
            "would pick up CLAUDE.md and replace the financial advisor system prompt"
        )

    def test_cwd_is_home_dir(self):
        """cwd should be the user's home directory."""
        from pmod.advisor.claude import _ask_via_cli

        with patch("subprocess.run", return_value=_make_completed(0, "hello")) as mock_run:
            _ask_via_cli("test question")

        call_kwargs = mock_run.call_args.kwargs
        assert str(call_kwargs.get("cwd")) == os.path.expanduser("~")

    def test_system_prompt_passed_as_flag(self):
        """--system-prompt must appear in the CLI args."""
        from pmod.advisor.claude import _ask_via_cli

        with patch("subprocess.run", return_value=_make_completed(0, "ok")) as mock_run:
            _ask_via_cli("my question")

        args = mock_run.call_args.args[0]
        assert "--system-prompt" in args

    def test_returns_stdout_on_success(self):
        from pmod.advisor.claude import _ask_via_cli

        with patch("subprocess.run", return_value=_make_completed(0, "Great answer!")):
            result = _ask_via_cli("any question")

        assert result == "Great answer!"

    def test_raises_on_nonzero_exit(self):
        from pmod.advisor.claude import _ask_via_cli

        with patch("subprocess.run", return_value=_make_completed(1, "", "auth error")):
            with pytest.raises(RuntimeError, match="exited 1"):
                _ask_via_cli("any question")

    def test_nonzero_exit_no_stderr_shows_placeholder(self):
        """Empty stderr on failure must not produce a cryptic empty message."""
        from pmod.advisor.claude import _ask_via_cli

        with patch("subprocess.run", return_value=_make_completed(1, "", "")):
            with pytest.raises(RuntimeError, match="no stderr"):
                _ask_via_cli("any question")

    def test_raises_on_timeout(self):
        from pmod.advisor.claude import _ask_via_cli

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 120)):
            with pytest.raises(subprocess.TimeoutExpired):
                _ask_via_cli("any question")


# ── ask_claude (top-level) ────────────────────────────────────────────────────

class TestAskClaude:
    def _mock_context(self):
        """Patch portfolio context so tests don't need a real DB."""
        return patch("pmod.advisor.claude._get_portfolio_context", return_value={})

    def test_returns_text_and_actions_on_success(self):
        from pmod.advisor.claude import ask_claude

        response = "Buy VOO. <actions>{\"add_to_watchlist\": [], \"risk_tolerance\": null, \"strategy\": null}</actions>"
        with self._mock_context():
            with patch("pmod.advisor.claude._ask_via_cli", return_value=response):
                text, actions = ask_claude("What should I buy?")

        assert "VOO" in text
        assert "<actions>" not in text
        assert "add_to_watchlist" in actions

    def test_falls_back_to_sdk_when_cli_not_found(self):
        from pmod.advisor.claude import ask_claude

        sdk_response = "Use index funds. <actions>{\"add_to_watchlist\": [], \"risk_tolerance\": null, \"strategy\": null}</actions>"
        with self._mock_context():
            with patch("pmod.advisor.claude._ask_via_cli", side_effect=FileNotFoundError):
                with patch("pmod.advisor.claude._ask_via_sdk", return_value=sdk_response) as mock_sdk:
                    text, actions = ask_claude("advice?")

        mock_sdk.assert_called_once()
        assert "index funds" in text

    def test_returns_error_string_on_cli_failure(self):
        from pmod.advisor.claude import ask_claude

        with self._mock_context():
            with patch("pmod.advisor.claude._ask_via_cli", side_effect=RuntimeError("exited 1: boom")):
                text, actions = ask_claude("advice?")

        assert "Error" in text or "error" in text.lower()
        assert actions == {"add_to_watchlist": [], "risk_tolerance": None, "strategy": None}

    def test_returns_error_string_on_timeout(self):
        from pmod.advisor.claude import ask_claude

        with self._mock_context():
            with patch("pmod.advisor.claude._ask_via_cli", side_effect=subprocess.TimeoutExpired("c", 120)):
                text, actions = ask_claude("advice?")

        assert "timed out" in text.lower()
        assert actions["add_to_watchlist"] == []

    def test_strips_actions_block_from_display_text(self):
        from pmod.advisor.claude import ask_claude

        raw = "Here is my advice.\n\n<actions>{\"add_to_watchlist\": [], \"risk_tolerance\": null, \"strategy\": null}</actions>"
        with self._mock_context():
            with patch("pmod.advisor.claude._ask_via_cli", return_value=raw):
                text, _ = ask_claude("?")

        assert "<actions>" not in text
        assert "Here is my advice." in text


# ── _parse_actions ────────────────────────────────────────────────────────────

class TestParseActions:
    def test_valid_watchlist(self):
        from pmod.advisor.claude import _parse_actions

        raw = '<actions>{"add_to_watchlist": [{"ticker": "NVDA", "reason": "AI growth"}], "risk_tolerance": null, "strategy": null}</actions>'
        actions = _parse_actions(raw)
        assert actions["add_to_watchlist"] == [{"ticker": "NVDA", "reason": "AI growth"}]

    def test_valid_risk_and_strategy(self):
        from pmod.advisor.claude import _parse_actions

        raw = '<actions>{"add_to_watchlist": [], "risk_tolerance": "high", "strategy": "growth"}</actions>'
        actions = _parse_actions(raw)
        assert actions["risk_tolerance"] == "high"
        assert actions["strategy"] == "growth"

    def test_invalid_risk_value_rejected(self):
        from pmod.advisor.claude import _parse_actions

        raw = '<actions>{"add_to_watchlist": [], "risk_tolerance": "yolo", "strategy": null}</actions>'
        actions = _parse_actions(raw)
        assert actions["risk_tolerance"] is None

    def test_invalid_strategy_value_rejected(self):
        from pmod.advisor.claude import _parse_actions

        raw = '<actions>{"add_to_watchlist": [], "risk_tolerance": null, "strategy": "memes"}</actions>'
        actions = _parse_actions(raw)
        assert actions["strategy"] is None

    def test_invalid_ticker_rejected(self):
        from pmod.advisor.claude import _parse_actions

        raw = '<actions>{"add_to_watchlist": [{"ticker": "TOOLONGTICKER", "reason": "x"}], "risk_tolerance": null, "strategy": null}</actions>'
        actions = _parse_actions(raw)
        assert actions["add_to_watchlist"] == []

    def test_missing_actions_block_returns_defaults(self):
        from pmod.advisor.claude import _parse_actions

        actions = _parse_actions("Just some text with no actions block.")
        assert actions == {"add_to_watchlist": [], "risk_tolerance": None, "strategy": None}

    def test_malformed_json_returns_defaults(self):
        from pmod.advisor.claude import _parse_actions

        actions = _parse_actions("<actions>{not valid json}</actions>")
        assert actions == {"add_to_watchlist": [], "risk_tolerance": None, "strategy": None}
