<#
.SYNOPSIS
  Uninstall the CommunityCompute worker (Sprint 24).
.DESCRIPTION
  1. Stops any running worker/tray processes started from a bundle dir.
  2. Removes the HKCU login auto-start entry.
  3. Optionally wipes per-machine data (id, policy, credential, models, logs).
  The bundle folder itself is deleted by hand afterwards (never self-delete).
.PARAMETER WipeData
  Also delete per-machine data (default prompts).
#>
param([switch]$WipeData)

$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $PSScriptRoot

Write-Output "== CommunityCompute worker uninstall =="
Get-Process -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -and $_.Path.StartsWith($here, [StringComparison]::OrdinalIgnoreCase) } |
  ForEach-Object { Write-Output "stopping $($_.ProcessName) ($($_.Id))"; Stop-Process -Id $_.Id -Force }

$runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
if (Get-ItemProperty -Path $runKey -Name "CommunityComputeWorker" -ErrorAction SilentlyContinue) {
    Remove-ItemProperty -Path $runKey -Name "CommunityComputeWorker"
    Write-Output "removed login auto-start entry"
} else {
    Write-Output "no auto-start entry found"
}

$data = Join-Path $env:LOCALAPPDATA "CommunityCompute"
$doWipe = $WipeData
if (-not $doWipe -and (Test-Path $data)) {
    $answer = Read-Host "Delete per-machine data at $data? (id, policy, credential, models, logs) [y/N]"
    $doWipe = $answer -match '^(y|yes)$'
}
if ($doWipe -and (Test-Path $data)) {
    Remove-Item -Recurse -Force $data
    Write-Output "wiped $data"
}
Write-Output "done. Delete this folder to finish uninstalling."
