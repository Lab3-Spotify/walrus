#!/usr/bin/env sh

python manage.py migrate

gunicorn walrus.wsgi:application --bind 0.0.0.0:8000 --reload --workers 3 --access-logfile - --error-logfile -
