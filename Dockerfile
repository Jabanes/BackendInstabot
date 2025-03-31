# CACHE_BUST=2025-03-31

# ✅ Use Python slim base image
FROM python:3.10-slim

# ✅ Install minimal system dependencies required for headless browsers
RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg \
    libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libasound2 libxshmfence1 fonts-liberation libatk-bridge2.0-0 \
    libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 lsb-release \
    xdg-utils --no-install-recommends && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ✅ Set working directory
WORKDIR /app

# ✅ Copy source code
COPY backend/ .

# ✅ ✅ Debug confirmation message
RUN echo "✅ Using UPDATED Dockerfile from project root — built on 2025-03-31"

# ✅ Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# ✅ Expose port
EXPOSE 8000

# ✅ Run Django using Gunicorn
CMD ["gunicorn", "--workers=1", "--bind", "0.0.0.0:8080", "myproj.wsgi"]
