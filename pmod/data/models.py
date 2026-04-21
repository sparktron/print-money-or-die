"""SQLAlchemy models for local persistence."""

import functools
from contextlib import contextmanager
from datetime import datetime
from typing import Generator

from sqlalchemy import Column, Date, DateTime, Enum, Float, Integer, String, Text, UniqueConstraint, create_engine, func, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from pmod.config import get_settings


class Base(DeclarativeBase):
    pass


class UserPreference(Base):
    """User risk profile and strategy preferences."""

    __tablename__ = "user_preferences"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    risk_tolerance: str = Column(  # type: ignore[assignment]
        Enum("low", "medium", "high", "degen", name="risk_tolerance"),
        nullable=False,
        default="medium",
    )
    strategy: str = Column(  # type: ignore[assignment]
        Enum("growth", "value", "dividend", "momentum", "balanced", name="strategy"),
        nullable=False,
        default="balanced",
    )
    max_position_pct: float = Column(Float, nullable=False, default=5.0)  # type: ignore[assignment]
    rebalance_frequency: str = Column(  # type: ignore[assignment]
        Enum("manual", "daily", "weekly", name="rebalance_frequency"),
        nullable=False,
        default="manual",
    )
    trade_execution: str = Column(  # type: ignore[assignment]
        Enum("manual-confirm", "auto", name="trade_execution"),
        nullable=False,
        default="manual-confirm",
    )
    sector_focus: str = Column(Text, nullable=True, default="[]")  # type: ignore[assignment]
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WatchlistItem(Base):
    """A ticker on the curated watchlist."""

    __tablename__ = "watchlist"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    ticker: str = Column(String(10), nullable=False, unique=True)  # type: ignore[assignment]
    company_name: str = Column(String(200), nullable=False)  # type: ignore[assignment]
    reason: str = Column(String(1000), nullable=True)  # type: ignore[assignment]
    momentum_score: float = Column(Float, nullable=True)  # type: ignore[assignment]
    added_at = Column(DateTime, server_default=func.now())


class PoliticianTrade(Base):
    """A disclosed stock trade by a member of Congress."""

    __tablename__ = "politician_trades"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    politician_name: str = Column(String(200), nullable=False)  # type: ignore[assignment]
    chamber: str = Column(  # type: ignore[assignment]
        Enum("house", "senate", name="chamber"), nullable=False
    )
    party: str = Column(String(10), nullable=True)  # type: ignore[assignment]
    state: str = Column(String(10), nullable=True)  # type: ignore[assignment]
    ticker: str = Column(String(20), nullable=False, index=True)  # type: ignore[assignment]
    company_name: str = Column(String(300), nullable=True)  # type: ignore[assignment]
    trade_type: str = Column(  # type: ignore[assignment]
        Enum("purchase", "sale", "sale_partial", "exchange", name="trade_type"),
        nullable=False,
    )
    transaction_date: datetime | None = Column(DateTime, nullable=True)  # type: ignore[assignment]
    disclosure_date: datetime = Column(DateTime, nullable=False)  # type: ignore[assignment]
    amount_low: int = Column(Integer, nullable=True)  # type: ignore[assignment]
    amount_high: int = Column(Integer, nullable=True)  # type: ignore[assignment]
    report_url: str = Column(String(500), nullable=True)  # type: ignore[assignment]
    fetched_at = Column(DateTime, server_default=func.now())


class ExternalAccount(Base):
    """A manually-tracked external account (e.g. 529, IRA at another custodian)."""

    __tablename__ = "external_accounts"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    name: str = Column(String(200), nullable=False, unique=True)  # type: ignore[assignment]
    account_type: str = Column(String(50), nullable=True)  # type: ignore[assignment]  e.g. "529", "IRA"
    last_imported_at = Column(DateTime, nullable=True)


class ExternalPosition(Base):
    """A position inside an external account, populated from a CSV import."""

    __tablename__ = "external_positions"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    account_id: int = Column(Integer, nullable=False, index=True)  # type: ignore[assignment]
    ticker: str = Column(String(20), nullable=False)  # type: ignore[assignment]
    company_name: str = Column(String(300), nullable=True)  # type: ignore[assignment]
    shares: float = Column(Float, nullable=True)  # type: ignore[assignment]
    avg_cost: float = Column(Float, nullable=True)  # type: ignore[assignment]
    current_price: float = Column(Float, nullable=True)  # type: ignore[assignment]
    market_value: float = Column(Float, nullable=True)  # type: ignore[assignment]
    imported_at = Column(DateTime, server_default=func.now())


class AccountDailyValue(Base):
    """Daily total value for a single named account (Schwab or external).

    Populated by ``pmod portfolio backfill``.  Used for per-account
    performance charts without requiring live API calls on every render.
    """

    __tablename__ = "account_daily_values"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    account_name: str = Column(String(200), nullable=False, index=True)  # type: ignore[assignment]
    total_value: float = Column(Float, nullable=False)  # type: ignore[assignment]
    captured_at = Column(DateTime, nullable=False, index=True)


