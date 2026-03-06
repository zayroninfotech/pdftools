#!/bin/bash
set -e

echo "Starting PDF Tools application..."
echo "PORT: $PORT"
echo "MONGODB_URI: $MONGODB_URI"
echo "SECRET_KEY: ${SECRET_KEY:0:10}..."

# Try to load Django first
python -c "import django; django.setup()" 2>&1 || {
    echo "ERROR: Django setup failed!"
    exit 1
}

echo "Django setup successful, starting gunicorn..."
gunicorn pdftools.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers 1 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level debug
