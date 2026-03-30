FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git curl ffmpeg libsm6 libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright
RUN playwright install chromium --with-deps 2>/dev/null || playwright install chromium

COPY . .

EXPOSE 37779

CMD ["python3", "robo_mae_api.py"]
