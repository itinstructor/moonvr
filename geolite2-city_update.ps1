Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Script root and license file location
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$licenseFile = Join-Path $scriptRoot "geoip_license.txt"

# Try environment variable first
$license = $env:GEOIP_LICENSE

# Fallback to file if env var not set; ensure we always build an array before accessing .Count
if (-not $license -and (Test-Path $licenseFile)) {
    try {
        $raw = Get-Content -Path $licenseFile -ErrorAction Stop
        $lines = @()
        foreach ($ln in $raw) {
            $t = $ln.Trim()
            if ($t -ne '') { $lines += $t }
        }

        if ($lines.Count -ge 1) {
            $first = $lines[0]
            # Extract quoted key if present, otherwise take last token
            if ($first -match '"([^"]+)"') {
                $license = $matches[1]
            } elseif ($first -match "'([^']+)'") {
                $license = $matches[1]
            } else {
                $parts = $first -split '\s+'
                $license = $parts[-1]
            }
        }
    } catch {
        Write-Error "Failed reading license file ${licenseFile}: $($_.Exception.Message)"
        exit 1
    }
}

if (-not $license) {
    Write-Error "GeoIP license not found. Create geoip_license.txt containing the license key (first non-empty line) or set GEOIP_LICENSE environment variable."
    exit 1
}

# Prepare URLs and paths (encode the license key)
$encLicense = [System.Uri]::EscapeDataString($license)
$url = "https://download.maxmind.com/app/geoip_download?edition_id=GeoLite2-City&license_key=$encLicense&suffix=tar.gz"

# Paths
$destDir = Join-Path $scriptRoot "geoip"
New-Item -Path $destDir -ItemType Directory -Force | Out-Null
$tarGz = Join-Path $destDir "GeoLite2-City.tar.gz"
$tmpExtractDir = Join-Path $destDir "geolite_tmp"

# Clean any previous temporary extraction directory
if (Test-Path $tmpExtractDir) {
    try { Remove-Item -Path $tmpExtractDir -Recurse -Force } catch {}
}
New-Item -Path $tmpExtractDir -ItemType Directory -Force | Out-Null

# Download (improved error reporting)
try {
    Write-Output "Downloading GeoLite2-City tarball..."
    Invoke-WebRequest -Uri $url -OutFile $tarGz -UseBasicParsing -TimeoutSec 120 -ErrorAction Stop
} catch {
    $err = $_
    $errMsg = if ($err.Exception) { $err.Exception.Message } else { $err.ToString() }

    try {
        if ($err.Exception -is [System.Net.WebException] -and $err.Exception.Response -ne $null) {
            $resp = $err.Exception.Response
            $stream = $resp.GetResponseStream()
            if ($stream) {
                $sr = New-Object System.IO.StreamReader($stream)
                $body = $sr.ReadToEnd()
                if ($body -and $body.Trim().Length -gt 0) {
                    Write-Error "Download failed (HTTP response body): $body"
                } else {
                    Write-Error "Download failed: $errMsg (empty response body)"
                }
            } else {
                Write-Error "Download failed: $errMsg (no response stream available)"
            }
        } else {
            Write-Error "Download failed: $errMsg"
        }
    } catch {
        Write-Error "Download failed and response could not be read: $($_.Exception.Message)"
    }

    Remove-Item -Path $tarGz -ErrorAction SilentlyContinue
    exit 2
}

# Extract - prefer tar if available, otherwise try 7z if installed
$extracted = $false
try {
    if (Get-Command tar -ErrorAction SilentlyContinue) {
        Write-Output "Extracting with tar..."
        & tar -xzf $tarGz -C $tmpExtractDir
        $extracted = $true
    } elseif (Get-Command 7z -ErrorAction SilentlyContinue) {
        Write-Output "Extracting with 7z..."
        # Extract tar.gz with 7z via two-step extraction
        & 7z x -y -o"$tmpExtractDir" $tarGz | Out-Null
        $extracted = $true
    } else {
        throw "No extraction tool (tar or 7z) found on PATH."
    }
} catch {
    Write-Error "Failed to extract ${tarGz}: $($_.Exception.Message)"
    Remove-Item -Path $tarGz -ErrorAction SilentlyContinue
    Remove-Item -Path $tmpExtractDir -Recurse -Force -ErrorAction SilentlyContinue
    exit 3
}

$mmdbFiles = @(Get-ChildItem -Path $tmpExtractDir -Recurse -Filter "GeoLite2-City.mmdb" -ErrorAction SilentlyContinue)
if (-not $mmdbFiles -or $mmdbFiles.Count -eq 0) {
    # Sometimes the file name is different in nested dir; search for *.mmdb
    $mmdbFiles = @(Get-ChildItem -Path $tmpExtractDir -Recurse -Filter "*.mmdb" -ErrorAction SilentlyContinue)
}

if (-not $mmdbFiles -or $mmdbFiles.Count -eq 0) {
    Write-Error "MMDB file not found after extraction."
    Remove-Item -Path $tarGz -ErrorAction SilentlyContinue
    Remove-Item -Path $tmpExtractDir -Recurse -Force -ErrorAction SilentlyContinue
    exit 4
}

try {
    $targetMmdb = Join-Path $destDir "GeoLite2-City.mmdb"
    # Backup existing file if present
    if (Test-Path $targetMmdb) {
        $backup = Join-Path $destDir ("GeoLite2-City.mmdb.bak." + (Get-Date -Format "yyyyMMddHHmmss"))
        Move-Item -Path $targetMmdb -Destination $backup -Force
        Write-Output "Existing MMDB backed up to $backup"
    }
    # Move first found mmdb to target location
    Move-Item -Path $mmdbFiles[0].FullName -Destination $targetMmdb -Force
    Write-Output "Installed GeoLite2-City.mmdb to $targetMmdb"
} catch {
    Write-Error "Failed to move mmdb file: $($_.Exception.Message)"
    Remove-Item -Path $tarGz -ErrorAction SilentlyContinue
    Remove-Item -Path $tmpExtractDir -Recurse -Force -ErrorAction SilentlyContinue
    exit 3
}

# Cleanup
Remove-Item -Path $tarGz -Force -ErrorAction SilentlyContinue
try { Remove-Item -Path $tmpExtractDir -Recurse -Force } catch {}

Write-Output "GeoLite2-City update completed successfully."
exit 0