#!/bin/bash

echo "Starting PDF Tools application..."
PORT=${PORT:-8000}
echo "Using PORT: $PORT"
echo "MONGODB_URI is set: $([ -z $MONGODB_URI ] && echo 'NO' || echo 'YES')"

# Run migrations to create database tables
echo "Running database migrations..."
python manage.py migrate --run-syncdb

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# Run gunicorn
exec gunicorn pdftools.wsgi:application \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
