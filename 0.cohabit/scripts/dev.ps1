#Requires -Version 5.1
<#
.SYNOPSIS
  Cohabit local development helper (Windows PowerShell).

.DESCRIPTION
  One-command setup/start/status/stop for the local Cohabit stack.
  The script only manages the local development environment. It never
  installs Python/Node/PostgreSQL, never commits, and never touches a
  non-local database.

.EXAMPLE
  .\scripts\dev.ps1 up
  .\scripts\dev.ps1 setup
  .\scripts\dev.ps1 start
  .\scripts\dev.ps1 status
  .\scripts\dev.ps1 stop
  .\scripts\dev.ps1 reset -Force
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "setup", "start", "stop", "status", "reset", "help")]
    [string]$Command = "help",

    [switch]$Force,
    [switch]$NoSeed,
    [switch]$Postgres
)

$ErrorActionPreference = "Stop"
$script:Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$script:Backend = Join-Path $script:Root "backend"
$script:Frontend = Join-Path $script:Root "frontend"
$script:RunDir = Join-Path $script:Root ".walkthrough\dev"
$script:BackendEnv = Join-Path $script:Backend ".env"
$script:FrontendEnv = Join-Path $script:Frontend ".env.local"
$script:Python = Join-Path $script:Backend ".venv\Scripts\python.exe"
$script:BackendPid = Join-Path $script:RunDir "backend.pid"
$script:FrontendPid = Join-Path $script:RunDir "frontend.pid"
$script:BackendPortPid = Join-Path $script:RunDir "backend.port.pid"
$script:FrontendPortPid = Join-Path $script:RunDir "frontend.port.pid"

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Write-Info([string]$Text) {
    Write-Host "  $Text"
}

function Write-OK([string]$Text) {
    Write-Host "  [OK] $Text" -ForegroundColor Green
}

function Write-Warn([string]$Text) {
    Write-Host "  [WARN] $Text" -ForegroundColor Yellow
}

function Fail([string]$Text) {
    Write-Host ""
    Write-Host "[FAIL] $Text" -ForegroundColor Red
    exit 1
}

function Test-Port([string]$HostName, [int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne(500)) { return $false }
        $client.EndConnect($iar)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Wait-Port([string]$HostName, [int]$Port, [int]$Seconds = 45) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $HostName $Port) { return $true }
        Start-Sleep -Milliseconds 800
    }
    return $false
}

function Get-PortOwnerPid([int]$Port) {
    $conn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($conn) { return [int]$conn.OwningProcess }
    return $null
}

function Get-EnvValue([string]$Key) {
    if (-not (Test-Path $script:BackendEnv)) { return $null }
    $pattern = "^\s*" + [regex]::Escape($Key) + "="
    $line = Get-Content $script:BackendEnv -ErrorAction SilentlyContinue |
        Where-Object { $_ -match $pattern } |
        Select-Object -First 1
    if (-not $line) { return $null }
    return ($line -replace $pattern, "").Trim()
}

function Set-EnvValue([string]$Key, [string]$Value) {
    $lines = @()
    if (Test-Path $script:BackendEnv) {
        $lines = @(Get-Content $script:BackendEnv)
    }
    $pattern = "^\s*" + [regex]::Escape($Key) + "="
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match $pattern) {
            $lines[$i] = "$Key=$Value"
            $found = $true
        }
    }
    if (-not $found) { $lines += "$Key=$Value" }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($script:BackendEnv, $lines, $utf8)
}

function Get-DbConfig {
    $url = Get-EnvValue "DATABASE_URL"
    if (-not $url) {
        $url = "postgres://cohabit:cohabit_dev_pw@127.0.0.1:5433/cohabit_dev"
    }
    $pattern = '^postgres(?:ql)?://([^:]+):([^@]*)@([^:/]+):(\d+)/(.+)$'
    if ($url -notmatch $pattern) {
        Fail "DATABASE_URL 格式无法解析：$url"
    }
    return [pscustomobject]@{
        Host = $Matches[3]
        Port = [int]$Matches[4]
        User = $Matches[1]
        Password = $Matches[2]
        Database = $Matches[5]
    }
}

function Get-PgBin {
    $candidates = @()
    if ($env:PG_BIN) { $candidates += $env:PG_BIN }
    $candidates += @(
        "D:\tools\pgsql16\bin",
        "C:\Program Files\PostgreSQL\16\bin",
        "C:\Program Files\PostgreSQL\15\bin"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path (Join-Path $candidate "pg_ctl.exe"))) {
            return $candidate
        }
    }
    $cmd = Get-Command "pg_ctl.exe" -ErrorAction SilentlyContinue
    if ($cmd) { return (Split-Path $cmd.Source) }
    return $null
}

