# Use official lightweight Python image
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies required by psycopg2 & reportlab
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    build-essential \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Expose port
EXPOSE 5000

# Start app
CMD ["python", "app.py"]
