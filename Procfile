web: python manage.py migrate --run-syncdb && python manage.py collectstatic --no-input && gunicorn pdftools.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
