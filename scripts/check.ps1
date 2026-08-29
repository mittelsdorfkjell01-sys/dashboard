[CmdletBinding()]
param(
    [ValidateSet('spots', 'map', 'weather', 'admin', 'frontend', 'backend', 'changed')]
    [string]$Area = 'changed',
    [ValidateRange(20, 500)]
    [int]$TailLines = 120
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$failures = 0

function Invoke-BoundedCheck {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [scriptblock]$Command
    )
    Write-Output "check=$Name"
    $output = @(& $Command 2>&1)
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        $output | Select-Object -Last $TailLines
        if ($output.Count -gt $TailLines) {
            Write-Output "... $($output.Count - $TailLines) earlier lines omitted"
        }
        Write-Output "result=failed exit_code=$code"
        $script:failures++
    } else {
        $summary = @($output | Where-Object {
            "$_" -match '(Test Files|Tests\s+|Duration|passed in|passed,|built in|compiled successfully)'
        } | Select-Object -Last 8)
        if ($summary.Count -gt 0) { $summary } else { Write-Output "output_lines=$($output.Count)" }
        Write-Output 'result=passed'
    }
}

function Get-ChangedAreas {
    $paths = @(& git -C $repoRoot status --porcelain=v1) | ForEach-Object {
        if ($_.Length -lt 4) { return }
        $path = $_.Substring(3)
        if ($path -like '* -> *') { $path = ($path -split ' -> ', 2)[1] }
        $path.Trim('"')
    } | Where-Object { $_ } | Sort-Object -Unique
    $areas = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($path in $paths) {
        if ($path -match '^(alembic/|app/(db|models)/)') { [void]$areas.Add('backend') }
        if ($path -match '^(app/(live|weather|nearshore|spatial_fields)/|app/api/(admin_weather|weather_fields)\.py|app/schemas/live\.py|tests/test_(live|weather|spatial))') { [void]$areas.Add('weather') }
        if ($path -match '^(app/api/spots\.py|app/schemas/spot\.py|frontend/src/lib/(api|adapt)\.ts|tests/test_api\.py)') { [void]$areas.Add('spots') }
        if ($path -match '^frontend/(src/(pages/MapView|components/(SpotMap|MapLegend|MapModeSwitch)|lib/(publicMap|spotMapReading|waveScale))|e2e/(map|spot-map))') { [void]$areas.Add('map') }
        if ($path -match '^(app/api/admin|app/admin/|frontend/src/(pages/Admin|components/admin|adminRoutes))') { [void]$areas.Add('admin') }
        if ($path -match '^frontend/(src/index\.css|src/main\.tsx|package(-lock)?\.json|vite\.config|tsconfig)') { [void]$areas.Add('frontend-build') }
        elseif (
            $path -match '^frontend/' -and
            $path -notmatch '^frontend/(src/(pages/MapView|components/(SpotMap|MapLegend|MapModeSwitch)|lib/(publicMap|spotMapReading|waveScale|api|adapt))|e2e/(map|spot-map))' -and
            $path -notmatch '^frontend/src/(pages/Admin|components/admin|adminRoutes)'
        ) { [void]$areas.Add('frontend-fast') }
    }
    return @($areas)
}

Push-Location $repoRoot
try {
    $areas = if ($Area -eq 'changed') { @(Get-ChangedAreas) } else { @($Area) }
    if ($areas.Count -eq 0) {
        Write-Output 'result=passed detail=no_changed_code_area'
        exit 0
    }

    foreach ($current in $areas | Sort-Object -Unique) {
        switch ($current) {
            'spots' {
                Invoke-BoundedCheck 'backend-spots' { python -m pytest tests/test_api.py -k 'list_spots or spot_catalog_version or live_map_catalogue or get_spot_by_id' -q }
                Invoke-BoundedCheck 'frontend-map-contract' { npm --prefix frontend test -- --run src/lib/__tests__/publicMap.test.ts src/lib/__tests__/adapt.test.ts }
            }
            'map' {
                Invoke-BoundedCheck 'frontend-map' { npm --prefix frontend test -- --run src/lib/__tests__/publicMap.test.ts src/lib/__tests__/spotMapReading.test.ts src/lib/__tests__/waveScale.test.ts }
            }
            'weather' {
                Invoke-BoundedCheck 'weather-unit-contracts' { python -m pytest tests/test_weather_physics.py tests/test_weather_contract_v4.py tests/test_spatial_field_contract.py -q }
            }
            'admin' {
                Invoke-BoundedCheck 'admin-api' { python -m pytest tests/test_admin_api.py -q -x }
            }
            'frontend' {
                Invoke-BoundedCheck 'frontend-tests' { npm --prefix frontend test }
                Invoke-BoundedCheck 'frontend-build' { npm --prefix frontend run build }
            }
            'frontend-fast' {
                Invoke-BoundedCheck 'frontend-tests' { npm --prefix frontend test }
            }
            'frontend-build' {
                Invoke-BoundedCheck 'frontend-build' { npm --prefix frontend run build }
            }
            'backend' {
                Invoke-BoundedCheck 'python-compile' { python -m compileall -q app tests }
            }
        }
    }
} finally {
    Pop-Location
}

if ($failures -gt 0) {
    Write-Output "summary=failed checks=$failures"
    exit 1
}
Write-Output 'summary=passed'
