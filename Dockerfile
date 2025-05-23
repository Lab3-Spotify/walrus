FROM python:3.10.13-slim

WORKDIR /usr/src/app

# if you want to install package to ENV, please:
# 1. intall poetry (uncomment below)
# 2. use `poetry add {package_name}` in the container
# 3. run export-requirements.sh to get the newest requirements
# 4. don't forget to use: RUN CMD ["tail -f /dev/null"] to keep the container running
# RUN pip install poetry==1.6.1
# COPY pyproject.toml poetry.lock ./

RUN apt-get update && \
    apt-get install vim -y \
    unzip

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

ENTRYPOINT ["bash", "-c"]
# CMD ["python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]


CMD ["tail -f /dev/null"]
