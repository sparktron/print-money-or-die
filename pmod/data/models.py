"""SQLAlchemy models for local persistence."""

import functools

from sqlalchemy import Column, DateTime, Enum, Float, Integer, String, Text, create_engine, func, inspect, text
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
    transaction_date: DateTime = Column(DateTime, nullable=True)  # type: ignore[assignment]
    disclosure_date: DateTime = Column(DateTime, nullable=False)  # type: ignore[assignment]
    amount_low: int = Column(Integer, nullable=True)  # type: ignore[assignment]
    amount_high: int = Column(Integer, nullable=True)  # type: ignore[assignment]
    report_url: str = Column(String(500), nullable=True)  # type: ignore[assignment]
    fetched_at = Column(DateTime, server_default=func.now())


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


@functools.lru_cache(maxsize=1)
def get_engine():  # type: ignore[no-untyped-def]
    """Return the cached SQLAlchemy engine, creating it on first call."""
    settings = get_settings()
    return create_engine(settings.database_url, echo=False)


def _run_migrations(engine) -> None:  # type: ignore[no-untyped-def]
    """Apply incremental schema changes to existing databases."""
    insp = inspect(engine)
    if "user_preferences" in insp.get_table_names():
        existing = {c["name"] for c in insp.get_columns("user_preferences")}
        with engine.connect() as conn:
            if "sector_focus" not in existing:
                conn.execute(text("ALTER TABLE user_preferences ADD COLUMN sector_focus TEXT DEFAULT '[]'"))
                conn.commit()

    if "politician_trades" in insp.get_table_names():
        existing = {c["name"] for c in insp.get_columns("politician_trades")}
        with engine.connect() as conn:
            if "report_url" not in existing:
                conn.execute(text("ALTER TABLE politician_trades ADD COLUMN report_url VARCHAR(500)"))
                conn.commit()


def init_db() -> None:
    """Create all tables and run incremental migrations.

    Call once at process startup. Safe to call multiple times — SQLAlchemy
    only creates tables that don't already exist.
    """
    engine = get_engine()
    Base.metadata.create_all(engine)
    _run_migrations(engine)


def get_session() -> Session:
    """Return a new database session.

    Callers are responsible for closing the session (use a try/finally or
    context manager). ``init_db()`` must be called at startup before any
    session is used.
    """
    factory = sessionmaker(bind=get_engine())
    return factory()
