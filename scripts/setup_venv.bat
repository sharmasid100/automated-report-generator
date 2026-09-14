@echo off
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-ci.txt -r requirements-dev.txt
python scripts/generate_sample_icsr.py
echo Environment ready. Activate with: .venv\Scripts\activate.bat
