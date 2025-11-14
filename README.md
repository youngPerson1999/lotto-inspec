# Lotto Insec Backend

FastAPI server that downloads Lotto draw data from DhLottery, exposes health/lotto endpoints, and enables statistical analysis.

## Getting Started

1. Create and activate a virtual environment (recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the server:

   ```bash
   uvicorn app.main:app --reload
   ```

4. Open http://localhost:8000/docs to use the interactive Swagger UI.  
   - `GET /lotto/latest` fetches the newest Lotto draw (currently up to the 1197th draw on Nov 15, 2025) and returns the winning numbers plus bonus ball.  
   - `GET /lotto/{draw_no}` fetches a specific 회차 (e.g., `GET /lotto/1197`).  
   - `POST /lotto/sync` downloads any missing draws (e.g., 1001~1197) and appends them to `data/lotto_draws.json`, returning a summary of what was added.

## Project Layout

- `crawler.py` – shared crawling helpers.
- `app/main.py` – FastAPI application exposing the `/lotto/latest`, `/lotto/{draw_no}`, `/lotto/sync`, and health check endpoints.
- `app/schemas.py` – shared Pydantic models used by the FastAPI routes.
- `lottery.py` – DhLottery-specific helpers that discover the latest draw metadata, fetch any specific draw, synchronize local storage, and load persisted data for analysis.
- `analysis.py` – statistical utilities (chi-square test, runs test, gap histogram) built on top of the locally stored draws for investigating anomalies.
- `data/lotto_draws.json` – populated on demand; stores draw history retrieved via the sync endpoint.
- `requirements.txt` – runtime dependencies.
