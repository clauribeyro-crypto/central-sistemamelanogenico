web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn clinica.wsgi --bind 0.0.0.0:$PORT --workers 2
