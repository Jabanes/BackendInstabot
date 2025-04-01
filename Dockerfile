# CACHE_BUST=2025-04-01

# ✅ Use Python slim base image
FROM python:3.10-slim

# ✅ Install system dependencies & Chromium
RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg \
    libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libasound2 libxshmfence1 fonts-liberation libatk-bridge2.0-0 \
    libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 lsb-release \
    chromium chromium-driver \
    xdg-utils --no-install-recommends && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ✅ Set environment variables for undetected_chromedriver
ENV CHROME_BIN="/usr/bin/chromium"
ENV CHROMEDRIVER_BIN="/usr/lib/chromium/chromedriver"
ENV PATH="${PATH}:${CHROME_BIN}:${CHROMEDRIVER_BIN}"
ENV ENVIRONMENT="production"
ENV HEADLESS=true

# ✅ Set working directory
WORKDIR /app

# ✅ Copy source code
COPY . .

# ✅ Debug confirmation
RUN echo "✅ USING DOCKERFILE inside /backend — Chromium Installed — 2025-04-01"

# ✅ Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# ✅ Expose port
EXPOSE 8000

# ✅ Run Django using Gunicorn
CMD ["gunicorn", "--workers=1", "--bind", "0.0.0.0:8080", "myproj.wsgi"]
