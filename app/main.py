from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import get_settings
from app.database import create_tables
from app.api.auth import router as auth_router
from app.api.transactions import router as transactions_router
from app.api.analytics import router as analytics_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup: Create database tables
    create_tables()
    print(f"[LedgerFlow] Database tables created successfully")
    print(f"[LedgerFlow] Using database: {settings.DATABASE_URL.split('://')[0]}")
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

# Include routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root():
    """Health check endpoint."""
    return {
        "service": "LedgerFlow",
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": settings.DATABASE_URL.split("://")[0],
        "debug": settings.DEBUG,
    }
