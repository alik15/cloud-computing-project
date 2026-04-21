#!/bin/sh
set -e

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Creating superuser if not exists..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@reelkeeper.local', 'adminpass123')
    print('Superuser created: admin / adminpass123')
else:
    print('Superuser already exists')
"

echo "==> Starting gunicorn..."
exec gunicorn app.wsgi:application --bind 0.0.0.0:8000 --workers 2
