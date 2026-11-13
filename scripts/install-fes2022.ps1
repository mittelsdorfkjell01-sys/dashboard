param(
    [string]$Target = 'C:\surfwinddata-private\fes2022b',
    [string]$LicenseAcceptedAt = (Get-Date -Format 'yyyy-MM-dd'),
    [switch]$KeepArchives
)

$ErrorActionPreference = 'Stop'

$username = Read-Host 'AVISO username'
$securePassword = Read-Host 'AVISO password' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)

try {
    $env:AVISO_USERNAME = $username
    $env:AVISO_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)

    python -m scripts.fes2022_assets access
    if ($LASTEXITCODE -ne 0) {
        throw 'AVISO access is not ready. Check My AVISO+ > My products > FES.'
    }

    $arguments = @(
        '-m', 'scripts.fes2022_assets', 'install',
        '--target', $Target,
        '--license-accepted-at', $LicenseAcceptedAt
    )
    if ($KeepArchives) {
        $arguments += '--keep-archives'
    }
    & python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw 'FES2022b installation failed.'
    }
}
finally {
    Remove-Item Env:AVISO_USERNAME -ErrorAction SilentlyContinue
    Remove-Item Env:AVISO_PASSWORD -ErrorAction SilentlyContinue
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
}
