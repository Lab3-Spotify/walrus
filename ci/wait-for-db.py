import os
import time

import psycopg2

host = os.environ.get('POSTGRES_HOST', 'localhost')
port = int(os.environ.get('POSTGRES_PORT', 5432))
user = os.environ.get('POSTGRES_USER', 'postgres')
password = os.environ.get('POSTGRES_PASSWORD', '')
dbname = os.environ.get('POSTGRES_DB', 'postgres')

print(f'Waiting for PostgreSQL at {host}:{port}...')
while True:
    try:
        conn = psycopg2.connect(
            host=host, port=port, user=user, password=password, dbname=dbname
        )
        conn.close()
        print('PostgreSQL is ready')
        break
    except Exception as e:
        print(f'  Still waiting... ({e})')
        time.sleep(2)
