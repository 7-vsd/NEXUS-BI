<#
.SYNOPSIS
  NEXUS BI command runner for Windows PowerShell (equivalent of the Makefile).

.EXAMPLE
  .\scripts\nexus.ps1 setup        # venv + dependencies
  .\scripts\nexus.ps1 init-db      # create PostgreSQL objects
  .\scripts\nexus.ps1 pipeline     # full ETL + warehouse + SQL + ML + publish
  .\scripts\nexus.ps1 api          # FastAPI on http://localhost:8000/docs
  .\scripts\nexus.ps1 app          # Streamlit on http://localhost:8501
  .\scripts\nexus.ps1 test
#>
param([Parameter(Mandatory = $true)][ValidateSet("setup", "init-db", "etl", "train", "analytics", "publish", "pipeline",
      "pipeline-no-db", "api", "app", "test", "notebooks", "reports", "powerbi", "validate-powerbi")] [string]$Command)

# "Continue", not "Stop": Windows PowerShell 5.1 treats ANY stderr output of a native program (pip warnings,
# Python logging) as a terminating error under "Stop". Failures are detected via $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if ($Command -ne "setup" -and -not (Test-Path $Py)) { throw "Virtual env missing - run: .\scripts\nexus.ps1 setup" }
$env:PYTHONPATH = $Root

switch ($Command) {
  "setup" {
    # Prefer the newest supported Python (3.13 -> 3.10). Python 3.9 is NOT supported.
    # Ask the launcher which versions exist ("py -0") instead of probing each one: probing a missing
    # version writes to stderr, which Windows PowerShell 5.1 turns into a terminating error.
    $installed = (& py -0 2>&1 | Out-String)
    $ver = $null
    foreach ($v in "3.13", "3.12", "3.11", "3.10") {
      if ($installed -match ("-V:" + [regex]::Escape($v) + "\b")) { $ver = $v; break }
    }
    if (-not $ver) { throw "Python 3.10+ required (found none via the py launcher). Install: winget install Python.Python.3.11" }
    Write-Host "Using Python $ver"
    & py "-$ver" -m venv .venv
    if ($LASTEXITCODE) { throw "Creating the virtual environment failed" }
    & $Py -m pip install --upgrade pip
    & $Py -m pip install -r requirements.txt
    if ($LASTEXITCODE) { throw "pip install failed - see the messages above" }
    if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Created .env - edit NEXUS_DB_PASSWORD before init-db." }
  }
  "init-db"          { & $Py -m src.database.init_db }
  "etl"              { foreach ($s in "extract", "validate", "transform", "load") { & $Py -m src.pipeline --stage $s; if ($LASTEXITCODE) { exit $LASTEXITCODE } } }
  "train"            { & $Py -m src.pipeline --stage predict }
  "analytics"        { & $Py -m src.pipeline --stage analytics }
  "publish"          { & $Py -m src.pipeline --stage publish }
  "pipeline"         { & $Py -m src.pipeline --stage all }
  "pipeline-no-db"   { & $Py -m src.pipeline --stage all --skip-db }
  "api"              { & $Py -m uvicorn api.main:app --host 127.0.0.1 --port 8000 }
  "app"              { & $Py -m streamlit run app/streamlit_app.py }
  "test"             { & $Py -m pytest }
  "notebooks"        { & $Py scripts/build_notebooks.py --execute }
  "reports"          { & $Py scripts/generate_reports.py }
  "powerbi"          { & $Py powerbi/build_pbip.py --data-folder (Join-Path $Root "data\processed\powerbi") }
  "validate-powerbi" { & $Py powerbi/validate_pbip.py }
}
exit $LASTEXITCODE
