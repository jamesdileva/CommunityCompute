<#
.SYNOPSIS
  Build the CommunityCompute worker bundle (Sprint 24).
.DESCRIPTION
  Runs PyInstaller against apps/worker/worker.spec from the repo root.
  Output: dist/worker/worker.exe (+ _internal/). Requires: pip install
  pyinstaller pyside6 httpx psutil pydantic websockets.
#>
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo
Write-Output "repo: $repo"
python -m PyInstaller --noconfirm apps/worker/worker.spec
Write-Output "built: dist/worker/worker.exe"
& ".\dist\worker\worker.exe" --help | Select-Object -First 5
