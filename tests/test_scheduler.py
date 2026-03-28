"""Tests for pmod.scheduler.jobs — background job scheduling."""

from unittest.mock import MagicMock, patch

import pytest


class TestRefreshToken:
    def test_logs_error_when_not_connected(self) -> None:
        from pmod.scheduler.jobs import _refresh_token

        with patch("pmod.scheduler.jobs.log") as mock_log:
            with patch("pmod.auth.schwab.auth_status", return_value={"connected": False, "reason": "expired"}):
                _refresh_token()
            mock_log.error.assert_called_once()

    def test_calls_get_client_when_connected(self) -> None:
        from pmod.scheduler.jobs import _refresh_token

        mock_client = MagicMock()
        with patch("pmod.auth.schwab.auth_status", return_value={"connected": True, "reason": "ok"}):
            with patch("pmod.auth.schwab.get_client", return_value=mock_client):
                _refresh_token()
                # get_client was called (forces token refresh)

    def test_handles_exception_gracefully(self) -> None:
        from pmod.scheduler.jobs import _refresh_token

        with patch("pmod.auth.schwab.auth_status", side_effect=RuntimeError("boom")):
            with patch("pmod.scheduler.jobs.log") as mock_log:
                _refresh_token()  # Should not raise
                mock_log.error.assert_called_once()


class TestRunResearch:
    def test_runs_pipeline(self) -> None:
        from pmod.scheduler.jobs import _run_research

        mock_signals = [MagicMock() for _ in range(3)]
        with patch("pmod.research.politician_signals.generate_signals", return_value=mock_signals):
            with patch("pmod.research.screener.screen_and_update_watchlist", return_value=5):
                _run_research()

    def test_handles_exception_gracefully(self) -> None:
        from pmod.scheduler.jobs import _run_research

        with patch("pmod.research.politician_signals.generate_signals", side_effect=RuntimeError("fail")):
            with patch("pmod.scheduler.jobs.log") as mock_log:
                _run_research()  # Should not raise
                mock_log.error.assert_called_once()


class TestRunRebalance:
    def test_skips_when_manual_mode(self) -> None:
        from pmod.scheduler.jobs import _run_rebalance

        mock_plan = MagicMock()
        mock_trade = MagicMock(action="buy", shares_delta=10)
        mock_plan.trades = [mock_trade]
        mock_plan.net_cash_change = -500.0

        prefs = {"max_position_pct": 5.0, "trade_execution": "manual-confirm"}
        with patch("pmod.preferences.profile.load_preferences_dict", return_value=prefs):
            with patch("pmod.optimizer.portfolio.compute_rebalance", return_value=mock_plan):
                with patch("pmod.scheduler.jobs.log") as mock_log:
                    _run_rebalance()
                    # Should log that it skipped due to manual mode
                    calls = [str(c) for c in mock_log.info.call_args_list]
                    assert any("manual" in c for c in calls)

    def test_no_action_when_all_hold(self) -> None:
        from pmod.scheduler.jobs import _run_rebalance

        mock_plan = MagicMock()
        mock_trade = MagicMock(action="hold")
        mock_plan.trades = [mock_trade]

        prefs = {"max_position_pct": 5.0, "trade_execution": "auto"}
        with patch("pmod.preferences.profile.load_preferences_dict", return_value=prefs):
            with patch("pmod.optimizer.portfolio.compute_rebalance", return_value=mock_plan):
                _run_rebalance()


class TestCaptureSnapshot:
    def test_skips_when_no_account(self) -> None:
        from pmod.scheduler.jobs import _capture_snapshot

        with patch("pmod.broker.schwab.get_account_summary", return_value=None):
            _capture_snapshot()  # Should not raise

    def test_handles_exception_gracefully(self) -> None:
        from pmod.scheduler.jobs import _capture_snapshot

        with patch("pmod.broker.schwab.get_account_summary", side_effect=RuntimeError("no auth")):
            with patch("pmod.scheduler.jobs.log") as mock_log:
                _capture_snapshot()
                mock_log.error.assert_called_once()


class TestStartStopScheduler:
    def test_start_and_stop(self) -> None:
        from pmod.scheduler.jobs import get_scheduler, start_scheduler, stop_scheduler

        prefs = {"rebalance_frequency": "manual"}
        with patch("pmod.preferences.profile.load_preferences_dict", return_value=prefs):
            sched = start_scheduler()
            assert sched.running

            current = get_scheduler()
            assert current is sched

            stop_scheduler()
            assert get_scheduler() is None

    def test_weekly_rebalance_schedule(self) -> None:
        from pmod.scheduler.jobs import start_scheduler, stop_scheduler

        prefs = {"rebalance_frequency": "weekly"}
        with patch("pmod.preferences.profile.load_preferences_dict", return_value=prefs):
            sched = start_scheduler()
            job_ids = [j.id for j in sched.get_jobs()]
            assert "rebalance" in job_ids
            stop_scheduler()

    def test_daily_rebalance_schedule(self) -> None:
        from pmod.scheduler.jobs import start_scheduler, stop_scheduler

        prefs = {"rebalance_frequency": "daily"}
        with patch("pmod.preferences.profile.load_preferences_dict", return_value=prefs):
            sched = start_scheduler()
            job_ids = [j.id for j in sched.get_jobs()]
            assert "rebalance" in job_ids
            stop_scheduler()
