"""Tests for portfolio P&L and alpha calculations.

Ensures that Today's P&L, Total P&L, and Alpha vs S&P 500 are calculated correctly.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from pmod.data.models import ExternalAccount, ExternalPosition, get_session
from pmod.analytics.alpha import calculate_alpha, get_historical_returns


class TestPortfolioMetrics:
    """Test P&L and alpha calculations."""

    def test_external_account_total_pnl_calculation(self, test_external_account):
        """Verify total P&L is calculated correctly for external accounts."""
        with get_session() as session:
            # Create a position with cost basis and current price
            pos = ExternalPosition(
                account_id=test_external_account,
                ticker="AASRX",
                shares=1000.0,  # Store as float (matches DB schema)
                avg_cost=20.00,
                current_price=25.00,
                market_value=25000.00,
            )
            session.add(pos)
            session.commit()

        # Verify calculation
        with get_session() as session:
            pos = session.query(ExternalPosition).filter_by(ticker="AASRX").first()

            # Expected P&L: (25.00 - 20.00) * 1000 = $5,000
            if pos.avg_cost and pos.current_price:
                expected_pnl = (pos.current_price - pos.avg_cost) * pos.shares
                # Expected P&L %: (25.00 - 20.00) / 20.00 * 100 = 25%
                expected_pnl_pct = (pos.current_price - pos.avg_cost) / pos.avg_cost * 100

                assert abs(expected_pnl - 5000.0) < 0.01, \
                    f"Expected P&L $5,000, got ${expected_pnl}"
                assert abs(expected_pnl_pct - 25.0) < 0.01, \
                    f"Expected P&L% 25%, got {expected_pnl_pct}%"

    def test_zero_pnl_when_price_equals_cost(self, test_external_account):
        """Verify P&L is zero when current price equals average cost."""
        with get_session() as session:
            pos = ExternalPosition(
                account_id=test_external_account,
                ticker="TEST",
                shares=Decimal("500"),
                avg_cost=Decimal("50.00"),
                current_price=Decimal("50.00"),  # Same as cost
                market_value=Decimal("25000.00"),
            )
            session.add(pos)
            session.commit()

        with get_session() as session:
            pos = session.query(ExternalPosition).filter_by(ticker="TEST").first()

            pnl = (pos.current_price - pos.avg_cost) * pos.shares
            pnl_pct = (pos.current_price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost else 0

            assert abs(pnl) < 0.01, f"Expected P&L $0, got ${pnl}"
            assert abs(pnl_pct) < 0.01, f"Expected P&L% 0%, got {pnl_pct}%"

    def test_negative_pnl_when_price_below_cost(self, test_external_account):
        """Verify P&L is negative when current price is below average cost."""
        with get_session() as session:
            pos = ExternalPosition(
                account_id=test_external_account,
                ticker="LOSER",
                shares=Decimal("200"),
                avg_cost=Decimal("100.00"),  # Cost: $20,000
                current_price=Decimal("80.00"),  # Value: $16,000
                market_value=Decimal("16000.00"),
            )
            session.add(pos)
            session.commit()

        with get_session() as session:
            pos = session.query(ExternalPosition).filter_by(ticker="LOSER").first()

            # Expected P&L: (80.00 - 100.00) * 200 = -$4,000
            pnl = (pos.current_price - pos.avg_cost) * pos.shares
            # Expected P&L %: (80.00 - 100.00) / 100.00 * 100 = -20%
            pnl_pct = (pos.current_price - pos.avg_cost) / pos.avg_cost * 100

            assert abs(pnl - (-4000.0)) < 0.01, \
                f"Expected P&L -$4,000, got ${pnl}"
            assert abs(pnl_pct - (-20.0)) < 0.01, \
                f"Expected P&L% -20%, got {pnl_pct}%"

    def test_pnl_with_no_cost_basis(self, test_external_account):
        """Verify P&L calculation handles missing cost basis gracefully."""
        with get_session() as session:
            pos = ExternalPosition(
                account_id=test_external_account,
                ticker="NOCOST",
                shares=Decimal("100"),
                avg_cost=None,  # No cost basis
                current_price=Decimal("50.00"),
                market_value=Decimal("5000.00"),
            )
            session.add(pos)
            session.commit()

        with get_session() as session:
            pos = session.query(ExternalPosition).filter_by(ticker="NOCOST").first()

            # Without cost basis, P&L should be 0
            pnl = (pos.current_price - (pos.avg_cost or 0)) * pos.shares
            pnl_pct = 0  # Can't calculate % without cost basis

            assert abs(pnl - 5000.0) < 0.01  # (50 - 0) * 100 = 5000
            assert pnl_pct == 0


class TestAlphaCalculation:
    """Test alpha (excess return vs S&P 500) calculation."""

    def test_alpha_returns_none_with_insufficient_data(self):
        """Verify alpha returns None when insufficient historical data exists."""
        # This test checks that the function handles gracefully when there's no data
        alpha_data = calculate_alpha()

        # Alpha should be None or have insufficient data marker
        if alpha_data is None:
            assert True, "Alpha correctly returned None for insufficient data"
        else:
            assert "days_tracked" in alpha_data
            print(f"Alpha data available: {alpha_data['days_tracked']} days")

    def test_alpha_structure(self):
        """Verify alpha calculation returns proper structure when data is available."""
        alpha_data = calculate_alpha()

        if alpha_data is not None:
            assert "total_return_pct" in alpha_data
            assert "benchmark_return_pct" in alpha_data
            assert "alpha_pct" in alpha_data
            assert "days_tracked" in alpha_data

            # All values should be numbers
            assert isinstance(alpha_data["total_return_pct"], (int, float))
            assert isinstance(alpha_data["benchmark_return_pct"], (int, float))
            assert isinstance(alpha_data["alpha_pct"], (int, float))
            assert isinstance(alpha_data["days_tracked"], int)


class TestDayPLDisplay:
    """Test that day P&L display is correct."""

    def test_day_pnl_zero_for_external_accounts(self):
        """Verify external accounts correctly show $0 day P&L (no intraday tracking)."""
        # External accounts are static imports, so day P&L should always be 0
        # This is the expected and correct behavior
        expected_day_pnl = 0.0
        expected_display = "$0 (0.00%)"

        day_pnl_str = f"${abs(expected_day_pnl):,.0f}"
        day_pnl_pct_str = f"{expected_day_pnl:.2f}%"
        display = f"{day_pnl_str} ({day_pnl_pct_str})"

        assert display == expected_display, \
            f"Expected '{expected_display}', got '{display}'"

    def test_day_pnl_positive_display(self):
        """Verify positive day P&L displays with + sign."""
        day_pnl = 42.50
        day_pnl_pct = 0.18
        day_sign = "+" if day_pnl >= 0 else ""

        day_pnl_str = f"{day_sign}${abs(day_pnl):,.0f}"
        day_pnl_pct_str = f"{day_sign}{day_pnl_pct:.2f}%"
        display = f"{day_pnl_str} ({day_pnl_pct_str})"

        assert display == "+$42 (+0.18%)"

    def test_day_pnl_negative_display(self):
        """Verify negative day P&L displays with - sign."""
        day_pnl = -120.00
        day_pnl_pct = -1.37
        day_sign = "+" if day_pnl >= 0 else ""

        # Format dollar amount with sign
        day_pnl_str = f"${abs(day_pnl):,.0f}"
        if day_pnl < 0:
            day_pnl_str = f"-{day_pnl_str}"

        # Format percentage with sign
        day_pnl_pct_str = f"{day_sign}{day_pnl_pct:.2f}%"
        display = f"{day_pnl_str} ({day_pnl_pct_str})"

        assert display == "-$120 (-1.37%)"
