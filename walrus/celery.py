import os

from celery import Celery

from walrus import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'walrus.settings')

app = Celery('walrus')

app.conf.broker_url = settings.CELERY_BROKER_URL
app.conf.result_backend = settings.CELERY_RESULT_BACKEND


app.autodiscover_tasks()
