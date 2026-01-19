# poc-import - MS Project and Excel Import Service

ETL service for importing project data from MS Project XML files and Excel spreadsheets into the wfp-poc REST API.

## Features

- Parse MS Project 2010+ XML files (projects, tasks, milestones, resources, assignments)
- Parse Excel files for expenses and RAE data
- Validate data integrity before import
- Support initial import and incremental sync modes
- Mock-friendly for testing without live API

## Installation

```bash
cd tools/poc-import
pip install -e ".[dev]"
```

## Usage

You can run via the installed CLI or the local wrapper to start the interactive
shell:

```bash
./tools/poc-import/poc-import.py
```

```bash
poc-import
```

### Import MS Project XML (Initial)

```bash
poc-import msproject path/to/your/project.xml \
  --mode=initial \
  --token=$WFP_JWT_TOKEN \
  --api-url=http://localhost:5000 \
  --verbose
```

### Import MS Project XML (Sync)

```bash
poc-import msproject path/to/your/project.xml \
  --mode=sync \
  --project-id=<project-uuid> \
  --token=$WFP_JWT_TOKEN \
  --api-url=http://localhost:5000
```

### Dry Run (Validation Only)

```bash
poc-import msproject path/to/your/project.xml \
  --mode=initial \
  --token=$WFP_JWT_TOKEN \
  --api-url=http://localhost:5000 \
  --dry-run
```

### Excel Imports (Scaffolded)

```bash
poc-import
> excel expenses ./expenses.xlsx --project-id <project-uuid>
> excel rae ./rae.xlsx --project-id <project-uuid>
```

## Environment Variables

- `WFP_JWT_TOKEN` - JWT authentication token
- `WFP_API_URL` - wfp-poc API base URL (default: http://localhost:5000)
- `WFP_USER_ID` / `WFP_COMPANY_ID` - IDs used for local JWT generation
- `JWT_SECRET_KEY` / `JWT_ALGORITHM` / `JWT_ACCESS_TOKEN_EXPIRES` - JWT settings

Local defaults are provided in `.env.example`.

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=poc_import --cov-report=html

# Format code
ruff format .

# Lint
ruff check .

# Type check
mypy poc_import
```

## Architecture

```
src/
  poc_import/
    cli.py                 # Click CLI entry point
    config.py              # Configuration management
    models.py              # Pydantic data models
    validators.py          # Business rule validators
    parsers/
      msproject.py         # MS Project XML parser
      excel.py             # Excel parser
    api/
      client.py            # wfp-poc API client with retry logic
      schemas.py           # API request/response schemas
tests/
  test_msproject_parser.py
  test_cli.py
  test_validators.py
  fixtures/              # Sample XML/Excel files for testing
```

## Testing

Tests use pytest with mocking for API calls:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_msproject_parser.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=poc_import --cov-report=term-missing
```

## License

Commercial License - See LICENSE file
