FROM python:3.10-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production
ENV HEADLESS=true
ENV CHROME_BIN=/usr/bin/chromium

# Install system dependencies
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

# Set workdir
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN apt-get update && \
    apt-get install -y python3-dev build-essential && \
    pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt


# Install Chromium v135 to match ChromeDriver 135
RUN apt-get update && \
    apt-get install -y wget unzip gnupg && \
    wget https://storage.googleapis.com/chrome-for-testing-public/135.0.7049.52/linux64/chrome-linux64.zip && \
    unzip chrome-linux64.zip && \
    mv chrome-linux64 /opt/chrome && \
    ln -sf /opt/chrome/chrome /usr/bin/chromium && \
    chmod +x /usr/bin/chromium


# Copy project files
COPY . .

# Expose port (Render expects 8000)
EXPOSE 8000

# Your existing CMD – DO NOT CHANGE
CMD ["gunicorn", "myproj.wsgi:application", "--bind", "0.0.0.0:8000", "--log-level=info", "--capture-output"]
