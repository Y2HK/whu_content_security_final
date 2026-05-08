param(
    [switch]$ForceInstall,
    [switch]$SkipModelDownload,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$InstallScript = Join-Path $Root "install_deps.py"
$ModelScript = Join-Path $Root "script\download_models.py"
$BackendVenvPython = Join-Path $Backend "venv\Scripts\python.exe"
$BackendActivate = Join-Path $Backend "venv\Scripts\Activate.ps1"
$FrontendNodeModules = Join-Path $Frontend "node_modules"
$ModelPackDir = Join-Path $Backend "models\buffalo_l"
$BackendUrl = "http://localhost:8000/health"
$SwaggerUrl = "http://localhost:8000/docs"
$FrontendUrl = "http://localhost:5173"

function Write-Section([string]$Text) {
    Write-Host ""
    Write-Host ("=" * 52)
    Write-Host $Text
    Write-Host ("=" * 52)
}

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host ("[STEP] {0}" -f $Text)
}

function Resolve-HostPython {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @($python.Source)
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return @($py.Source, "-3")
    }

    throw "未找到 Python。请先安装 Python 3.12+ 并加入 PATH。"
}

function Resolve-NpmExecutable {
    $npmCmd = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($npmCmd) {
        return $npmCmd.Source
    }

    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if ($npm) {
        return $npm.Source
    }

    throw "未找到 npm。请先安装 Node.js 18+ 并加入 PATH。"
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Command,
        [string]$WorkingDirectory = $Root
    )

    Push-Location -LiteralPath $WorkingDirectory
    try {
        if ($Command.Count -gt 1) {
            & $Command[0] @($Command[1..($Command.Count - 1)]) 2>&1 | Write-Host
        } else {
            & $Command[0] 2>&1 | Write-Host
        }

        if ($LASTEXITCODE -ne 0) {
            throw "命令执行失败: $($Command -join ' ')"
        }
    } finally {
        Pop-Location
    }
}

function Test-UrlReady {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url
    )

    try {
        $null = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return $true
    } catch {
        return $false
    }
}

function Wait-UrlReady {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [int]$TimeoutSeconds = 120,
        [int]$IntervalSeconds = 2
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-UrlReady -Url $Url) {
            return $true
        }
        Start-Sleep -Seconds $IntervalSeconds
    }
    return $false
}

function Start-BackendWindow {
    $command = @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "Set-Location -LiteralPath '$Backend'; & '$BackendActivate'; python run.py"
    )

    Start-Process -FilePath "powershell.exe" -ArgumentList $command -WorkingDirectory $Backend
}

function Start-FrontendWindow {
    param(
        [Parameter(Mandatory = $true)]
        [string]$NpmExecutable
    )

    $command = @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "Set-Location -LiteralPath '$Frontend'; & '$NpmExecutable' run dev"
    )

    Start-Process -FilePath "powershell.exe" -ArgumentList $command -WorkingDirectory $Frontend
}

Write-Section "班级考勤系统 - 一键运行脚本"

if (-not (Test-Path -LiteralPath $Backend)) {
    throw "未找到 backend 目录: $Backend"
}
if (-not (Test-Path -LiteralPath $Frontend)) {
    throw "未找到 frontend 目录: $Frontend"
}

$hostPython = Resolve-HostPython
$npmExecutable = Resolve-NpmExecutable

$needsInstall = $ForceInstall -or
    -not (Test-Path -LiteralPath $BackendVenvPython) -or
    -not (Test-Path -LiteralPath $FrontendNodeModules) -or
    -not (Test-Path -LiteralPath (Join-Path $Backend ".env")) -or
    -not (Test-Path -LiteralPath (Join-Path $Frontend ".env.local"))

if ($needsInstall) {
    Write-Step "安装和初始化依赖环境"
    Invoke-External -Command ($hostPython + @($InstallScript)) -WorkingDirectory $Root
} else {
    Write-Step "依赖环境已存在，跳过安装"
    Write-Host "backend venv: $BackendVenvPython"
    Write-Host "frontend node_modules: $FrontendNodeModules"
}

if (-not (Test-Path -LiteralPath $BackendVenvPython)) {
    throw "安装后仍未找到后端虚拟环境 Python: $BackendVenvPython"
}

if (-not $SkipModelDownload) {
    if (-not (Test-Path -LiteralPath $ModelPackDir)) {
        Write-Step "下载 InsightFace 模型到 backend/models"
        Invoke-External -Command @($BackendVenvPython, $ModelScript) -WorkingDirectory $Root
    } else {
        Write-Step "模型目录已存在，跳过下载"
        Write-Host $ModelPackDir
    }
} else {
    Write-Step "按参数跳过模型下载"
}

Write-Step "启动后端服务"
Start-BackendWindow

Write-Step "启动前端服务"
Start-FrontendWindow -NpmExecutable $npmExecutable

Write-Step "等待服务就绪"
$backendReady = Wait-UrlReady -Url $BackendUrl -TimeoutSeconds 120
$frontendReady = Wait-UrlReady -Url $FrontendUrl -TimeoutSeconds 120

Write-Host ("后端状态: {0}" -f ($(if ($backendReady) { "已就绪" } else { "超时未确认" })))
Write-Host ("前端状态: {0}" -f ($(if ($frontendReady) { "已就绪" } else { "超时未确认" })))

if (-not $NoBrowser) {
    Write-Step "打开浏览器"
    Start-Process $FrontendUrl
    Start-Process $SwaggerUrl
} else {
    Write-Step "按参数跳过打开浏览器"
}

Write-Section "启动完成"
Write-Host "前端: $FrontendUrl"
Write-Host "Swagger: $SwaggerUrl"
Write-Host "默认账号: teacher / teacher123"
Write-Host ""
Write-Host "可选参数:"
Write-Host "  -ForceInstall      强制重新执行 install_deps.py"
Write-Host "  -SkipModelDownload 跳过模型下载"
Write-Host "  -NoBrowser         不自动打开浏览器"
