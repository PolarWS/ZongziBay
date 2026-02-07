# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /web

# Copy package.json and package-lock.json first to leverage cache
COPY web/package.json web/package-lock.json ./

# Install dependencies
RUN npm install --registry=https://registry.npmmirror.com

# Copy the rest of the frontend code
COPY web .

# Build the frontend (static site generation)
RUN npm run generate

# Stage 2: Build Backend and Final Image
FROM python:3.12-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (if needed)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY app ./app
COPY sql ./sql
COPY config.yml ./config.yml.default

# Copy built frontend from Stage 1
COPY --from=frontend-builder /web/.output/public ./web/.output/public

# Create config directory for volume mounting
RUN mkdir -p config

# Copy entrypoint script
COPY entrypoint.sh .
RUN sed -i 's/\r$//' entrypoint.sh
RUN chmod +x entrypoint.sh

# Expose port
EXPOSE 8000

# Volume for configuration and database
VOLUME ["/app/config"]

# Entrypoint
ENTRYPOINT ["./entrypoint.sh"]
