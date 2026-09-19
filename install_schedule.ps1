# 注册一个 Windows 任务计划：每天定时跑一轮，挑 3 个项目并推送到手机。
#
# 用法（在 PowerShell 里执行）：
#     powershell -ExecutionPolicy Bypass -File install_schedule.ps1
#     powershell -ExecutionPolicy Bypass -File install_schedule.ps1 -Time 21:30
#
# 取消：
#     Unregister-ScheduledTask -TaskName "GitHub每日3选"

param(
    [string]$Time = "09:00",
    [string]$TaskName = "GitHub每日3选"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$entry = Join-Path $root "scripts\main.py"

if (-not (Test-Path $entry)) {
    throw "找不到 $entry，请确认脚本放在 github-daily-pick 目录下。"
}

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    throw "系统里找不到 python，请先安装 Python 并勾选 Add to PATH。"
}

$action = New-ScheduledTaskAction -Execute $python `
    -Argument "`"$entry`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
# StartWhenAvailable：错过了（比如电脑在睡眠）会在开机后补跑一次
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Force `
    -Description "每天挑 3 个 GitHub 高星好玩项目，推送到手机。" | Out-Null

Write-Host "已注册任务计划：$TaskName，每天 $Time 运行"
Write-Host "用这个命令立刻试跑一次： Start-ScheduledTask -TaskName `"$TaskName`""
Write-Host "注意：电脑要在那个时间开机（睡眠后唤醒补跑需要系统允许唤醒计时器）。"
