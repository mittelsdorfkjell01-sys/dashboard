[CmdletBinding()]
param(
    [switch]$Fetch,
    [string]$PublicRemote = 'public',
    [string]$PublicBranch = 'main'
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$publicRef = "$PublicRemote/$PublicBranch"

Push-Location $repoRoot
try {
    if ($Fetch) {
        & git fetch --quiet $PublicRemote $PublicBranch
        if ($LASTEXITCODE -ne 0) { throw "git fetch $PublicRemote $PublicBranch failed" }
    }
    & git rev-parse --verify --quiet $publicRef *> $null
    if ($LASTEXITCODE -ne 0) { throw "Missing ref $publicRef. Run with -Fetch or verify the remote." }

    $dashboardHead = (& git rev-parse --short=12 HEAD).Trim()
    $publicHead = (& git rev-parse --short=12 $publicRef).Trim()
    $mergeBase = (& git merge-base HEAD $publicRef).Trim()
    $baseShort = (& git rev-parse --short=12 $mergeBase).Trim()
    $counts = ((& git rev-list --left-right --count "$publicRef...HEAD").Trim() -split '\s+')
    $publicOnly = [int]$counts[0]
    $dashboardOnly = [int]$counts[1]
    $codeGlobs = @('*.py', '*.pyi', '*.ts', '*.tsx', '*.js', '*.jsx', '*.css', '*.html', '*.sql', '*.yml', '*.yaml', '*.toml')
    $changed = @(& git diff --name-only "$publicRef...HEAD" -- @codeGlobs)

    Write-Output "dashboard_head=$dashboardHead"
    Write-Output "public_head=$publicHead"
    Write-Output "merge_base=$baseShort"
    Write-Output "dashboard_only_commits=$dashboardOnly"
    Write-Output "public_only_commits=$publicOnly"
    Write-Output "changed_code_files=$($changed.Count)"
    if ($publicOnly -gt 0) { Write-Output 'status=diverged' }
    elseif ($dashboardOnly -gt 0) { Write-Output 'status=public_behind' }
    else { Write-Output 'status=in_sync' }
    Write-Output 'sample:'
    $changed | Select-Object -First 20 | ForEach-Object { Write-Output "  $_" }
    if ($changed.Count -gt 20) { Write-Output "  ... $($changed.Count - 20) more" }
} finally {
    Pop-Location
}
