PYTHON := python
VENV_DIR := .venv
DIST_ZIP := skillout-dist.zip

ifeq ($(OS),Windows_NT)
VENV_PY := $(VENV_DIR)\Scripts\python.exe
VENV_PIP := $(VENV_DIR)\Scripts\pip.exe
else
VENV_PY := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
endif

.PHONY: help venv install migrate build dist run test lint clean

help:
	@echo Available backend targets:
	@echo   make venv     - Create Python virtual environment
	@echo   make install  - Install backend dependencies
	@echo   make migrate  - Apply Django migrations
	@echo   make dist     - Create distributable zip package
	@echo   make build    - Full backend build (venv + deps + migrate + zip)
	@echo   make run      - Run Django development server
	@echo   make test     - Run backend tests with pytest
	@echo   make lint     - Run Django system checks
	@echo   make clean    - Remove local build artifacts

venv:
	$(PYTHON) -m venv $(VENV_DIR)

install: venv
	$(VENV_PIP) install -r requirements.txt

migrate: install
	$(VENV_PY) manage.py migrate

dist: migrate
	$(VENV_PY) -c "import zipfile,os,pathlib; src_dirs=['web_project','hello']; src_files=['manage.py','requirements.txt','Makefile','pytest.ini']; z=zipfile.ZipFile('$(DIST_ZIP)','w',zipfile.ZIP_DEFLATED); [z.write(f) for f in src_files if os.path.isfile(f)]; [z.write(str(p),str(p)) for d in src_dirs if os.path.exists(d) for p in pathlib.Path(d).rglob('*') if p.is_file() and '__pycache__' not in p.parts and not str(p).endswith('.pyc')]; z.close(); print('Created $(DIST_ZIP)')"

build: dist

run: install
	$(VENV_PY) manage.py runserver

test: install
	$(VENV_PY) -m pytest

lint: install
	$(VENV_PY) manage.py check

clean:
	$(PYTHON) -c "import shutil,os; [shutil.rmtree(p, ignore_errors=True) for p in ['$(VENV_DIR)', '.pytest_cache']]; os.path.isfile('$(DIST_ZIP)') and os.remove('$(DIST_ZIP)')"
