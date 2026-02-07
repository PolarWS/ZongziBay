$ErrorActionPreference = "Stop"

# Configuration
$IMAGE_NAME = "zongzibay:latest"
$OUTPUT_FILE = "zongzibay_latest.tar"

# 1. Build the image
Write-Host "----------------------------------------"
Write-Host "Step 1: Building Docker Image [$IMAGE_NAME]..."
Write-Host "----------------------------------------"
docker build -t $IMAGE_NAME .

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker build failed!"
    exit 1
}

# 2. Save the image to tar
Write-Host "`n----------------------------------------"
Write-Host "Step 2: Exporting Image to [$OUTPUT_FILE]..."
Write-Host "----------------------------------------"
docker save -o $OUTPUT_FILE $IMAGE_NAME

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker save failed!"
    exit 1
}

Write-Host "`n----------------------------------------"
Write-Host "Success! Image package created: $OUTPUT_FILE"
Write-Host "You can load it elsewhere using: docker load -i $OUTPUT_FILE"
Write-Host "----------------------------------------"
