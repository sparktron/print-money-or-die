"""SQLAlchemy models for local persistence."""

from sqlalchemy import Column, DateTime, Enum, Float, Integer, String, create_engine, func
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


def get_engine():  # type: ignore[no-untyped-def]
    """Create a SQLAlchemy engine from settings."""
    settings = get_settings()
    return create_engine(settings.database_url, echo=False)


def get_session() -> Session:
    """Return a new database session."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    return factory()
