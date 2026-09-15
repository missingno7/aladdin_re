@echo off
setlocal
pushd "%~dp0" || exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo Build the project first using the commands in README.md.
    popd
    exit /b 2
)
if not exist "build\libaladdin_native.dll" (
    echo Build the native DLL first using the commands in README.md ^(the sound driver needs it^).
    popd
    exit /b 2
)
if defined PYTHONPATH (
    set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%CD%\src"
)
set "ALADDIN_NATIVE_LIBRARY=%CD%\build\libaladdin_native.dll"
".venv\Scripts\python.exe" scripts\play_native.py %*
set "playerExitCode=%ERRORLEVEL%"
popd
exit /b %playerExitCode%
