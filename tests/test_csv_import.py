"""Tests for CSV import edge cases in pmod.data.external_accounts.parse_csv."""
from __future__ import annotations

import io

import pytest

from pmod.data.external_accounts import parse_csv


def _csv(content: str) -> io.StringIO:
    return io.StringIO(content.strip())


class TestParseCsvValidation:
    def test_basic_happy_path(self) -> None:
        data = "ticker,shares,price,market value\nAAPL,10,150.00,1500.00\n"
        rows = parse_csv(_csv(data))
        assert len(rows) == 1
        assert rows[0].ticker == "AAPL"
        assert rows[0].shares == pytest.approx(10.0)
        assert rows[0].current_price == pytest.approx(150.0)

    def test_rejects_blank_ticker(self) -> None:
        data = "ticker,shares,price\n,10,100\n"
        rows = parse_csv(_csv(data))
        assert rows == []

    def test_rejects_ticker_with_spaces(self) -> None:
        data = "ticker,shares,price\nCASH & CASH INVESTMENTS,0,1.00\n"
        rows = parse_csv(_csv(data))
        assert rows == []

    def test_rejects_all_numeric_ticker(self) -> None:
        data = "ticker,shares,price\n12345,10,50.00\n"
        rows = parse_csv(_csv(data))
        assert rows == []

    def test_rejects_ticker_longer_than_10_chars(self) -> None:
        data = "ticker,shares,price\nTECHNOLOGYXYZ,10,50.00\n"
        rows = parse_csv(_csv(data))
        assert rows == []

    def test_accepts_valid_5_char_ticker(self) -> None:
        data = "ticker,shares,price\nAASRX,100,25.00\n"
        rows = parse_csv(_csv(data))
        assert len(rows) == 1
        assert rows[0].ticker == "AASRX"

    def test_accepts_ticker_with_dot(self) -> None:
        # e.g. BRK.B style
        data = "ticker,shares,price\nBRK.B,5,350.00\n"
        rows = parse_csv(_csv(data))
        assert len(rows) == 1
        assert rows[0].ticker == "BRK.B"

    def test_rejects_footer_rows(self) -> None:
        data = "ticker,shares,price\nAAPL,10,150\nTotal,,15000\nGrand Total,,30000\n"
        rows = parse_csv(_csv(data))
        assert len(rows) == 1
        assert rows[0].ticker == "AAPL"

    def test_duplicate_tickers_kept_both(self) -> None:
        # parse_csv is a raw parser; deduplication is caller's responsibility
        data = "ticker,shares,price\nVTI,50,200\nVTI,25,201\n"
        rows = parse_csv(_csv(data))
        assert len(rows) == 2
        assert all(r.ticker == "VTI" for r in rows)

    def test_negative_shares_parsed(self) -> None:
        # Negative shares can occur in short positions — should parse, not reject
        data = "ticker,shares,price\nTSLA,-10,200.00\n"
        rows = parse_csv(_csv(data))
        assert len(rows) == 1
        assert rows[0].shares == pytest.approx(-10.0)

    def test_market_value_derived_from_shares_times_price(self) -> None:
        data = "ticker,shares,price\nMSFT,5,400.00\n"
        rows = parse_csv(_csv(data))
        assert len(rows) == 1
        assert rows[0].market_value == pytest.approx(2000.0)

    def test_strips_dollar_signs_and_commas(self) -> None:
        data = "ticker,shares,price,market value\nNVDA,10,$924.80,\"$9,248.00\"\n"
        rows = parse_csv(_csv(data))
        assert len(rows) == 1
        assert rows[0].current_price == pytest.approx(924.80)
        assert rows[0].market_value == pytest.approx(9248.00)

    def test_windows_line_endings(self) -> None:
        data = "ticker,shares,price\r\nAMZN,3,185.00\r\n"
        rows = parse_csv(io.StringIO(data))
        assert len(rows) == 1
        assert rows[0].ticker == "AMZN"

    def test_utf8_bom_stripped(self) -> None:
        # Write a CSV file with a UTF-8 BOM (as Excel exports) and verify it parses cleanly.
        import pathlib
        import tempfile
        content = "ticker,shares,price\nGOOGL,2,170.00\n"
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", suffix=".csv", delete=False) as f:
            f.write(content)
            tmp_path = pathlib.Path(f.name)
        try:
            rows = parse_csv(tmp_path)
            assert len(rows) == 1
            assert rows[0].ticker == "GOOGL"
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_empty_csv_returns_empty_list(self) -> None:
        data = "ticker,shares,price\n"
        rows = parse_csv(_csv(data))
        assert rows == []

    def test_schwab_parenthesis_negative_value(self) -> None:
        # Schwab exports negatives as (1.23)
        data = "ticker,shares,average cost\nTSLA,10,(248.60)\n"
        rows = parse_csv(_csv(data))
        assert len(rows) == 1
        assert rows[0].avg_cost == pytest.approx(-248.60)
