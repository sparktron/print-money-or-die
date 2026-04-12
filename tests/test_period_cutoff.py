"""Tests for _period_cutoff in dashboard.pages.portfolio."""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from pmod.dashboard.pages.portfolio import _period_cutoff


class TestPeriodCutoff:
    def test_1w_is_seven_days_back(self) -> None:
        today = date(2026, 4, 4)
        with patch("pmod.dashboard.pages.portfolio.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = _period_cutoff("1W")
        assert result == date(2026, 3, 28)

    def test_1m_steps_back_one_calendar_month(self) -> None:
        today = date(2026, 4, 4)
        with patch("pmod.dashboard.pages.portfolio.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = _period_cutoff("1M")
        assert result == date(2026, 3, 4)

    def test_1m_january_steps_back_to_december(self) -> None:
        today = date(2026, 1, 15)
        with patch("pmod.dashboard.pages.portfolio.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = _period_cutoff("1M")
        assert result == date(2025, 12, 15)

    def test_1m_march_31_steps_back_to_feb_28(self) -> None:
        # March 31 → Feb doesn't have 31 days → clamp to Feb 28
        today = date(2026, 3, 31)
        with patch("pmod.dashboard.pages.portfolio.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = _period_cutoff("1M")
        assert result == date(2026, 2, 28)

    def test_ytd_is_jan_1(self) -> None:
        today = date(2026, 4, 4)
        with patch("pmod.dashboard.pages.portfolio.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = _period_cutoff("YTD")
        assert result == date(2026, 1, 1)

    def test_1y_same_calendar_day_last_year(self) -> None:
        today = date(2026, 4, 4)
        with patch("pmod.dashboard.pages.portfolio.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = _period_cutoff("1Y")
        assert result == date(2025, 4, 4)

    def test_1y_feb_29_leap_year_falls_back_to_feb_28(self) -> None:
        # 2024 is a leap year; going back 1Y from Feb 29 2024 → 2023 has no Feb 29
        today = date(2024, 2, 29)
        with patch("pmod.dashboard.pages.portfolio.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = _period_cutoff("1Y")
        assert result == date(2023, 2, 28)

    def test_unknown_period_returns_1y(self) -> None:
        today = date(2026, 6, 15)
        with patch("pmod.dashboard.pages.portfolio.date") as mock_date:
            mock_date.today.return_value = today
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            result = _period_cutoff("ALL")
        assert result == date(2025, 6, 15)
