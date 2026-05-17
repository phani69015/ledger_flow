# LedgerFlow

AI-powered ETL and analytics platform for processing financial transactions. Built with FastAPI and PostgreSQL, featuring automated ingestion pipelines, intelligent transaction categorization, and anomaly detection capable of handling 100K+ records.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        LedgerFlow API                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │  Auth    │    │  Ingestion   │    │    Analytics Engine    │  │
│  │  (JWT)   │    │  Pipeline    │    │                       │  │
│  └──────────┘    └──────┬───────┘    │  ┌─────────────────┐  │  │
│                         │            │  │ AI Categorizer  │  │  │
│                         ▼            │  │ (Keyword + Stat)│  │  │
│                  ┌──────────────┐    │  └─────────────────┘  │  │
│                  │  Validation  │    │                       │  │
│                  │  & Transform │    │  ┌─────────────────┐  │  │
│                  │  (Pandas)    │    │  │ Anomaly Detect  │  │  │
│                  └──────┬───────┘    │  │ (Z-Score + IQR) │  │  │
│                         │            │  └─────────────────┘  │  │
│                         ▼            └───────────────────────┘  │
│                  ┌──────────────┐                                │
│                  │ Deduplication│                                │
│                  └──────┬───────┘                                │
│                         │                                        │
├─────────────────────────┼────────────────────────────────────────┤
│                         ▼                                        │
│              ┌────────────────────┐                              │
│              │  PostgreSQL / SQLite │                             │
│              └────────────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **Web Dashboard** - Modern dark-themed UI with real-time charts and analytics
- **CSV/JSON Ingestion Pipelines** - Upload financial data with automated validation, transformation, and deduplication
- **AI Transaction Categorization** - Intelligent keyword-based categorization with confidence scoring across 11 categories
- **Anomaly Detection** - Z-Score and IQR-based detection for unusual transactions
- **Financial Analytics** - Spending summaries, category breakdowns, monthly trends, and anomaly reports
- **JWT Authentication** - Secure token-based auth with user isolation
- **REST API** - Full CRUD operations with filtering and pagination
- **Docker Ready** - Containerized deployment with PostgreSQL
- **Dual Database Support** - SQLite for local dev, PostgreSQL for production

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+, FastAPI |
| Frontend | HTML5, CSS3, JavaScript, Chart.js |
| Database | PostgreSQL (production), SQLite (development) |
| ORM | SQLAlchemy 2.0 |
| Data Processing | Pandas, NumPy |
| Authentication | JWT (python-jose), bcrypt |
| Containerization | Docker, Docker Compose |
| Testing | Pytest, HTTPx |

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/ledgerflow.git
cd ledgerflow

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run the application (uses SQLite by default - no DB setup needed)
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

- **Web Dashboard**: `http://localhost:8000` (main UI)
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Docker Deployment (PostgreSQL)

```bash
# Build and start services
docker-compose up --build

# Stop services
docker-compose down

# Stop and remove data volumes
docker-compose down -v
```

## Web Dashboard

The built-in web dashboard provides a complete financial analytics interface:

- **Login/Register** - Secure authentication with JWT tokens
- **Dashboard** - Real-time stats, income vs expense trend charts, and category breakdown (doughnut chart)
- **Transactions** - Sortable/filterable table of all transactions with category badges and anomaly flags
- **Upload** - Drag-and-drop file upload with instant processing feedback (records processed, anomalies detected, categories assigned)
- **Anomalies** - Visual anomaly report showing flagged transactions with severity scores and explanations

The UI is built with vanilla HTML/CSS/JS and Chart.js — no build step required.

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login and get JWT token |
| GET | `/api/v1/auth/me` | Get current user info |

### Transactions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/transactions/upload` | Upload CSV/JSON file |
| POST | `/api/v1/transactions/` | Create single transaction |
| GET | `/api/v1/transactions/` | List transactions (with filters) |
| GET | `/api/v1/transactions/{id}` | Get transaction by ID |
| PUT | `/api/v1/transactions/{id}` | Update transaction |
| DELETE | `/api/v1/transactions/{id}` | Delete transaction |
| POST | `/api/v1/transactions/detect-anomalies` | Trigger anomaly detection |

### Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/analytics/summary` | Overall financial summary |
| GET | `/api/v1/analytics/categories` | Category breakdown |
| GET | `/api/v1/analytics/anomalies` | Anomaly detection report |
| GET | `/api/v1/analytics/trends` | Monthly income/expense trends |

## Usage Examples

### 1. Register and Login

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "username": "user1", "password": "securepass123"}'

