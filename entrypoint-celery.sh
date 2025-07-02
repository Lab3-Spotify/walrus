#!/bin/bash
# entrypoint-celery.sh


QUEUE=${1:-playlog}
celery -A walrus worker -Q $QUEUE --concurrency=1 --loglevel=info -n ${QUEUE}_worker@%h
