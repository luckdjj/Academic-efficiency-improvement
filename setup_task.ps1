# 配置定时任务
# 运行方式（管理员）: powershell -ExecutionPolicy Bypass -File setup_task.ps1

$taskName = "更新 PDF 图片库"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host " PDF 图片库自动更新 - 定时任务配置" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]"Administrator")
if (-not $isAdmin) {
    Write-Host "[错误] 需要管理员权限。" -ForegroundColor Red
    Write-Host "请右键 PowerShell -> 以管理员身份运行，然后重试。" -ForegroundColor Yellow
    exit 1
}

$scriptPath = Join-Path $PSScriptRoot "run.bat"
if (-not (Test-Path $scriptPath)) {
    Write-Host "[错误] 找不到 run.bat: $scriptPath" -ForegroundColor Red
    exit 1
}

Write-Host "任务将执行: $scriptPath" -ForegroundColor White
Write-Host ""

Write-Host "选择更新频率:" -ForegroundColor Yellow
Write-Host "  1. 每天 10:00 (推荐)"
Write-Host "  2. 每天 14:00"
Write-Host "  3. 每周一 10:00"
Write-Host "  4. 自定义时间"
Write-Host ""

$choice = Read-Host "请输入选择 (1-4) [默认=1]"

switch ($choice) {
    "1" { $trigger = New-ScheduledTaskTrigger -Daily -At 10:00am; $desc = "每天 10:00" }
    "2" { $trigger = New-ScheduledTaskTrigger -Daily -At 14:00; $desc = "每天 14:00" }
    "3" { $trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 10:00am; $desc = "每周一 10:00" }
    "4" {
        $h = Read-Host "小时 (0-23)"
        $m = Read-Host "分钟 (0-59)"
        $trigger = New-ScheduledTaskTrigger -Daily -At ("{0:D2}:{1:D2}" -f [int]$h, [int]$m)
        $desc = "每天 $h:$m"
    }
    default { $trigger = New-ScheduledTaskTrigger -Daily -At 10:00am; $desc = "每天 10:00" }
}

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host ""
    Write-Host "已存在同名任务，是否覆盖？ (Y/N)" -ForegroundColor Yellow
    $ans = Read-Host
    if ($ans -notin @("Y","y")) {
        Write-Host "操作取消。" -ForegroundColor Yellow
        exit 0
    }
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "旧任务已删除。" -ForegroundColor Green
}

$action = New-ScheduledTaskAction -Execute $scriptPath
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

try {
    Register-ScheduledTask -TaskName $taskName `
        -Description "PDF 图片库自动更新（耕地细碎化 + 农业多功能性）" `
        -Trigger $trigger -Action $action -Settings $settings `
        -RunLevel Highest -ErrorAction Stop | Out-Null

    Write-Host ""
    Write-Host "[成功] 定时任务已创建" -ForegroundColor Green
    Write-Host "  任务名: $taskName" -ForegroundColor White
    Write-Host "  频率:   $desc" -ForegroundColor White
    Write-Host ""
    Write-Host "  手动运行:  Start-ScheduledTask -TaskName `"$taskName`"" -ForegroundColor Cyan
    Write-Host "  查看状态:  Get-ScheduledTask -TaskName `"$taskName`"" -ForegroundColor Cyan
    Write-Host ""
} catch {
    Write-Host "[失败] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
