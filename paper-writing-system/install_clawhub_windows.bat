@echo off
setlocal
set SCRIPT_DIR=%~dp0
python "%SCRIPT_DIR%scripts\install_openclaw.py" %*
endlocal
