# SkillOut

## Backend Setup

Run all backend commands from the project root:

`...\GitHub\SkillOut`

If an old virtual environment is active, deactivate it first:

```powershell
deactivate
```

Create a new virtual environment:

```powershell
python -m venv venv
```

Activate the virtual environment:

```powershell
venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Apply database migrations:

```powershell
python manage.py migrate
```

Start the Django development server:

```powershell
python manage.py runserver
```

For scraping to work in the backend, run

```
ollama pull llama3
```

## Notes

- `manage.py` is at the project root and should be used for all Django commands.
- `web_project` is the Django project configuration package.
- `hello` is the Django app where the application code and app-specific migrations live.
- If VS Code does not detect installed packages, select the interpreter from `venv\Scripts\python.exe`.
