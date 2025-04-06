# Use an official Python base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV ENVIRONMENT=production
ENV HEADLESS=true
ENV CHROME_BIN=/usr/bin/chromium

# Set work directory
WORKDIR /app

# Install system dependencies (for Selenium + Chromium)
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    curl \
    unzip \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libnspr4 \
    libnss3 \
    libxss1 \
    xdg-utils \
    libgbm-dev \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project files
COPY . .

# Run collectstatic if using Django static files
# RUN python manage.py collectstatic --noinput

# Expose port (Railway will automatically bind to this)
EXPOSE 8000

# Run with gunicorn for production
CMD ["gunicorn", "myproj.wsgi:application", "--bind", "0.0.0.0:8000", "--log-level=info", "--capture-output" ]