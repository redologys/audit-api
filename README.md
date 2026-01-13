# Audit API

Business Digital Presence Audit API powered by FastAPI and Groq LLM.

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/redologys/audit-api.git
cd audit-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example config/.env

# Edit config/.env with your API keys
```

### Running Locally

```bash
python main.py
```

Server starts at `http://localhost:8000`

API docs available at `http://localhost:8000/docs`

## Environment Variables

| Variable            | Description                     | Required     |
| ------------------- | ------------------------------- | ------------ |
| `GROQ_API_KEY`      | Groq API key for LLM            | Yes          |
| `STRIPE_SECRET_KEY` | Stripe secret key               | For payments |
| `STRIPE_PRICE_ID`   | Stripe price ID for full report | For payments |
| `SUPABASE_URL`      | Supabase project URL            | Yes          |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (server-side) | Yes |
| `LOGIC_TEST_MODE`   | Set to `true` for mock data     | No           |

## API Endpoints

| Method | Endpoint                     | Description               |
| ------ | ---------------------------- | ------------------------- |
| POST   | `/api/audit`                 | Create new business audit |
| GET    | `/api/audit/{id}`            | Get audit by ID           |
| POST   | `/api/generate-report`       | Generate PDF report       |
| POST   | `/api/create-payment-intent` | Create Stripe payment     |
| POST   | `/api/confirm-payment`       | Confirm payment           |

## Deployment

### Railway

1. Connect GitHub repository
2. Set environment variables in Railway dashboard
3. Railway auto-deploys on push

### Docker

```bash
docker build -t audit-api .
docker run -p 8000:8000 --env-file .env audit-api
```

## License

MIT
