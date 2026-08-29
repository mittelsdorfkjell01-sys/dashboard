[CmdletBinding()]
param(
    [ValidateSet('spots', 'map', 'weather', 'admin', 'frontend', 'database', 'tests', 'changed')]
    [string]$Area = 'changed',
    [string]$Query,
    [ValidateRange(1, 200)]
    [int]$MaxFiles = 40,
    [ValidateRange(1, 500)]
    [int]$MaxMatches = 80
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

$areaPatterns = @{
    spots = @(
        'app/api/spots.py', 'app/public_catalog.py', 'app/schemas/spot.py',
        'app/models/spot.py', 'frontend/src/lib/api.ts', 'frontend/src/lib/adapt.ts',
        'frontend/src/lib/hooks.ts', 'tests/test_api.py'
    )
    map = @(
        'frontend/src/pages/MapView.tsx', 'frontend/src/components/SpotMap.tsx',
        'frontend/src/components/MapLegend.tsx', 'frontend/src/components/MapModeSwitch.tsx',
        'frontend/src/lib/publicMap.ts', 'frontend/src/lib/spotMapReading.ts',
        'frontend/src/lib/waveScale.ts', 'frontend/src/lib/__tests__/publicMap.test.ts',
        'frontend/e2e/map.spec.ts', 'frontend/e2e/spot-map.spec.ts', 'app/api/spots.py'
    )
    weather = @(
        'app/live', 'app/weather', 'app/nearshore', 'app/spatial_fields',
        'app/api/weather_fields.py', 'app/api/admin_weather.py', 'app/schemas/live.py',
        'tests/test_live.py', 'tests/test_live_api.py', 'tests/test_weather_physics.py',
        'tests/test_weather_w1.py', 'tests/test_weather_contract_v4.py',
        'tests/test_spatial_field_contract.py', 'frontend/src/components/data',
        'frontend/src/lib/forecastNormalization.ts'
    )
    admin = @(
        'app/api/admin.py', 'app/admin', 'frontend/src/adminRoutes.tsx',
        'frontend/src/pages/AdminHome.tsx', 'frontend/src/pages/AdminSpots.tsx',
        'frontend/src/pages/AdminSpotForm.tsx', 'frontend/src/components/admin',
        'tests/test_admin_api.py'
    )
    frontend = @(
        'frontend/src/main.tsx', 'frontend/src/pages', 'frontend/src/components',
        'frontend/src/lib', 'frontend/src/state', 'frontend/src/index.css',
        'frontend/package.json', 'frontend/vite.config.ts'
    )
    database = @(
        'app/db', 'app/models', 'app/config.py', 'alembic/env.py',
        'alembic/versions', 'docker-compose.yml', 'tests/conftest.py'
    )
    tests = @('tests', 'frontend/src/lib/__tests__', 'frontend/src/components/data/__tests__', 'frontend/e2e')
    changed = @()
}

function Get-AreaFiles {
    if ($Area -eq 'changed') {
        $names = @(& git -C $repoRoot status --porcelain=v1) | ForEach-Object {
            if ($_.Length -lt 4) { return }
            $path = $_.Substring(3)
            if ($path -like '* -> *') { $path = ($path -split ' -> ', 2)[1] }
            $path.Trim('"')
        }
        return @($names | Where-Object { $_ } | Sort-Object -Unique)
    }

    $files = foreach ($pattern in $areaPatterns[$Area]) {
        $absolute = Join-Path $repoRoot $pattern
        if (Test-Path -LiteralPath $absolute -PathType Leaf) {
            $pattern
            continue
        }
        if (Test-Path -LiteralPath $absolute -PathType Container) {
            Get-ChildItem -LiteralPath $absolute -Recurse -File |
                Where-Object {
                    $_.FullName -notmatch '[\\/](node_modules|dist|reports|data|__pycache__)[\\/]'
                } |
                ForEach-Object { [IO.Path]::GetRelativePath($repoRoot, $_.FullName).Replace('\', '/') }
        }
    }
    return @($files | Sort-Object -Unique)
}

$files = @(Get-AreaFiles | Select-Object -First $MaxFiles)
$total = @(Get-AreaFiles).Count

Write-Output "area=$Area files_shown=$($files.Count) files_total=$total"
Write-Output 'architecture=docs/architecture/repository-map.md'
Write-Output 'files:'
$files | ForEach-Object { Write-Output "  $_" }
if ($total -gt $files.Count) {
    Write-Output "  ... $($total - $files.Count) more (raise -MaxFiles only if needed)"
}

Write-Output 'git:'
$status = @(& git -C $repoRoot status --short)
if ($status.Count -eq 0) { Write-Output '  clean' } else { $status | Select-Object -First 30 | ForEach-Object { "  $_" } }

if ($Query) {
    Write-Output "matches query=${Query}:"
    if ($files.Count -eq 0) {
        Write-Output '  none (area has no files)'
        exit 0
    }
    Push-Location $repoRoot
    try {
        $matches = @(& rg -n --color never --glob '!*.min.*' --glob '!frontend/tsconfig.tsbuildinfo' -- $Query @files 2>$null)
        $matches | Select-Object -First $MaxMatches
        if ($matches.Count -gt $MaxMatches) {
            Write-Output "... $($matches.Count - $MaxMatches) more matches omitted"
        }
        if ($matches.Count -eq 0) { Write-Output '  none' }
    } finally {
        Pop-Location
    }
}
