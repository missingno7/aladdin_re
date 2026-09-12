@echo off
setlocal
pushd "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo Build the project first using the commands in README.md.
    popd
    exit /b 2
)
".venv\Scripts\python.exe" -m aladdin_sega play %*
set "playerExitCode=%ERRORLEVEL%"
popd
exit /b %playerExitCode%
