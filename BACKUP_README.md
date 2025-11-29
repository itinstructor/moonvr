# Database Backup System

Automated daily backup system for the NASA Blog SQLite database.

## Components

### 1. `backup_database.ps1`
The backup script that:
- Creates timestamped backups of `instance/nasa_blog.db`
- Stores backups in `backups/` directory
- Automatically removes backups older than 30 days
- Logs all backup operations to `backups/backup_log.txt`

### 2. `setup_backup_task.ps1`
Setup script that:
- Creates a Windows scheduled task
- Runs the backup daily at 2:00 AM
- Requires Administrator privileges

## Installation

1. Open PowerShell as Administrator
2. Navigate to the project directory:
   ```powershell
   cd C:\inetpub\podsinspace
   ```
3. Run the setup script:
   ```powershell
   .\setup_backup_task.ps1
   ```
4. Optionally run a test backup when prompted

## Manual Backup

To manually run a backup at any time:
```powershell
.\backup_database.ps1
```

## Backup Location

Backups are stored in:
```
C:\inetpub\podsinspace\backups\
```

Files are named: `nasa_blog_YYYY-MM-DD_HHmmss.db`

## Retention Policy

- Backups are kept for 30 days
- Older backups are automatically deleted
- Modify `$daysToKeep` in `backup_database.ps1` to change retention

## Task Management

### View the scheduled task:
```powershell
Get-ScheduledTask -TaskName "PodsinSpace Database Backup"
```

### Run the task immediately:
```powershell
Start-ScheduledTask -TaskName "PodsinSpace Database Backup"
```

### View task history:
```powershell
Get-ScheduledTaskInfo -TaskName "PodsinSpace Database Backup"
```

### Disable the task:
```powershell
Disable-ScheduledTask -TaskName "PodsinSpace Database Backup"
```

### Enable the task:
```powershell
Enable-ScheduledTask -TaskName "PodsinSpace Database Backup"
```

### Remove the task:
```powershell
Unregister-ScheduledTask -TaskName "PodsinSpace Database Backup" -Confirm:$false
```

## Monitoring

Check the backup log for status:
```powershell
Get-Content C:\inetpub\podsinspace\backups\backup_log.txt -Tail 20
```

## Restore from Backup

To restore a backup:

1. Stop the web application:
   ```powershell
   .\recycle.ps1
   ```

2. Replace the current database:
   ```powershell
   Copy-Item "backups\nasa_blog_YYYY-MM-DD_HHmmss.db" "instance\nasa_blog.db" -Force
   ```

3. Restart the web application:
   ```powershell
   .\recycle.ps1
   ```

## Troubleshooting

### Check if task exists:
```powershell
Get-ScheduledTask | Where-Object {$_.TaskName -like "*Database Backup*"}
```

### View last run result:
```powershell
(Get-ScheduledTaskInfo -TaskName "PodsinSpace Database Backup").LastTaskResult
```
- 0 = Success
- Other values = Error code

### Test backup script manually:
```powershell
.\backup_database.ps1
```

### Check backup directory:
```powershell
Get-ChildItem backups\*.db | Sort-Object LastWriteTime -Descending
```
