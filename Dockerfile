FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    libgl1 \
    libglib2.0-0 \
    build-essential \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -v -r requirements.txt

# Verify installation
RUN pip show chandra-ocr || (echo "ERROR: chandra-ocr package not found" && pip list && exit 1) && \
    python3 -c "import chandra_ocr; print('✓ chandra_ocr imported successfully')" || \
    (echo "ERROR: Failed to import chandra_ocr module" && python3 -c "import sys; print(sys.path)" && exit 1)

COPY ocr_api.py /app/

# تعيين المنفذ
EXPOSE 5000

# الأمر الافتراضي
CMD ["python3", "ocr_api.py"]
