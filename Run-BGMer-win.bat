@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title BGMer - Windows Launcher

rem ===== keep console open even on double-click =====
if /i "%~1"=="--console" goto CONT
start "" cmd /k "%~f0" --console
exit /b

:CONT
rem ===== config =====
set "VENV=.venv"
set "ENTRY=app.py"
set "DEBUG=1"   rem 1=show output on screen, 0=write to logs

rem ===== cd to script dir =====
cd /d "%~dp0"

rem ===== find Python (avoid WindowsApps dummy) =====
set "PYCMD="
where py >nul 2>nul
if %ERRORLEVEL%==0 set "PYCMD=py"
if defined PYCMD goto HAVE_PY
for /f "delims=" %%I in ('where python 2^>nul') do set "PYCMD=python"
if defined PYCMD goto HAVE_PY
echo [ERROR] No valid Python found. Install Python 3.11 x64 and Python Launcher py.exe
echo         Tip: turn OFF "App execution aliases" for Python.
goto END

:HAVE_PY
rem ===== create venv if missing =====
if exist "%VENV%\Scripts\python.exe" goto VENV_OK
echo [+] Creating venv: %VENV% ...
if /i "%PYCMD%"=="py" goto MAKE_VENV_PY
python -m venv "%VENV%"
if errorlevel 1 goto VENV_FAIL
goto VENV_OK

:MAKE_VENV_PY
py -3.12 -m venv "%VENV%" || py -3.11 -m venv "%VENV%" || py -m venv "%VENV%"
if errorlevel 1 goto VENV_FAIL

:VENV_OK
set "VENVSCRIPTS=%CD%\%VENV%\Scripts"
set "PY_EXE=%VENVSCRIPTS%\python.exe"
set "PIP_EXE=%VENVSCRIPTS%\pip.exe"

rem ===== pip upgrade =====
"%PY_EXE%" -m pip install -U pip setuptools wheel
if errorlevel 1 goto PIP_FAIL

rem ===== env (UTF-8 & gradio) =====
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "GRADIO_LAUNCH_BROWSER=1"
set "GRADIO_SERVER_PORT=7860"

rem ===== ensure torch (CPU) if missing =====
"%PY_EXE%" -c "import importlib; importlib.import_module('torch')" 1>nul 2>nul
if %ERRORLEVEL% NEQ 0 goto INSTALL_TORCH
goto AFTER_TORCH

:INSTALL_TORCH
echo [+] Installing PyTorch CPU...
"%PIP_EXE%" install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto TORCH_FAIL

:AFTER_TORCH
rem ===== install other deps (torch must NOT be in requirements.txt) =====
if exist requirements.txt goto HAS_REQ
echo [ERROR] requirements.txt not found in project root.
goto END

:HAS_REQ
"%PIP_EXE%" install -r requirements.txt
if errorlevel 1 goto REQ_FAIL

rem ===== ffmpeg warn (optional) =====
where ffmpeg >nul 2>nul
if %ERRORLEVEL% NEQ 0 echo [WARN] ffmpeg not found; audio mux needs it.

if not exist logs mkdir logs

rem ===== run app =====
echo [+] Launching...
if "%DEBUG%"=="1" goto RUN_FOREGROUND
"%PY_EXE%" -X utf8 "%ENTRY%" 1> "logs\app.out.txt" 2> "logs\app.err.txt"
goto AFTER_RUN

:RUN_FOREGROUND
"%PY_EXE%" -X utf8 "%ENTRY%"

:AFTER_RUN
echo [OK] exit code: %ERRORLEVEL%
goto END

:VENV_FAIL
echo [ERROR] venv creation failed. Reinstall Python 3.11 x64 or disable App execution aliases.
goto END

:PIP_FAIL
echo [ERROR] pip upgrade failed.
goto END

:TORCH_FAIL
echo [ERROR] PyTorch CPU install failed. Ensure torch is NOT in requirements.txt.
goto END

:REQ_FAIL
echo [ERROR] requirements install failed. See messages above.
goto END

:END
rem stays open because of --console
