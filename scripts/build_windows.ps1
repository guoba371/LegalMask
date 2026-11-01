param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { (Get-Command python).Source }

Push-Location $Root
try {
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -r requirements-build.txt
    & $Python packaging\create_icons.py
    & $Python -m PyInstaller packaging\LegalMask.spec --clean --noconfirm

    $PortableZip = Join-Path $Root "dist\LegalMask-Windows-x64.zip"
    if (Test-Path $PortableZip) {
        Remove-Item -LiteralPath $PortableZip -Force
    }
    Compress-Archive -Path (Join-Path $Root "dist\LegalMask") -DestinationPath $PortableZip -CompressionLevel Optimal

    if (-not $SkipInstaller) {
        $IsccCandidates = @(
            (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
            (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
            (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
            (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
        ) | Where-Object { $_ -and (Test-Path $_) }

        if (-not $IsccCandidates) {
            throw "Inno Setup 6 is required. Install it with: winget install JRSoftware.InnoSetup"
        }
        & $IsccCandidates[0] "packaging\windows\LegalMask.iss"
    }
}
finally {
    Pop-Location
}
