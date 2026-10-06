import os
import logging
from typing import Generator, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import SQLAlchemyError

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Determine effective database URL with graceful SQLite fallback
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

is_placeholder_url = "<password>" in db_url or "<host>" in db_url

local_db_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "license_intelligence.db"
)
os.makedirs(os.path.dirname(local_db_path), exist_ok=True)
sqlite_fallback_url = f"sqlite:///{local_db_path}"

# Attempt to connect to PostgreSQL if configured; otherwise use SQLite
db_type = "postgresql"
if is_placeholder_url or not db_url or "sqlite" in db_url.lower():
    db_url = sqlite_fallback_url
    db_type = "sqlite"

try:
    if "postgresql" in db_url:
        engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"connect_timeout": 4},
        )
        # Test connection immediately
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_type = "postgresql"
    else:
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
        )
        db_type = "sqlite"
except Exception as e:
    logger.warning(f"Primary PostgreSQL connection failed ({e}). Falling back to local SQLite at {local_db_path}")
    db_url = sqlite_fallback_url
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    db_type = "sqlite"

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> Dict[str, Any]:
    """
    Test the database connectivity.
    Returns a status dictionary indicating database engine status.
    """
    if engine is None:
        return {
            "connected": False,
            "status": "unconfigured",
            "db_type": "none",
            "message": "Database engine is unconfigured."
        }

    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            if result == 1:
                return {
                    "connected": True,
                    "status": "connected",
                    "db_type": db_type,
                    "url": "postgresql://***" if db_type == "postgresql" else f"sqlite:///{local_db_path}",
                    "message": f"{db_type.capitalize()} database is reachable and operational."
                }
            return {
                "connected": False,
                "status": "unexpected_result",
                "db_type": db_type,
                "message": f"Unexpected response from database query: {result}"
            }
    except SQLAlchemyError as exc:
        logger.warning(f"Database connection check failed: {exc}")
        return {
            "connected": False,
            "status": "unreachable",
            "db_type": db_type,
            "message": f"Failed to connect to database: {str(exc)}"
        }
    except Exception as exc:
        logger.error(f"Unexpected error during database check: {exc}")
        return {
            "connected": False,
            "status": "error",
            "message": f"Unexpected error: {str(exc)}"
        }
