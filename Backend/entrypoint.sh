#!/bin/sh
set -e

echo "Waiting for PostgreSQL database to be ready..."
python -c "
import os, sys, time
import psycopg

host = os.getenv('DB_HOST', 'db')
port = int(os.getenv('DB_PORT', 5432))
dbname = os.getenv('DB_NAME', os.getenv('POSTGRES_DB', 'routiqo'))
user = os.getenv('DB_USER', os.getenv('POSTGRES_USER', 'routiqo_user'))
password = os.getenv('DB_PASSWORD', os.getenv('POSTGRES_PASSWORD', 'routiqo_password'))

for i in range(30):
    try:
        conn = psycopg.connect(
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            connect_timeout=3
        )
        conn.close()
        print('PostgreSQL is ready!')
        sys.exit(0)
    except Exception as e:
        print(f'Waiting for PostgreSQL ({i+1}/30): {e}')
        time.sleep(1)
print('Timed out waiting for PostgreSQL')
sys.exit(1)
"

echo "Applying Django database migrations..."
python manage.py migrate --noinput

echo "Starting Routiqo backend on 0.0.0.0:8000..."
exec python manage.py runserver 0.0.0.0:8000

