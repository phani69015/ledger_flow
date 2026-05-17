from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from app.config import get_settings
from app.database import create_tables
from app.api.auth import router as auth_router
from app.api.transactions import router as transactions_router
from app.api.analytics import router as analytics_router

settings = get_settings()

# Path to static files
STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup: Create database tables
    create_tables()
    print(f"[LedgerFlow] Database tables created successfully")
    print(f"[LedgerFlow] Using database: {settings.DATABASE_URL.split('://')[0]}")
    print(f"[LedgerFlow] UI available at: http://localhost:8000")
    print(f"[LedgerFlow] API docs at: http://localhost:8000/docs")
    yield
    # Shutdown
    print("[LedgerFlow] Shutting down...")


app = FastAPI(
    title="LedgerFlow",
    description=(
        "AI-powered ETL and analytics platform for financial transactions. "
        "Features automated ingestion pipelines, intelligent categorization, "
        "and anomaly detection for 100K+ transactions."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")

# Serve static files (CSS, JS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", tags=["UI"])
def serve_ui():
    """Serve the LedgerFlow web dashboard."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health", tags=["Health"])
def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": settings.DATABASE_URL.split("://")[0],
        "debug": settings.DEBUG,
    }
