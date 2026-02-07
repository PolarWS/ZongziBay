#!/bin/sh

# Ensure config directory exists
mkdir -p config

# If config.yml does not exist in /app/config, copy the default one
if [ ! -f config/config.yml ]; then
    echo "Initializing config.yml in /app/config..."
    if [ -f config.yml.default ]; then
        cp config.yml.default config/config.yml
        # Attempt to update database path to use the config directory
        # We assume the default config has "path: "ZongziBay.db""
        sed -i 's|path: "ZongziBay.db"|path: "config/ZongziBay.db"|g' config/config.yml
    else
        echo "Warning: Default config.yml.default not found."
    fi
fi

# Note: Database initialization is handled by app/core/db.py on startup
# It checks if the table exists, if not, it runs the SQL script.
# We just need to make sure the app is configured to use the DB in /app/config/ZongziBay.db
# This is done by ensuring config.yml has the correct path or relies on default logic if we modified it.
# Our code modification prioritizes config/config.yml and handles DB path relative to root correctly.

echo "Starting ZongziBay..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