function Get-PgPassword {
    $pwFile = Join-Path $script:Root ".pgpw"
    if (Test-Path $pwFile) {
        return (Get-Content $pwFile -Raw).Trim()
    }
    return (Get-DbConfig).Password
}

function Ensure-EnvFiles {
    Write-Step "检查本地配置"
    if (-not (Test-Path $script:BackendEnv)) {
        $example = Join-Path $script:Backend ".env.example"
        if (-not (Test-Path $example)) { Fail "缺少 backend/.env.example，无法生成 .env" }
        Copy-Item $example $script:BackendEnv
        Write-OK "已从 .env.example 生成 backend/.env"
    }
    else {
        Write-OK "backend/.env 已存在"
    }

    $secret = Get-EnvValue "SECRET_KEY"
    if (-not $secret -or $secret -eq "change-me-local-only") {
        if (-not (Test-Path $script:Python)) {
            Write-Warn "venv 尚未创建，稍后安装依赖后再生成 SECRET_KEY"
        }
        else {
            $newSecret = & $script:Python -c "import secrets; print(secrets.token_urlsafe(50))"
            if ($LASTEXITCODE -ne 0) { Fail "生成 SECRET_KEY 失败" }
            Set-EnvValue "SECRET_KEY" $newSecret.Trim()
            Write-OK "已生成本地 SECRET_KEY"
        }
    }
    else {
        Write-OK "SECRET_KEY 已配置"
    }

    if (-not (Test-Path $script:FrontendEnv)) {
        $frontendExample = Join-Path $script:Frontend ".env.example"
        if (-not (Test-Path $frontendExample)) { Fail "缺少 frontend/.env.example，无法生成 .env.local" }
        Copy-Item $frontendExample $script:FrontendEnv
        Write-OK "已从 .env.example 生成 frontend/.env.local"
    }
    else {
        Write-OK "frontend/.env.local 已存在"
    }
}

function Ensure-Venv {
    Write-Step "检查 Python 虚拟环境"
    if (Test-Path $script:Python) {
        & $script:Python -c "import django" 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-OK "venv 与 Django 已就绪"
            return
        }
    }

    $uv = Get-Command "uv.exe" -ErrorAction SilentlyContinue
    if ($uv) {
        Write-Info "使用 uv 创建 venv 并安装依赖"
        Push-Location $script:Backend
        try {
            & $uv.Source venv --python 3.12 .venv
            if ($LASTEXITCODE -ne 0) { Fail "uv venv 创建失败" }
            & $uv.Source pip install --python $script:Python -r (Join-Path $script:Backend "requirements\dev.txt")
            if ($LASTEXITCODE -ne 0) { Fail "uv pip install 失败" }
        }
        finally { Pop-Location }
    }
    else {
        Write-Info "未找到 uv，使用 py -3.12 + pip 安装依赖"
        $py = Get-Command "py.exe" -ErrorAction SilentlyContinue
        if (-not $py) { Fail "未找到 Python 3.12；请先安装 Python 3.12 或 uv" }
        Push-Location $script:Backend
        try {
            & $py.Source -3.12 -m venv .venv
            if ($LASTEXITCODE -ne 0) { Fail "Python venv 创建失败（需要 Python 3.12）" }
            & $script:Python -m pip install --upgrade pip
            & $script:Python -m pip install -r (Join-Path $script:Backend "requirements\dev.txt")
            if ($LASTEXITCODE -ne 0) { Fail "pip install 失败" }
        }
        finally { Pop-Location }
    }

    if (-not (Test-Path $script:Python)) { Fail "venv 创建后仍未找到 $script:Python" }
    $secret = Get-EnvValue "SECRET_KEY"
    if (-not $secret -or $secret -eq "change-me-local-only") {
        $newSecret = & $script:Python -c "import secrets; print(secrets.token_urlsafe(50))"
        if ($LASTEXITCODE -ne 0) { Fail "生成 SECRET_KEY 失败" }
        Set-EnvValue "SECRET_KEY" $newSecret.Trim()
        Write-OK "已生成本地 SECRET_KEY"
    }
}

function Ensure-Npm {
    Write-Step "检查前端依赖"
    $npm = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    if (-not $npm) { Fail "未找到 npm；请先安装 Node.js 22/24" }
    $nodeModules = Join-Path $script:Frontend "node_modules"
    if (Test-Path $nodeModules) {
        Write-OK "node_modules 已存在"
        return
    }
    Push-Location $script:Frontend
    try {
        Write-Info "执行 npm ci（首次可能需要几分钟）"
        & $npm.Source ci
        if ($LASTEXITCODE -ne 0) { Fail "npm ci 失败" }
    }
    finally { Pop-Location }
}

