import os
import time

import redis

host = os.environ.get('REDIS_HOST', 'localhost')
port = int(os.environ.get('REDIS_PORT', 6379))

print(f'Waiting for Redis at {host}:{port}...')
while True:
    try:
        r = redis.Redis(host=host, port=port)
        r.ping()
        print('Redis is ready')
        break
    except Exception as e:
        print(f'  Still waiting... ({e})')
        time.sleep(2)
