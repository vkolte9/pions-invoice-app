FROM python:3.11-slim

# System deps + MS SQL ODBC driver
RUN apt-get update && apt-get install -y curl gnupg apt-transport-https unixodbc unixodbc-dev \
 && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
 && curl https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

ENV PORT=10000
CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