function Ensure-Postgres {
    Write-Step "检查 PostgreSQL"
    $db = Get-DbConfig
    if (Test-Port $db.Host $db.Port) {
        Write-OK "PostgreSQL 已在 $($db.Host):$($db.Port) 监听"
        return
    }

    $pgBin = Get-PgBin
    if (-not $pgBin) {
        Fail "未找到 PostgreSQL 16。请安装 PostgreSQL 16，或设置 `$env:PG_BIN` 指向 bin 目录。"
    }
    $pgData = Join-Path $script:Root ".pgdata"
    $pgLog = Join-Path $script:RunDir "postgres.log"
    if (-not (Test-Path $script:RunDir)) { New-Item -ItemType Directory -Force -Path $script:RunDir | Out-Null }

    if (-not (Test-Path $pgData)) {
        Write-Info "初始化本地 PostgreSQL 数据目录：$pgData"
        & (Join-Path $pgBin "initdb.exe") -D $pgData -U postgres --encoding=UTF8 --locale=C
        if ($LASTEXITCODE -ne 0) { Fail "initdb 失败" }
    }
    else {
        Write-Info "使用已有数据目录：$pgData"
    }

    Write-Info "启动 PostgreSQL（端口 $($db.Port)）"
    & (Join-Path $pgBin "pg_ctl.exe") -D $pgData -o "-p $($db.Port)" -l $pgLog start
    if (-not (Wait-Port $db.Host $db.Port 30)) {
        Fail "PostgreSQL 启动后未监听 $($db.Host):$($db.Port)。查看 $pgLog"
    }
    Write-OK "PostgreSQL 已启动"
}

