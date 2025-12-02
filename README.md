# Lotto Insec Backend

FastAPI server that downloads Lotto draw data from DhLottery, exposes health/lotto endpoints, and enables statistical analysis.  
The repo now ships with a production-ready layout for Docker/Koyeb deployments.

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

4. Open http://localhost:8000/docs to use the interactive Swagger UI. GET 분석 엔드포인트는 MariaDB에 저장된 최신 스냅샷만 조회하며, POST 요청을 보내야 새 분석을 실행하고 저장합니다.  
   - `GET /lotto/latest` fetches the newest Lotto draw (currently up to the 1197th draw on Nov 15, 2025) and returns the winning numbers plus bonus ball.  
   - `GET /lotto/{draw_no}` fetches a specific 회차 (e.g., `GET /lotto/1197`).  
   - `POST /lotto/sync` downloads any missing draws (e.g., 1001~1197) and appends them to `data/lotto_draws.json`, returning a summary of what was added.
   - `GET /analysis` summarizes locally stored draws (chi-square, runs test, frequency tables, gap histogram). Use `/lotto/sync` first to hydrate storage.
   - `GET /analysis/dependency` runs 시계열 자기상관 + 직전 회차 재등장 확률 비교로 회차 간 의존성이 있는지 검정합니다.
   - `GET /analysis/runs/sum` tests whether 회차 합계가 중앙값 기준으로 너무 오래 한쪽에 머무는지 (런 검정).
   - `GET /analysis/patterns` checks 홀짝/저고/끝자리 분포가 이론적 확률과 일치하는지 χ² 검정.
   - `POST /analysis/distribution` compares 합계/간격 분포 전체가 시뮬레이션한 이상적 분포와 얼마나 차이나는지를 χ² + KS 통계로 보여줍니다 (계산 비용 때문에 POST 전용).
   - `GET /analysis/randomness` runs a lightweight NIST-style randomness suite on 비트열 인코딩(번호 존재 여부/이진 표현 등) 후 각 검정의 p-value를 제공합니다. (POST로 재계산 가능)
   - `GET /recommendations?strategy=frequency_hot` 등으로 랜덤/분석 기반 추천 조합을 받을 수 있습니다 (`random`, `frequency_hot`, `frequency_cold`, `balanced_parity` 지원).
   - `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`로 JWT 기반 로그인/토큰 갱신을 사용할 수 있습니다. (MariaDB 필수)

## Running with Docker

Build and run the container locally:

```bash
docker build -t lotto-insec .
docker run --rm -p 8000:8000 \
  --env-file .env \
  lotto-insec
```

The API will be available at http://localhost:8000.  
Set `LOTTO_DATA_DIR` (inside `.env`) to a mounted volume if you need the synchronized draws to persist across container restarts.

## Deploying to Koyeb

1. Install the [Koyeb CLI](https://www.koyeb.com/docs/cli/installation) and authenticate.
2. Review `koyeb.yaml` and optionally tweak the region, autoscaling, or env vars.
3. Deploy:
   ```bash
   koyeb service deploy \
     --app lotto-insec \
     --name lotto-api \
     --manifest ./koyeb.yaml
   ```
   Koyeb will build the Docker image using the provided `Dockerfile` and expose the service through its HTTPS edge.
4. The default manifest stores synced results in `/var/cache/lotto`. Attach a persistent volume if you need durable history between deployments.

## Configuration

| Variable                | Default                 | Description                                                                                |
| ----------------------- | ----------------------- | ------------------------------------------------------------------------------------------ |
| `LOTTO_DATA_DIR`        | `data`                  | Directory where synced draws are stored.                                                   |
| `LOTTO_RESULT_URL`      | DhLottery `byWin` page  | Override target HTML page for scraping the latest draw number.                             |
| `LOTTO_JSON_URL`        | DhLottery JSON endpoint | Override API base for individual draw metadata.                                            |
| `LOTTO_USER_AGENT`      | `lotto-insec/1.0 (...)` | Custom User-Agent header for outbound requests.                                            |
| `LOTTO_REQUEST_TIMEOUT` | `10` seconds            | Default HTTP timeout used by the crawler.                                                  |
| `LOTTO_ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated list of Origins allowed via CORS.                                          |
| `LOTTO_STORAGE_BACKEND` | `file`                  | Set to `mariadb` to persist draws in MariaDB instead of `data/lotto_draws.json`.           |
| `MARIADB_HOST`          | `127.0.0.1`             | MariaDB hostname (set to `localhost` when running locally).                                |
| `MARIADB_PORT`          | `3306`                  | MariaDB port.                                                                              |
| `MARIADB_USER`          | `lotto`                 | MariaDB user with privileges on the target database.                                       |
| `MARIADB_PASSWORD`      | _(unset)_               | Password for `MARIADB_USER`.                                                               |
| `MARIADB_DB_NAME`       | `lotto_insec`           | MariaDB database used for draws, analysis snapshots, auth, and recommendations.            |
| `JWT_SECRET_KEY` | `change-me` | JWT 서명 비밀 키 (프로덕션에서는 안전한 값으로 변경). |
| `JWT_ALGORITHM` | `HS256` | JWT 서명 알고리즘. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access Token 만료 시간(분). |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `14` | Refresh Token 만료 시간(일). |
| `PORT`                  | `8000`                  | Honored by the Dockerfile/Procfile for platforms that inject a port (Koyeb, Render, etc.). |

### Using MariaDB for draw storage

1. Provision a MariaDB instance (e.g., `brew install mariadb` + `brew services start mariadb`) and create the target database/user:

   ```sql
   CREATE DATABASE lotto_insec CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'lotto'@'%' IDENTIFIED BY 'super-secret';
   GRANT ALL PRIVILEGES ON lotto_insec.* TO 'lotto'@'%';
   FLUSH PRIVILEGES;
   ```

2. Create a `.env` file (already git-ignored) with the connection details:

   ```bash
   LOTTO_STORAGE_BACKEND=mariadb
   MARIADB_HOST=127.0.0.1
   MARIADB_PORT=3306
   MARIADB_USER=lotto
   MARIADB_PASSWORD=super-secret
   MARIADB_DB_NAME=lotto_insec
   ```

3. Export the variables before starting the server locally (or pass them through Docker/Koyeb):

   ```bash
   set -a
   source .env
   set +a
   uvicorn app.main:app --reload
   ```

With the MariaDB backend enabled, `/lotto/sync` upserts draws into SQL tables while `/analysis`, `/auth`, `/recommendations`, and `/lotto/tickets` query the same database.

## Project Layout

- `app/api/routes.py` – master router that includes each category router.
- `app/api/routes_system.py` – system endpoints (health, diagnostics).
- `app/api/routes_lotto.py` – Lotto data retrieval and sync endpoints.
- `app/api/routes_analysis.py` – statistical summaries over stored draws.
- `app/core/config.py` – environment-driven settings (paths, endpoints, user agent).
- `app/core/http_client.py` – shared HTTP helper built on requests.
- `app/services/lotto.py` – DhLottery-specific helpers that crawl/sync data.
- `app/main.py` – FastAPI application, includes routers and metadata.
- `app/schemas.py` – shared Pydantic models (`HealthResponse`, `Lotto*` DTOs).
- `analysis.py` – statistical utilities (chi-square test, runs test, gap histogram) built on top of the locally stored draws.
- `data/` – populated on demand; stores draw history retrieved via the sync endpoint.
- `Dockerfile`, `.dockerignore`, `Procfile`, `koyeb.yaml` – deployment assets for container platforms/Koyeb.
- `requirements.txt` – runtime dependencies.
