$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'vSMR AVISO Converter'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$converterPython = $null
$converterArgs = @()
foreach ($candidateName in @('py.exe', 'python.exe', 'python3.exe')) {
    $candidate = Get-Command $candidateName -ErrorAction SilentlyContinue
    if ($null -eq $candidate) { continue }
    $probeArgs = @()
    if ($candidateName -eq 'py.exe') { $probeArgs += '-3' }
    try {
        & $candidate.Source @probeArgs -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) {
            $converterPython = $candidate.Source
            $converterArgs = $probeArgs
            break
        }
    } catch { continue }
}
if ($null -eq $converterPython) {
    Write-Host 'Python 3.10 or later was not found. No conversion was performed.' -ForegroundColor Red
    return
}
Write-Host ''
Write-Host '  AVISO CONVERSION' -ForegroundColor Cyan
Write-Host '  [1] Local GNG / Colours.sct (default)'
Write-Host '  [2] Original official GitHub repository'
Write-Host '  [3] QGIS projects -> AVISO GeoJSON'
do {
    $sourceChoice = Read-Host '  Choose 1, 2 or 3 (Enter = local)'
} while ($sourceChoice -notin @('', '1', '2', '3'))
$sourceArgs = @('--local')
if ($sourceChoice -eq '2') { $sourceArgs = @('--github') }
if ($sourceChoice -eq '3') {
    Write-Host '  Enter = all airports from QGIS/LFXX.qgz.' -ForegroundColor Cyan
    Write-Host '  Or enter the path to one saved airport project or AVISO.gpkg.'
    $qgisPath = (Read-Host '  QGIS input').Trim().Trim('"')
    $sourceArgs = @('--qgis')
    if ($qgisPath) { $sourceArgs += $qgisPath }
}
& $converterPython @converterArgs (Join-Path $PSScriptRoot 'aviso_converter.py') @sourceArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Conversion did not complete. See the error above.' -ForegroundColor Red
}
