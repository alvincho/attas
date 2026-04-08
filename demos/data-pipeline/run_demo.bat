@echo off
setlocal

set "ROOT_DIR=%~dp0..\.."
pushd "%ROOT_DIR%" >nul || exit /b 1

where py >nul 2>&1
if not errorlevel 1 (
  py -3 -m scripts.demo_launcher data-pipeline %*
) else (
  python -m scripts.demo_launcher data-pipeline %*
)

set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
exit /b %EXIT_CODE%
