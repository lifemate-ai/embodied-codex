@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
  echo toio-mcp HTTP launcher could not find "%PYTHON_EXE%". 1>&2
  echo Run "uv sync --extra dev" in the toio-mcp directory first. 1>&2
  exit /b 1
)

"%PYTHON_EXE%" -m toio_mcp.server --transport http --host 0.0.0.0 --port 8766
exit /b %ERRORLEVEL%