class PortfolioSnapshot(Base):
    """Daily snapshot of portfolio value for historical tracking."""

    __tablename__ = "portfolio_snapshots"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    total_value: float = Column(Float, nullable=False)  # type: ignore[assignment]
    cash_balance: float = Column(Float, nullable=False, default=0.0)  # type: ignore[assignment]
    day_pnl: float = Column(Float, nullable=True)  # type: ignore[assignment]
    num_positions: int = Column(Integer, nullable=True)  # type: ignore[assignment]
    captured_at = Column(DateTime, server_default=func.now())


class BenchmarkSnapshot(Base):
    """Daily snapshot of S&P 500 closing price for alpha calculation."""

    __tablename__ = "benchmark_snapshots"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    ticker: str = Column(String(10), nullable=False, default="SPY")  # type: ignore[assignment]
    close_price: float = Column(Float, nullable=False)  # type: ignore[assignment]
    captured_at = Column(DateTime, server_default=func.now())


class PoliticianSignal(Base):
    """Aggregated buy/sell signal derived from politician trading activity."""

    __tablename__ = "politician_signals"

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    ticker: str = Column(String(20), nullable=False, index=True)  # type: ignore[assignment]
    company_name: str = Column(String(300), nullable=True)  # type: ignore[assignment]
    signal: str = Column(  # type: ignore[assignment]
        Enum("strong_buy", "buy", "hold", "sell", name="politician_signal"),
        nullable=False,
    )
    confidence: float = Column(Float, nullable=False)  # 0.0–1.0
    buy_count: int = Column(Integer, nullable=False, default=0)  # type: ignore[assignment]
    sell_count: int = Column(Integer, nullable=False, default=0)  # type: ignore[assignment]
    unique_politicians: int = Column(Integer, nullable=False, default=0)  # type: ignore[assignment]
    rationale: str = Column(String(1000), nullable=True)  # type: ignore[assignment]
    generated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ClosingPrice(Base):
    """Cached daily closing prices for momentum/trend calculations."""

    __tablename__ = "closing_prices"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uix_cp_ticker_date"),
    )

    id: int = Column(Integer, primary_key=True, autoincrement=True)  # type: ignore[assignment]
    ticker: str = Column(String(20), nullable=False, index=True)  # type: ignore[assignment]
    date = Column(Date, nullable=False, index=True)
    close: float = Column(Float, nullable=False)  # type: ignore[assignment]
    cached_at = Column(DateTime, server_default=func.now())


@functools.lru_cache(maxsize=1)
def get_engine():  # type: ignore[no-untyped-def]
    """Return the cached SQLAlchemy engine, creating it on first call."""
    settings = get_settings()
    return create_engine(settings.database_url, echo=False)


@functools.lru_cache(maxsize=1)
def _get_session_factory():  # type: ignore[no-untyped-def]
    """Return a cached sessionmaker bound to the engine.

    Creating a new sessionmaker on every get_session() call is wasteful;
    the factory itself is stateless so it is safe to share.
    """
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def _run_migrations(engine) -> None:  # type: ignore[no-untyped-def]
    """Apply incremental schema changes to existing databases."""
    insp = inspect(engine)
    table_names = set(insp.get_table_names())

    with engine.connect() as conn:
        if "user_preferences" in table_names:
            existing = {c["name"] for c in insp.get_columns("user_preferences")}
            if "sector_focus" not in existing:
                conn.execute(text("ALTER TABLE user_preferences ADD COLUMN sector_focus TEXT DEFAULT '[]'"))

        if "politician_trades" in table_names:
            existing = {c["name"] for c in insp.get_columns("politician_trades")}
            if "report_url" not in existing:
                conn.execute(text("ALTER TABLE politician_trades ADD COLUMN report_url VARCHAR(500)"))

        if "closing_prices" in table_names:
            # Normalise date column from "YYYY-MM-DD HH:MM:SS" (old DateTime
            # storage) to "YYYY-MM-DD" so the Date type can parse it correctly.
            conn.execute(text("""
                UPDATE closing_prices
                SET date = substr(date, 1, 10)
                WHERE length(date) > 10
            """))
            # Remove duplicate (ticker, date) rows before creating the unique
            # index; keep the row with the highest id (most recently inserted).
            conn.execute(text("""
                DELETE FROM closing_prices
                WHERE id NOT IN (
                    SELECT MAX(id) FROM closing_prices GROUP BY ticker, date
                )
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uix_cp_ticker_date
                ON closing_prices (ticker, date)
            """))

        conn.commit()

    # external_accounts / external_positions created via create_all; no column migrations needed yet


def init_db() -> None:
    """Create all tables and run incremental migrations.

    Call once at process startup. Safe to call multiple times — SQLAlchemy
    only creates tables that don't already exist.
    """
    engine = get_engine()
    Base.metadata.create_all(engine)
    _run_migrations(engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Yield a database session with auto-commit / rollback / close.

    Usage::

        with get_session() as session:
            session.query(...)

    On normal exit the session is committed. On exception it is rolled
    back. In either case the session is closed.
    ``init_db()`` must be called at startup before any session is used.
    """
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
