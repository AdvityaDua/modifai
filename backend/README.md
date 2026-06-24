# Modifai Backend

Backend API for the Modifai platform. Built with FastAPI, PostgreSQL (NeonDB), Celery, Redis, and Cloudflare R2.

## Setup

1. **Create Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Copy `.env.example` to `.env` and fill in the values.
   ```bash
   cp .env.example .env
   ```

4. **Run Database Migrations:**
   ```bash
   alembic upgrade head
   ```

## Running the Application

1. **Start FastAPI Server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

2. **Start Celery Worker (requires Redis):**
   ```bash
   celery -A app.worker.celery_app worker --loglevel=info
   ```

## API Documentation

Once the server is running, you can access the interactive API documentation at:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
