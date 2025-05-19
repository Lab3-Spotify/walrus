# FROM python:3.8.13-slim-
FROM python:3.10.13-slim


WORKDIR /usr/src/app

RUN apt-get update && \
    apt-get install vim -y \
    unzip

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

# CMD ["python", "manage.py", "runserver", "0.0.0.0", "8080"]
CMD ["tail", "-f", "/dev/null"]

EXPOSE 8080