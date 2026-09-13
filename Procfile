web: python manage.py migrate --noinput && python manage.py collectstatic --noinput && python -m gunicorn clinica.wsgi --bind 0.0.0.0:$PORT --workers 2
