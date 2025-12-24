FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY ocr_api.py /app/

# تعيين المنفذ
EXPOSE 5000

# الأمر الافتراضي
CMD ["python3", "ocr_api.py"]
