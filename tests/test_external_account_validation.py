"""Tests for external account position data integrity and sanity checks.

Catches issues like:
- Mismatched shares/price/market_value (calculated vs stored)
- Price anomalies (10x jumps, negative prices, zero prices for non-zero shares)
- Portfolio totals that don't match sum of positions
- Positions with zero value but non-zero shares (or vice versa)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from pmod.data.models import ExternalAccount, ExternalPosition, get_session


class TestExternalPositionDataIntegrity:
    """Validate that position records are internally consistent."""

    def test_market_value_matches_shares_times_price(self, test_external_account):
        """Ensure market_value = shares * current_price (within rounding)."""
        with get_session() as session:
            pos = ExternalPosition(
                account_id=test_external_account,
                ticker="AASRX",
                shares=Decimal("1247.7814"),
                current_price=Decimal("25.34"),
                market_value=Decimal("31618.78"),
            )
            session.add(pos)
            session.commit()

        # Verify
        with get_session() as session:
            pos = session.query(ExternalPosition).filter_by(ticker="AASRX").first()
            calculated = pos.shares * pos.current_price

            # Allow ±0.01 rounding tolerance
            assert abs(float(pos.market_value) - float(calculated)) < 0.01, \
                f"market_value {pos.market_value} != shares*price {calculated}"

    def test_price_sanity_check(self, test_external_account):
        """Flag if price is suspiciously high or zero."""
        with get_session() as session:
            # Good price
            pos1 = ExternalPosition(
                account_id=test_external_account,
                ticker="GOOD",
                shares=Decimal("100"),
                current_price=Decimal("50.00"),
                market_value=Decimal("5000.00"),
            )
            session.add(pos1)

            # Bad: price is 10x too high
            pos2 = ExternalPosition(
                account_id=test_external_account,
                ticker="AASRX",
                shares=Decimal("1247.7814"),
                current_price=Decimal("359.18"),  # Should be ~$25
                market_value=Decimal("448178.11"),  # Wrong!
            )
            session.add(pos2)
            session.commit()

        # Verify we can detect the anomaly
        with get_session() as session:
            pos = session.query(ExternalPosition).filter_by(ticker="AASRX").first()

            # Sanity: if price seems wildly off (calculated != stored), flag it
            calculated_value = pos.shares * pos.current_price
            stored_value = pos.market_value

            ratio = float(calculated_value) / float(stored_value) if stored_value else 0

            # This SHOULD fail (shows the bug)
            if abs(ratio - 1.0) > 0.05:  # >5% mismatch is suspicious
                assert False, \
                    f"Price mismatch for {pos.ticker}: " \
                    f"calculated {calculated_value} vs stored {stored_value} " \
                    f"(ratio {ratio:.2f})"

    def test_zero_price_with_nonzero_shares_is_invalid(self, test_external_account):
        """DETECTOR: Flag positions with shares but no price."""
        with get_session() as session:
            pos = ExternalPosition(
                account_id=test_external_account,
                ticker="BADPRICE",
                shares=Decimal("100"),
                current_price=Decimal("0.00"),  # Bad!
                market_value=Decimal("0.00"),
            )
            session.add(pos)
            session.commit()

        # Verify we CAN detect this anomaly
        issues = []
        with get_session() as session:
            pos = session.query(ExternalPosition).filter_by(ticker="BADPRICE").first()

            has_shares = float(pos.shares) > 0.001
            has_price = float(pos.current_price) > 0
            has_value = float(pos.market_value) > 0.01

            if has_shares and not (has_price and has_value):
                issues.append(
                    f"{pos.ticker}: {pos.shares} shares but price=${pos.current_price}, value=${pos.market_value}"
                )

        # Ensure we caught the issue
        assert len(issues) > 0, "Failed to detect zero-price position"
        print(f"✓ Detected: {issues[0]}")

    def test_portfolio_total_sanity(self, test_external_account):
        """Verify that portfolio totals match sum of positions."""
        with get_session() as session:
            pos1 = ExternalPosition(
                account_id=test_external_account,
                ticker="VTI",
                shares=Decimal("50"),
                current_price=Decimal("200.00"),
                market_value=Decimal("10000.00"),
            )
            pos2 = ExternalPosition(
                account_id=test_external_account,
                ticker="BND",
                shares=Decimal("100"),
                current_price=Decimal("80.00"),
                market_value=Decimal("8000.00"),
            )
            session.add_all([pos1, pos2])
            session.commit()

        # Verify totals match
        with get_session() as session:
            positions = session.query(ExternalPosition).filter_by(
                account_id=test_external_account
            ).all()

            total = sum(float(p.market_value) for p in positions)
            expected = 18000.00

            assert abs(total - expected) < 0.01, \
                f"Portfolio total {total} != expected {expected}. Positions: {[(p.ticker, p.market_value) for p in positions]}"

    def test_negative_price_is_invalid(self, test_external_account):
        """DETECTOR: Flag any negative prices."""
        with get_session() as session:
            pos = ExternalPosition(
                account_id=test_external_account,
                ticker="NOPE",
                shares=Decimal("100"),
                current_price=Decimal("-50.00"),  # Impossible!
                market_value=Decimal("-5000.00"),
            )
            session.add(pos)
            session.commit()

        # Verify we can detect this
        issues = []
        with get_session() as session:
            pos = session.query(ExternalPosition).filter_by(ticker="NOPE").first()

            if float(pos.current_price) < 0:
                issues.append(f"{pos.ticker}: negative price ${pos.current_price}")

        assert len(issues) > 0, "Failed to detect negative price"
        print(f"✓ Detected: {issues[0]}")


class TestExternalAccountPriceAnomalies:
    """Detect suspicious price changes between updates."""

    @pytest.mark.xfail(strict=True, reason="Demonstrates anomaly detection: this scenario intentionally triggers a failure")
    def test_price_jump_detection(self, test_external_account):
        """Flag if price jumps >50% between consecutive updates (unusual)."""
        with get_session() as session:
            # First update: $25.34
            pos = ExternalPosition(
                account_id=test_external_account,
                ticker="AASRX",
                shares=Decimal("1247.7814"),
                current_price=Decimal("25.34"),
                market_value=Decimal("31618.78"),
            )
            session.add(pos)
            session.commit()

        # Second update: price jumped to $359.18 (1414% increase!)
        with get_session() as session:
            pos = session.query(ExternalPosition).filter_by(ticker="AASRX").first()
            old_price = float(pos.current_price)
            new_price = 359.18

            pct_change = abs((new_price - old_price) / old_price) * 100

            if pct_change > 50:  # Unrealistic for a single day
                assert False, \
                    f"{pos.ticker}: price jumped {pct_change:.1f}% " \
                    f"from ${old_price:.2f} to ${new_price:.2f} — check data source!"
