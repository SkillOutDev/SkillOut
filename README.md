# SkillOut

SkillOut is a full-stack app with:

- Django backend API (port `8000`)
- Vue + Vite frontend (port `5173`)
- SQLite database (`db.sqlite3`)
- Web scraping + subject extraction flow that uses Ollama (`llama3`)

## Project Structure

- `web_project/` - Django project settings and root URLs
- `hello/` - Main Django app (API endpoints and models)
- `frontend/` - Vue client app
- `scraped_text/` - Output files from scraping (`latest_scrape.txt`, `latest_subjects.json`)

## Prerequisites

Install these before running:

1. Python 3.11+ (recommended)
2. Node.js 18+ and npm
3. Ollama (required for `/api/scrape-text/` extraction)

## 1) Backend Setup (Django)

Run from the repository root:

```powershell
cd C:\Users\legat\Desktop\SkillOut
```

Create and activate virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install Python dependencies:

```powershell
pip install -r requirements.txt
```

Run migrations:

```powershell
python manage.py migrate
```

Start backend server:

```powershell
python manage.py runserver
```

Backend will be available at:

- `http://127.0.0.1:8000/`

## 2) Frontend Setup (Vue + Vite)

Open a second terminal, then:

```powershell
cd C:\Users\legat\Desktop\SkillOut\frontend
npm install
npm run dev
```

Frontend will be available at:

- `http://localhost:5173/`

Notes:

- Vite proxy is configured so requests to `/api/*` are forwarded to `http://localhost:8000`.
- Keep both backend and frontend servers running during development.

## 3) Ollama Setup (Required for Subject Extraction)

The endpoint `/api/scrape-text/` calls Ollama with model `llama3`.

Install the Python package in your venv:

```powershell
pip install ollama
```

Install and run Ollama desktop/app on your machine, then pull the model:

```powershell
ollama pull llama3
```

Quick health check:

```powershell
ollama list
```

If Ollama is not running or `llama3` is unavailable, scraping requests will fail.

## How to Use the App

1. Open `http://localhost:5173/`
2. Enter a study programme URL
3. Select semester range (`fromSemester` and `toSemester`, valid 1-8)
4. Submit
5. App navigates to `/subjects` and shows extracted subjects

Generated files are saved in:

- `scraped_text/latest_scrape.txt`
- `scraped_text/latest_subjects.json`

## Useful Commands

Backend:

```powershell
python manage.py runserver
python manage.py test
pytest
pytest --cov=hello --cov-report=term-missing
```

Frontend:

```powershell
cd frontend
npm run dev
npm run build
npm run serve
```

Testing:

```powershell
# Django tests
python manage.py test

# Cypress (install once in project root)
npm install

# Open Cypress UI
npx cypress open

# Run all Cypress E2E tests (headless)
npx cypress run

# Run SD-68 spec only
npx cypress run --spec "cypress/e2e/sd-68-events.cy.js"
```

## 4) Testing Setup (Django + Cypress)

This project currently uses:

- Django unit/integration tests via `python manage.py test`
- Cypress end-to-end UI tests from `cypress/e2e/`

### Backend Tests (Django)

Run from repository root with venv activated:

```powershell
python manage.py test
```

### UI Tests (Cypress + Vue)

1. Install Cypress dependencies in repository root (once):

```powershell
cd C:\Users\legat\Desktop\SkillOut
npm install
```

2. Start frontend dev server in a separate terminal:

```powershell
cd C:\Users\legat\Desktop\SkillOut\frontend
npm run dev
```

3. Run Cypress from repository root:

```powershell
cd C:\Users\legat\Desktop\SkillOut
npx cypress open
```

or headless:

```powershell
npx cypress run
```

Run only SD-68 events test:

```powershell
npx cypress run --spec "cypress/e2e/sd-68-events.cy.js"
```

### Port Note for Cypress

Cypress baseUrl is set to `http://localhost:5173` in `cypress.config.js`.

If Vite starts on a different port (for example `5174`), run Cypress with an override:

```powershell
npx cypress run --spec "cypress/e2e/sd-68-events.cy.js" --config baseUrl=http://localhost:5174
```

## API Endpoints

Base URL: `http://127.0.0.1:8000`

- `GET /` - health/home response
- `POST /api/scrape-text/` - scrape URL and extract subjects with semester filtering
- `GET /api/get-latest-subjects/` - return latest extracted subjects JSON
- `POST /add-student/`
- `POST /add-category/`
- `POST /add-subject/`
- `POST /add-interest/`
- `GET /student/<student_id>/subjects/`

## Troubleshooting

### `ModuleNotFoundError` or missing packages

Make sure venv is active, then reinstall:

```powershell
pip install -r requirements.txt
pip install ollama
```

### `Only POST is allowed` on `/api/scrape-text/`

That endpoint accepts `POST` requests only.

### `fromSemester and toSemester must be at most 8`

Valid semester values are integers from 1 to 8.

### Frontend cannot reach backend

Confirm:

1. Django is running on `:8000`
2. Vite is running on `:5173`
3. You are opening the app through Vite URL (`http://localhost:5173`), not backend URL

### `File not found` for latest subjects

This means no successful scrape has been completed yet. Submit a valid URL first.

## Automated Testing with Pytest

Pytest is configured for Django through `pytest.ini`.

Run all backend tests:

```powershell
pytest
```

Run only tests for one requirement example (semester range validation):

```powershell
pytest hello/test_requirement_semester_range.py
```

Run with coverage:

```powershell
pytest --cov=hello --cov-report=term-missing
```

CI automation:

- GitHub Actions workflow is added at `.github/workflows/backend-tests.yml`.
- It runs automatically on pushes and pull requests to `main` or `master`.
