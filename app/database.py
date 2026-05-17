from pathlib import Path
import os
import subprocess
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import get_settings

settings = get_settings()

# For SQLite, resolve relative paths to the project root directory
database_url = settings.DATABASE_URL
if database_url.startswith("sqlite:///./"):
    # Convert relative path to absolute path based on project root
    db_filename = database_url.replace("sqlite:///./", "")
    project_root = Path(__file__).parent.parent
    db_path = project_root / db_filename

    # Ensure the database file exists and is writable
    # macOS com.apple.provenance attribute can block SQLite writes
    if not db_path.exists():
        db_path.touch()
    # Clear any extended attributes that might block writes (macOS)
    subprocess.run(["xattr", "-c", str(db_path)], capture_output=True)
    os.chmod(str(db_path), 0o666)

    database_url = f"sqlite:///{db_path}"

# Handle SQLite vs PostgreSQL connection args
connect_args = {}
if database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    database_url,
    connect_args=connect_args,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def get_db():
    """Dependency that provides a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    # Import models to ensure they are registered with Base.metadata
    from app.models.user import User  # noqa: F401
    from app.models.transaction import Transaction  # noqa: F401
    Base.metadata.create_all(bind=engine)
