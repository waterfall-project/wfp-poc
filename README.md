# wfp-poc

Quickstart guide for local development.

## 1) Create `.env.development`

Copy the template and adjust values as needed:

```bash
cp .env.example .env.development
```

Important defaults:
- `DATABASE_URL=sqlite:///data/app.db`
- `JWT_SECRET_KEY` must be set (even for local use)
- `METRICS_API_KEY` must be set

## 2) Run with Docker Compose (recommended)

Spin up API, database, Guardian mock, Adminer, and Superset:

```bash
docker compose up -d --build
```

Useful URLs:
- API: http://127.0.0.1:5000
- Adminer: http://127.0.0.1:8080
- Superset: http://127.0.0.1:8088

## 3) Run the Guardian mock (local, without Docker)

Start the mock service on port 5001:

```bash
python tools/guardian_mock/app.py
```

Optional flags:
- `GUARDIAN_MOCK_DENY_ALL=true` to force access denied
- `GUARDIAN_MOCK_ECHO_REQUEST=true` to echo request payloads

Then ensure:
- `GUARDIAN_SERVICE_URL=http://localhost:5001`

## 4) CLI commands

Show current configuration:

```bash
FLASK_ENV=development FLASK_APP=wsgi.py flask config show
```

Validate configuration:

```bash
FLASK_ENV=development FLASK_APP=wsgi.py flask config validate
```

## 5) Database migrations

Initialize or update the database:

```bash
FLASK_ENV=development FLASK_APP=wsgi.py flask db upgrade
```

## 6) Run the service

Start the API server (loads `.env.development`):

```bash
FLASK_ENV=development python run.py
```

## 7) Run tests

```bash
pytest
```

## 8) Generate a JWT for local calls

```bash
JWT=$(python tools/generate_jwt.py --env-file .env.development)
```

Optional arguments: `--env-file`, `--user-id`, `--company-id`, `--email`,
`--expires-in`.

## 9) Postman collections

Postman collections are available in `docs/postman/collections/` with a local
environment in `docs/postman/environments/wfp-poc.local.postman_environment.json`.
Set `access_token` in the environment using a token generated above.

## 10) Main curl commands

Health and readiness:

```bash
curl -i http://127.0.0.1:5000/health
curl -i http://127.0.0.1:5000/ready
```

List projects (requires JWT):

```bash
curl -i -H "Authorization: Bearer $JWT" "http://127.0.0.1:5000/v0/projects?page=1&per_page=20"
```

Create a project:

```bash
curl -i -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"name":"Demo Project","code":"PRJ-001","start_date":"2025-01-01T09:00:00Z","finish_date":"2025-02-01T18:00:00Z","status":"active","currency_code":"EUR"}' \
  http://127.0.0.1:5000/v0/projects
```

Create an expense:

```bash
curl -i -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"date":"2025-04-25T00:00:00Z","amount":3820,"category":"procurement","description":"Procurement expense"}' \
  http://127.0.0.1:5000/v0/projects/<project_id>/expenses
```

List expenses:

```bash
curl -i -H "Authorization: Bearer $JWT" "http://127.0.0.1:5000/v0/projects/<project_id>/expenses?page=1&per_page=20"
```
