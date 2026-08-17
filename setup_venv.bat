@echo off
setlocal

echo ============================================================
echo PADER Safety Reporting Project - Virtual Environment Setup
echo ============================================================
echo.

REM Move to the directory containing this script
cd /d "%~dp0"

REM ------------------------------------------------------------
REM Check for Python
REM ------------------------------------------------------------
python --version >nul 2>&1

if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    echo.
    echo Install Python 3.11+ and make sure "Add Python to PATH"
    echo is enabled during installation.
    pause
    exit /b 1
)

echo Python detected:
python --version
echo.

REM ------------------------------------------------------------
REM Create virtual environment
REM ------------------------------------------------------------
if exist ".venv" (
    echo Existing .venv found.
    echo Reusing the existing virtual environment.
) else (
    echo Creating virtual environment...
    python -m venv .venv

    if errorlevel 1 (
        echo ERROR: Failed to create the virtual environment.
        pause
        exit /b 1
    )

    echo Virtual environment created successfully.
)

echo.

REM ------------------------------------------------------------
REM Upgrade pip
REM ------------------------------------------------------------
echo Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel

if errorlevel 1 (
    echo ERROR: Failed to upgrade pip.
    pause
    exit /b 1
)

echo.

REM ------------------------------------------------------------
REM Install project dependencies
REM ------------------------------------------------------------
echo Installing project dependencies...
echo This may take several minutes because PyTorch and
echo Hugging Face Transformers are included.
echo.

".venv\Scripts\python.exe" -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    echo.
    echo Try running:
    echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo.

REM ------------------------------------------------------------
REM Verify important packages
REM ------------------------------------------------------------
echo ============================================================
echo Verifying installation
echo ============================================================
echo.

".venv\Scripts\python.exe" -c "import pandas; print('pandas        :', pandas.__version__)"
".venv\Scripts\python.exe" -c "import numpy; print('numpy         :', numpy.__version__)"
".venv\Scripts\python.exe" -c "import openpyxl; print('openpyxl      :', openpyxl.__version__)"
".venv\Scripts\python.exe" -c "import torch; print('torch         :', torch.__version__)"
".venv\Scripts\python.exe" -c "import transformers; print('transformers  :', transformers.__version__)"
".venv\Scripts\python.exe" -c "import sentencepiece; print('sentencepiece : installed')"

if errorlevel 1 (
    echo.
    echo WARNING: One or more package verification checks failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo SETUP COMPLETE
echo ============================================================
echo.
echo To activate the environment manually:
echo.
echo     .venv\Scripts\activate
echo.
echo Then run the pipeline with:
echo.
echo     python src\main.py
echo.
echo To deactivate:
echo.
echo     deactivate
echo.
pause
endlocal
