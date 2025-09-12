@echo off
setlocal

rem Resolve project root (one level up from this scripts directory)
pushd "%~dp0\.."
set "PROJECT_ROOT=%CD%"

rem Activate virtualenv (adjust if your venv path differs)
if exist "%PROJECT_ROOT%\.venv\Scripts\activate.bat" (
  call "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
) else (
  echo Virtualenv activation script not found at "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
  echo Ensure you created a venv or update this batch file to point at your environment.
)

rem Ensure PYTHONPATH is set so scripts can import app package
set "PYTHONPATH=%PROJECT_ROOT%"

rem Ensure reports and logs directories exist
if not exist "%PROJECT_ROOT%\data\reports" mkdir "%PROJECT_ROOT%\data\reports"
if not exist "%PROJECT_ROOT%\logs" mkdir "%PROJECT_ROOT%\logs"

rem Format date as YYYY-MM-DD using PowerShell (works reliably across locales)
for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "(Get-Date).ToString('yyyy-MM-dd')"`) do set "TODAY=%%D"

rem PSI snapshot
python "%PROJECT_ROOT%\scripts\collect_psi.py" --infile "%PROJECT_ROOT%\data\sample_urls.txt" --out "%PROJECT_ROOT%\data\reports\psi_%TODAY%.csv" --strategy mobile
set PSI_EXIT=%ERRORLEVEL%

rem GEO snapshot (replace domain)
python "%PROJECT_ROOT%\scripts\collect_geo.py" --queries "%PROJECT_ROOT%\data\geo_queries.txt" --site yourdomain.co.za --out "%PROJECT_ROOT%\data\reports\geo_%TODAY%.csv"
set GEO_EXIT=%ERRORLEVEL%

rem Save exit codes and timestamp to log
echo %DATE% %TIME% PSI=%PSI_EXIT% GEO=%GEO_EXIT% >> "%PROJECT_ROOT%\logs\daily_reports.log"

popd
endlocal
