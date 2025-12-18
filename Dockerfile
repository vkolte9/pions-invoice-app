FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for Postgres and PDF generation
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    python3-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# Use Gunicorn for production. 
# It handles multiple requests and stays alive better than 'python app.py'
CMD ["gunicorn", "-w", "4", "-k", "gthread", "-b", "0.0.0.0:5000", "app:app"]
