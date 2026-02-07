#!/bin/bash
set -e

# Configuration
IMAGE_NAME="zongzibay:latest"
OUTPUT_FILE="zongzibay_latest.tar"

# 1. Build the image
echo "----------------------------------------"
echo "Step 1: Building Docker Image [$IMAGE_NAME]..."
echo "----------------------------------------"
docker build -t "$IMAGE_NAME" .

# 2. Save the image to tar
echo ""
echo "----------------------------------------"
echo "Step 2: Exporting Image to [$OUTPUT_FILE]..."
echo "----------------------------------------"
docker save -o "$OUTPUT_FILE" "$IMAGE_NAME"

echo ""
echo "----------------------------------------"
echo "Success! Image package created: $OUTPUT_FILE"
echo "You can load it elsewhere using: docker load -i $OUTPUT_FILE"
echo "----------------------------------------"
