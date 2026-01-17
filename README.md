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

## 2) Run the Guardian mock (local)

Start the mock service on port 5001:

```bash
python tools/guardian_mock/app.py
```

Optional flags:
- `GUARDIAN_MOCK_DENY_ALL=true` to force access denied
- `GUARDIAN_MOCK_ECHO_REQUEST=true` to echo request payloads

Then ensure:
- `GUARDIAN_SERVICE_URL=http://localhost:5001`

## 3) CLI commands

Show current configuration:

```bash
FLASK_ENV=development FLASK_APP=wsgi.py flask config show
```

Validate configuration:

```bash
FLASK_ENV=development FLASK_APP=wsgi.py flask config validate
```

## 4) Database migrations

Initialize or update the database:

```bash
FLASK_ENV=development FLASK_APP=wsgi.py flask db upgrade
```

## 5) Run the service

Start the API server (loads `.env.development`):

```bash
FLASK_ENV=development python run.py
```

## 6) Run tests

```bash
pytest
```

## 7) Generate a JWT for local calls

```bash
JWT=$(python -c "import time,uuid; from pathlib import Path; import jwt; env={}; [env.update({k:v}) for k,v in (line.split('=',1) for line in Path('.env.development').read_text().splitlines() if line and not line.lstrip().startswith('#') and '=' in line)]; secret=env.get('JWT_SECRET_KEY'); alg=env.get('JWT_ALGORITHM','HS256'); payload={'user_id':str(uuid.uuid4()),'company_id':str(uuid.uuid4()),'email':'user@example.com','exp':int(time.time())+3600}; print(jwt.encode(payload, secret, algorithm=alg))")
```

## 8) Main curl commands

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
