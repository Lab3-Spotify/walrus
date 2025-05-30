#!/usr/bin/env sh

gunicorn walrus.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile - --error-logfile -
