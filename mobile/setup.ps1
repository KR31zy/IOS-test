$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (Get-Command py -ErrorAction SilentlyContinue) { py -3 tools/bootstrap.py @args }
else { python tools/bootstrap.py @args }
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
