#!/bin/sh

# Ensure config directory exists
mkdir -p config

# Create an empty config file marker so the Python Config class writes to
# /app/config/config.yml (on the volume) instead of /app/config.yml (in-container).
# The Config class merges this empty file with config_default.yml on startup.
if [ ! -f config/config.yml ]; then
    touch config/config.yml
fi

echo "Starting ZongziBay..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
