# Test OCR API with image file
param(
    [Parameter(Mandatory=$false)]
    [string]$ImagePath = ""
)

# Try direct access first (without sslip.io), fallback to sslip.io
$directUri = "http://31.97.55.12:5000/ocr"
$sslipUri = "http://jgw0048go40g08wwg48g0c40.31.97.55.12.sslip.io/ocr"

# Check which URL to use - try direct first
$uri = $directUri
Write-Host "`n=== Testing Connection ===" -ForegroundColor Cyan
try {
    $testResponse = curl.exe -X GET "http://31.97.55.12:5000/health" --max-time 5 --silent 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Direct connection works, using: $uri" -ForegroundColor Green
    } else {
        Write-Host "⚠ Direct connection failed, trying sslip.io: $sslipUri" -ForegroundColor Yellow
        $uri = $sslipUri
    }
} catch {
    Write-Host "⚠ Direct connection failed, using sslip.io: $sslipUri" -ForegroundColor Yellow
    $uri = $sslipUri
}

# If no path provided, search for images on Desktop
if ([string]::IsNullOrEmpty($ImagePath)) {
    Write-Host "No image path provided. Searching for images on Desktop..." -ForegroundColor Yellow
    $images = Get-ChildItem -Path "$env:USERPROFILE\Desktop" -Include *.png,*.jpg,*.jpeg -Recurse -ErrorAction SilentlyContinue | 
              Where-Object {$_.Length -lt 2MB} | 
              Select-Object -First 1
    
    if ($images) {
        $ImagePath = $images.FullName
        Write-Host "Found image: $ImagePath" -ForegroundColor Green
    } else {
        Write-Host "No images found on Desktop. Please provide image path." -ForegroundColor Red
        Write-Host "Usage: .\test_ocr.ps1 -ImagePath 'C:\path\to\image.png'" -ForegroundColor Yellow
        exit 1
    }
}

if (-not (Test-Path $ImagePath)) {
    Write-Host "File not found: $ImagePath" -ForegroundColor Red
    exit 1
}

$fileInfo = Get-Item $ImagePath
Write-Host "`n=== Testing OCR API ===" -ForegroundColor Cyan
Write-Host "Image: $($fileInfo.FullName)" -ForegroundColor White
Write-Host "Size: $([math]::Round($fileInfo.Length/1KB, 2)) KB" -ForegroundColor White
Write-Host "URL: $uri" -ForegroundColor White
Write-Host "`nSending request..." -ForegroundColor Yellow

try {
    # Set longer timeout for OCR processing (2400 seconds = 40 minutes)
    # Add verbose output to see what's happening
    Write-Host "Timeout set to: 2400 seconds (40 minutes)" -ForegroundColor Cyan
    Write-Host "Note: If using sslip.io, it may have its own timeout limit!" -ForegroundColor Yellow
    Write-Host "Start time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
    
    $response = curl.exe -X POST $uri -F "image=@$($fileInfo.FullName)" --max-time 2400 --show-error 2>&1
    
    Write-Host "End time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
    
    # Extract JSON response (usually the last line)
    $jsonResponse = $response | Select-String -Pattern '\{.*\}' | Select-Object -Last 1
    
    if ($jsonResponse) {
        Write-Host "`n=== Response ===" -ForegroundColor Green
        $json = $jsonResponse.Matches.Value | ConvertFrom-Json
        
        if ($json.error) {
            Write-Host "Error: $($json.error)" -ForegroundColor Red
        } elseif ($json.text) {
            Write-Host "OCR Text:" -ForegroundColor Green
            Write-Host $json.text -ForegroundColor White
        } else {
            Write-Host ($json | ConvertTo-Json -Depth 10) -ForegroundColor White
        }
    } else {
        Write-Host "`n=== Raw Response ===" -ForegroundColor Yellow
        Write-Host $response
        
        # Check if it's a timeout error
        if ($response -match "timeout|Timeout|timed out") {
            Write-Host "`n=== TIMEOUT DETECTED ===" -ForegroundColor Red
            Write-Host "This timeout may be from:" -ForegroundColor Yellow
            Write-Host "1. sslip.io reverse proxy (if using sslip.io URL)" -ForegroundColor Yellow
            Write-Host "2. Network/firewall timeout" -ForegroundColor Yellow
            Write-Host "3. The OCR process taking too long" -ForegroundColor Yellow
            Write-Host "`nTry:" -ForegroundColor Cyan
            Write-Host "- Access directly: http://31.97.55.12:5000/ocr" -ForegroundColor White
            Write-Host "- Use a smaller/simpler image" -ForegroundColor White
            Write-Host "- Check server logs: docker logs <container>" -ForegroundColor White
        }
    }
} catch {
    Write-Host "`n=== Error ===" -ForegroundColor Red
    Write-Host $_.Exception.Message
    
    if ($_.Exception.Message -match "timeout|Timeout") {
        Write-Host "`n=== TIMEOUT ERROR ===" -ForegroundColor Red
        Write-Host "The timeout is likely from sslip.io or network." -ForegroundColor Yellow
        Write-Host "Try accessing directly: http://31.97.55.12:5000/ocr" -ForegroundColor Cyan
    }
}

