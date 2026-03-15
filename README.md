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
```

Frontend:

```powershell
cd frontend
npm run dev
npm run build
npm run serve
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
