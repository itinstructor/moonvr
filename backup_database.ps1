# Database Backup Script
# Backs up the SQLite database with timestamp

$ErrorActionPreference = "Stop"

# Configuration
$dbPath = "C:\inetpub\moonvr\instance\nasa_blog.db"
$backupDir = "C:\inetpub\moonvr\backups"
$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$backupFileName = "blog_$timestamp.bak"
$backupPath = Join-Path $backupDir $backupFileName

# Keep only the last 14 days of backups
$daysToKeep = 14

try {
    # Create backup directory if it doesn't exist
    if (-not (Test-Path $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        Write-Host "Created backup directory: $backupDir"
    }

    # Check if database exists
    if (-not (Test-Path $dbPath)) {
        Write-Error "Database not found at: $dbPath"
        exit 1
    }

    # Copy database file
    Copy-Item -Path $dbPath -Destination $backupPath -Force
    Write-Host "Database backed up successfully to: $backupPath"

    # Clean up old backups
    $cutoffDate = (Get-Date).AddDays(-$daysToKeep)
    Get-ChildItem -Path $backupDir -Filter "blog_*.db" | 
        Where-Object { $_.LastWriteTime -lt $cutoffDate } | 
        ForEach-Object {
            Remove-Item $_.FullName -Force
            Write-Host "Removed old backup: $($_.Name)"
        }

    # Log success
    $logPath = Join-Path $backupDir "backup_log.txt"
    $logEntry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Backup successful: $backupFileName"
    Add-Content -Path $logPath -Value $logEntry

    Write-Host "Backup completed successfully"
    exit 0
}
catch {
    $errorMsg = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - Backup FAILED: $($_.Exception.Message)"
    Write-Error $errorMsg
    
    # Log error
    $logPath = Join-Path $backupDir "backup_log.txt"
    Add-Content -Path $logPath -Value $errorMsg
    
    exit 1
}