function Ensure-Database {
    Write-Step "检查数据库角色与库"
    $db = Get-DbConfig
    $pgBin = Get-PgBin
    if (-not $pgBin) { Fail "未找到 PostgreSQL bin 目录" }
    $psql = Join-Path $pgBin "psql.exe"
    if (-not (Test-Path $psql)) { Fail "未找到 psql.exe" }

    $oldPw = $env:PGPASSWORD
    $env:PGPASSWORD = Get-PgPassword
    try {
        $role = (& $psql -w -h $db.Host -p $db.Port -U postgres -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$($db.User)'" 2>$null | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) {
            Fail "无法以 postgres 连接本机数据库。请确认 postgres 超级用户密码（可写入 0.cohabit/.pgpw）或手动建库。"
        }
        if ($role -ne "1") {
            & $psql -w -h $db.Host -p $db.Port -U postgres -d postgres -c "CREATE ROLE $($db.User) LOGIN PASSWORD '$($db.Password)';"
            if ($LASTEXITCODE -ne 0) { Fail "创建数据库角色失败" }
            Write-OK "已创建角色 $($db.User)"
        }
        else {
            Write-OK "角色 $($db.User) 已存在"
        }

        $database = (& $psql -w -h $db.Host -p $db.Port -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$($db.Database)'" 2>$null | Out-String).Trim()
        if ($database -ne "1") {
            & $psql -w -h $db.Host -p $db.Port -U postgres -d postgres -c "CREATE DATABASE $($db.Database) OWNER $($db.User);"
            if ($LASTEXITCODE -ne 0) { Fail "创建数据库 $($db.Database) 失败" }
            Write-OK "已创建数据库 $($db.Database)"
        }
        else {
            Write-OK "数据库 $($db.Database) 已存在"
        }
    }
    finally {
        if ($null -eq $oldPw) { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
        else { $env:PGPASSWORD = $oldPw }
    }
}

function Initialize-Database {
    Write-Step "迁移与演示数据"
    Push-Location $script:Backend
    try {
        & $script:Python manage.py migrate --noinput
        if ($LASTEXITCODE -ne 0) { Fail "migrate 失败" }

        $countText = (& $script:Python manage.py shell -c "from django.contrib.auth import get_user_model; print(get_user_model().objects.count())" 2>$null | Select-Object -Last 1)
        $userCount = 0
        [void][int]::TryParse(($countText | Out-String).Trim(), [ref]$userCount)
        if ($userCount -eq 0 -and -not $NoSeed) {
            Write-Info "数据库为空，执行 seed_demo --reset"
            & $script:Python manage.py seed_demo --reset
            if ($LASTEXITCODE -ne 0) { Fail "seed_demo 失败" }
        }
        elseif ($userCount -gt 0) {
            Write-Info "数据库已有 $userCount 个用户，跳过 seed（需要重置请运行 reset）"
        }
        else {
            Write-Info "按 -NoSeed 跳过演示数据"
        }

        & $script:Python manage.py check
        if ($LASTEXITCODE -ne 0) { Fail "manage.py check 失败" }
    }
    finally { Pop-Location }
}

function Setup-Dev {
    Ensure-Venv
    Ensure-EnvFiles
    Ensure-Npm
    Ensure-Postgres
    Ensure-Database
    Initialize-Database
    Write-Step "环境准备完成"
    Write-Info "启动：.\scripts\dev.ps1 start"
    Write-Info "或一键：.\scripts\dev.ps1 up"
}

function Start-Backend {
    if (Test-Port "127.0.0.1" 8000) {
        Write-OK "后端 8000 已在运行"
        return
    }
    if (-not (Test-Path $script:Python)) { Fail "未找到 venv，请先运行 setup" }
    if (-not (Test-Path $script:RunDir)) { New-Item -ItemType Directory -Force -Path $script:RunDir | Out-Null }
    $outLog = Join-Path $script:RunDir "backend.out.log"
    $errLog = Join-Path $script:RunDir "backend.err.log"
    Write-Info "启动 Django 后端（127.0.0.1:8000）"
    $p = Start-Process -FilePath $script:Python `
        -ArgumentList @("manage.py", "runserver", "127.0.0.1:8000") `
        -WorkingDirectory $script:Backend `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -PassThru
    Set-Content -Path $script:BackendPid -Value $p.Id -Encoding ascii
    if (-not (Wait-Port "127.0.0.1" 8000 60)) {
        Fail "后端未在 60 秒内监听 8000。查看 $outLog / $errLog"
    }
    if (-not (Wait-Http "http://127.0.0.1:8000/api/health/" 60)) {
        Fail "后端端口已开但 /api/health/ 未返回 200。查看 $outLog / $errLog"
    }
    $ownerPid = Get-PortOwnerPid 8000
    if ($ownerPid) { Set-Content -Path $script:BackendPortPid -Value $ownerPid -Encoding ascii }
    Write-OK "后端已就绪"
}

function Start-Frontend {
    if (Test-Port "127.0.0.1" 5173) {
        Write-OK "前端 5173 已在运行"
        return
    }
    $npm = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
    if (-not $npm) { Fail "未找到 npm" }
    if (-not (Test-Path $script:RunDir)) { New-Item -ItemType Directory -Force -Path $script:RunDir | Out-Null }
    $outLog = Join-Path $script:RunDir "frontend.out.log"
    $errLog = Join-Path $script:RunDir "frontend.err.log"
    Write-Info "启动 Vite 前端（127.0.0.1:5173）"
    $p = Start-Process -FilePath $npm.Source `
        -ArgumentList @("run", "dev") `
        -WorkingDirectory $script:Frontend `
        -WindowStyle Hidden `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -PassThru
    Set-Content -Path $script:FrontendPid -Value $p.Id -Encoding ascii
    if (-not (Wait-Port "127.0.0.1" 5173 60)) {
        Fail "前端未在 60 秒内监听 5173。查看 $outLog / $errLog"
    }
    $ownerPid = Get-PortOwnerPid 5173
    if ($ownerPid) { Set-Content -Path $script:FrontendPortPid -Value $ownerPid -Encoding ascii }
    Write-OK "前端已就绪"
}

function Wait-Http([string]$Url, [int]$Seconds = 45) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return $true }
        }
        catch { }
        Start-Sleep -Milliseconds 800
    }
    return $false
}

function Show-Access {
    Write-Step "访问入口"
    Write-Info "学生端: http://127.0.0.1:5173/"
    Write-Info "管理后台: http://127.0.0.1:8000/admin/"
    Write-Info "健康检查: http://127.0.0.1:8000/api/health/"
    Write-Host ""
    Write-Info "学生账号: demo009@stu.edu.cn / Demo1234!"
    Write-Info "管理员:  admin@cohabit.local / Admin1234!"
    Write-Info "邀请码:  COHAB2026    本地验证码: 123456"
    Write-Host ""
    Write-Info "日志目录: $script:RunDir"
}

function Start-Dev {
    Ensure-Postgres
    Ensure-Database
    Start-Backend
    Start-Frontend
    Show-Access
}

function Stop-ProcessTree([int]$ProcessId) {
    if (-not $ProcessId) { return }
    if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
    }
}

function Stop-Dev {
    Write-Step "停止由脚本启动的服务"
    $seen = @{}

    # 先停 Start-Process 返回的根进程；taskkill /T 会连带停掉子进程。
    foreach ($pidFile in @($script:BackendPid, $script:FrontendPid)) {
        if (Test-Path $pidFile) {
            $value = (Get-Content $pidFile -Raw).Trim()
            $procId = 0
            if ([int]::TryParse($value, [ref]$procId) -and -not $seen.ContainsKey($procId)) {
                $seen[$procId] = $true
                if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
                    Stop-ProcessTree $procId
                    Write-OK "已停止 PID $procId"
                }
            }
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        }
    }

    # 再处理端口 owner：如果根进程的 /T 已带走它，这里会静默清理。
    foreach ($pidFile in @($script:BackendPortPid, $script:FrontendPortPid)) {
        if (Test-Path $pidFile) {
            $value = (Get-Content $pidFile -Raw).Trim()
            $procId = 0
            if ([int]::TryParse($value, [ref]$procId) -and -not $seen.ContainsKey($procId)) {
                if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
                    Stop-ProcessTree $procId
                    Write-OK "已停止端口进程 PID $procId"
                }
            }
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        }
    }
    if ($Postgres) {
        $pgBin = Get-PgBin
        if ($pgBin) {
            $pgData = Join-Path $script:Root ".pgdata"
            if (Test-Path $pgData) {
                & (Join-Path $pgBin "pg_ctl.exe") -D $pgData stop -m fast
            }
        }
    }
    Write-Info "未由脚本启动、或没有 PID 文件的服务不会被停止。"
}

function Show-Status {
    Write-Step "Cohabit 本地状态"
    $db = Get-DbConfig
    if (Test-Port $db.Host $db.Port) {
        Write-OK "PostgreSQL $($db.Host):$($db.Port) 监听中"
    }
    else {
        Write-Warn "PostgreSQL $($db.Host):$($db.Port) 未监听"
    }

    foreach ($item in @(
        @{ Name = "后端"; Port = 8000; Url = "http://127.0.0.1:8000/api/health/" },
        @{ Name = "前端"; Port = 5173; Url = "http://127.0.0.1:5173/" }
    )) {
        if (Test-Port "127.0.0.1" $item.Port) {
            if (Wait-Http $item.Url 3) { Write-OK "$($item.Name) 端口 $($item.Port) 正常" }
            else { Write-Warn "$($item.Name) 端口 $($item.Port) 已开，但 HTTP 未就绪" }
        }
        else {
            Write-Warn "$($item.Name) 端口 $($item.Port) 未监听"
        }
    }
    if (Test-Path $script:RunDir) {
        Write-Info "日志目录: $script:RunDir"
    }
}

function Reset-Seed {
    if (-not $Force) {
        Write-Warn "reset 会删除并重建本地演示数据。"
        $answer = Read-Host "确认重置本地开发库？输入 RESET 继续"
        if ($answer -ne "RESET") {
            Write-Info "已取消。"
            return
        }
    }
    Ensure-Postgres
    Ensure-Database
    Push-Location $script:Backend
    try {
        & $script:Python manage.py seed_demo --reset
        if ($LASTEXITCODE -ne 0) { Fail "seed_demo --reset 失败" }
    }
    finally { Pop-Location }
    Write-OK "演示数据已重置"
}

function Show-Help {
    Write-Host @"
Cohabit 本地开发脚本

用法:
  .\scripts\dev.ps1 up        检查环境、安装依赖、建库、迁移，然后启动前后端
  .\scripts\dev.ps1 setup     只做环境准备（不启动服务）
  .\scripts\dev.ps1 start     启动 PostgreSQL/后端/前端（已运行则跳过）
  .\scripts\dev.ps1 status    查看端口与 HTTP 状态
  .\scripts\dev.ps1 stop      停止由本脚本启动的前后端
  .\scripts\dev.ps1 stop -Postgres
                              同时停止本地 .pgdata 的 PostgreSQL
  .\scripts\dev.ps1 reset     重置演示数据（需输入 RESET）
  .\scripts\dev.ps1 reset -Force
                              非交互重置（仅限本地开发库）

前提:
  Python 3.12、Node 22/24、PostgreSQL 16（或设置 `$env:PG_BIN`）。
  脚本不会自动安装这些依赖，不会 commit，也不会操作非本地数据库。
"@
}

switch ($Command) {
    "help"    { Show-Help }
    "setup"   { Setup-Dev }
    "start"   { Start-Dev }
    "up"      { Setup-Dev; Start-Dev }
    "status"  { Show-Status }
    "stop"    { Stop-Dev }
    "reset"   { Reset-Seed }
    default   { Show-Help }
}


