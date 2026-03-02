FROM python:3.11-slim

WORKDIR /app

# instala deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copia o código
COPY app ./app

# Railway injeta PORT automaticamente
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

CMD ["bash","-lc","uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