# Login (save the token)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass123"}' | jq -r '.access_token')
```

### 2. Upload Transactions

```bash
# Upload CSV file
curl -X POST http://localhost:8000/api/v1/transactions/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample_data/transactions.csv"

# Upload JSON file
curl -X POST http://localhost:8000/api/v1/transactions/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample_data/transactions.json"
```

### 3. View Analytics

```bash
# Get financial summary (last 30 days)
curl -X GET "http://localhost:8000/api/v1/analytics/summary?days=365" \
  -H "Authorization: Bearer $TOKEN"

# Get category breakdown
curl -X GET "http://localhost:8000/api/v1/analytics/categories?days=365" \
  -H "Authorization: Bearer $TOKEN"

# Get anomaly report
curl -X GET http://localhost:8000/api/v1/analytics/anomalies \
  -H "Authorization: Bearer $TOKEN"

# Get monthly trends
curl -X GET "http://localhost:8000/api/v1/analytics/trends?months=6" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Filter Transactions

```bash
# Get only anomalous transactions
curl -X GET "http://localhost:8000/api/v1/transactions/?anomalies_only=true" \
  -H "Authorization: Bearer $TOKEN"

# Filter by category
curl -X GET "http://localhost:8000/api/v1/transactions/?category=Food%20%26%20Dining" \
  -H "Authorization: Bearer $TOKEN"
```

## Sample Data

The `sample_data/` directory contains example files for testing:

- `transactions.csv` - 35 transactions including normal and anomalous entries
- `transactions.json` - 15 transactions in JSON format

These files include intentionally anomalous transactions (e.g., $12,000 and $25,000 transfers) to demonstrate the anomaly detection capability.

## AI Categorization

The categorization engine uses a hybrid approach:

1. **Keyword Matching** - Weighted keyword dictionary across 11 categories
2. **Pattern Matching** - Regex patterns for flexible text matching
3. **Confidence Scoring** - Sigmoid-normalized scoring with margin-based boosting

### Supported Categories
- Food & Dining
- Transportation
- Housing & Rent
- Utilities
- Shopping
- Salary & Income
- Entertainment
- Healthcare
- Education
- Transfers
- Investments

## Anomaly Detection

Two statistical methods are combined for robust detection:

1. **Z-Score Method** - Flags transactions with amounts >2.5 standard deviations from the mean
2. **IQR Method** - Uses interquartile range fences to detect statistical outliers

Results are combined with weighted scoring (60% Z-Score, 40% IQR) for a final anomaly determination.

## Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_auth.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing
```

## Project Structure

```
ledgerflow/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Environment-based configuration
│   ├── database.py          # SQLAlchemy engine & session
│   ├── models/
│   │   ├── user.py          # User ORM model
│   │   └── transaction.py   # Transaction ORM model
│   ├── schemas/
│   │   ├── user.py          # Auth request/response schemas
│   │   └── transaction.py   # Transaction & analytics schemas
│   ├── api/
│   │   ├── deps.py          # Auth dependencies
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── transactions.py  # Transaction CRUD & upload
│   │   └── analytics.py     # Analytics & insights endpoints
│   ├── services/
│   │   ├── ingestion.py     # CSV/JSON parsing & validation
│   │   ├── categorization.py # AI categorization engine
│   │   └── anomaly_detection.py # Statistical anomaly detection
│   └── utils/
│       └── security.py      # JWT & password utilities
├── static/
│   ├── index.html           # Web dashboard (single page app)
│   ├── css/style.css        # Dashboard styles
│   └── js/app.js            # Frontend logic & API client
├── tests/
│   ├── conftest.py          # Test fixtures & setup
│   ├── test_auth.py         # Authentication tests
│   ├── test_ingestion.py    # Ingestion & categorization tests
│   └── test_analytics.py    # Analytics endpoint tests
├── sample_data/
│   ├── transactions.csv     # Sample CSV data
│   └── transactions.json    # Sample JSON data
├── Dockerfile               # Multi-stage Docker build
├── docker-compose.yml       # Docker Compose with PostgreSQL
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./ledgerflow.db` | Database connection string |
| `SECRET_KEY` | `dev-secret-key...` | JWT signing secret |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token expiry (24 hours) |
| `DEBUG` | `true` | Enable debug mode |

## Performance

- Handles 100K+ transaction ingestion via batch processing
- Pandas-based ETL ensures efficient data transformation
- SQLAlchemy bulk operations for fast database writes
- Deduplication prevents redundant processing on re-uploads

## License

MIT
