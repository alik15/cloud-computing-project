#!/bin/sh
set -e

echo "==> Creating django database if not exists..."
python manage.py shell -c "
import psycopg2, os
conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'postgres-svc'),
    port=os.environ.get('DB_PORT', '5432'),
    user=os.environ.get('POSTGRES_USER', 'appuser'),
    password=os.environ.get('POSTGRES_PASSWORD', 'apppassword'),
    dbname='appdb'
)
conn.autocommit = True
cur = conn.cursor()
cur.execute(\"SELECT 1 FROM pg_database WHERE datname='django'\")
if not cur.fetchone():
    cur.execute('CREATE DATABASE django')
    print('Created django database')
else:
    print('Django database already exists')
conn.close()
"

echo "==> Running migrations..."
python manage.py migrate --noinput auth
python manage.py migrate --noinput contenttypes
python manage.py migrate --noinput sessions

echo "==> Creating app_userprofile table if not exists..."
python manage.py shell -c "
import psycopg2, os
conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'postgres-svc'),
    port=os.environ.get('DB_PORT', '5432'),
    user=os.environ.get('POSTGRES_USER', 'appuser'),
    password=os.environ.get('POSTGRES_PASSWORD', 'apppassword'),
    dbname='django'
)
conn.autocommit = True
cur = conn.cursor()
cur.execute('''
    CREATE TABLE IF NOT EXISTS app_userprofile (
        id       SERIAL PRIMARY KEY,
        user_id  INTEGER NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE,
        location VARCHAR(100) NOT NULL DEFAULT \\'\\',
        services JSONB NOT NULL DEFAULT \\'[]\\' 
    )
''')
print('app_userprofile table ready')
conn.close()
"

echo "==> Creating superuser if not exists..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@reelkeeper.local', 'adminpass123')
    print('Superuser created')
else:
    print('Superuser already exists')
"

echo "==> Starting gunicorn..."
exec gunicorn app.wsgi:application --bind 0.0.0.0:8000 --workers 2
