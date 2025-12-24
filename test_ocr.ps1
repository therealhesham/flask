# Test OCR API with image file
param(
    [Parameter(Mandatory=$false)]
    [string]$ImagePath = ""
)

$uri = "http://jgw0048go40g08wwg48g0c40.31.97.55.12.sslip.io/ocr"

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
    # Set longer timeout for OCR processing (900 seconds = 15 minutes)
    $response = curl.exe -X POST $uri -F "image=@$($fileInfo.FullName)" --max-time 900 2>&1
    
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
    }
} catch {
    Write-Host "`n=== Error ===" -ForegroundColor Red
    Write-Host $_.Exception.Message
}

