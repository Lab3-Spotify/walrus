FROM python:3.10.13-slim

WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get install -y vim unzip procps && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

ENTRYPOINT ["/usr/src/app/entrypoint.sh"]

# CMD ["python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]

# CMD ["tail -f /dev/null"]
