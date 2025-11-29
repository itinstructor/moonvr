# Setup Database Backup Task
# Creates a Windows scheduled task to backup the database daily at 2 AM

$ErrorActionPreference = "Stop"

# Task configuration
$taskName = "MoonVR Database Backup"
$scriptPath = "C:\inetpub\moonvr\backup_database.ps1"
$taskDescription = "Daily backup of the Blog SQLite database"

# Check if running as Administrator
$currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "This script must be run as Administrator"
    exit 1
}

try {
    # Check if task already exists
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Host "Removing existing task..."
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }

    # Create the action (run PowerShell script)
    $action = New-ScheduledTaskAction -Execute "PowerShell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

    # Create the trigger (daily at 2:30 AM)
    $trigger = New-ScheduledTaskTrigger -Daily -At 2:30AM

    # Create settings
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable:$false `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries

    # Create principal (run as SYSTEM with highest privileges)
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

    # Register the task
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description $taskDescription | Out-Null

    Write-Host "Scheduled task created successfully!" -ForegroundColor Green
    Write-Host "`nTask Details:" -ForegroundColor Cyan
    Write-Host "  Name: $taskName"
    Write-Host "  Schedule: Daily at 2:00 AM"
    Write-Host "  Script: $scriptPath"
    Write-Host "  Retention: 14 days"
    Write-Host "`nBackup location: C:\inetpub\moonvr\backups"
    
    # Test the backup immediately
    Write-Host "`nWould you like to run a test backup now? (Y/N): " -NoNewline -ForegroundColor Yellow
    $response = Read-Host
    if ($response -eq 'Y' -or $response -eq 'y') {
        Write-Host "`nRunning test backup..." -ForegroundColor Cyan
        & $scriptPath
    }
}
catch {
    Write-Error "Failed to create scheduled task: $($_.Exception.Message)"
    exit 1
}
