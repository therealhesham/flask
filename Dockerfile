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
RUN pip install --upgrade pip setuptools wheel

# Install dependencies from requirements.txt first
RUN pip install --no-cache-dir -r requirements.txt || \
    (echo "Installing from requirements.txt failed, trying individual packages..." && \
     pip install --no-cache-dir flask && \
     (pip install --no-cache-dir chandra-ocr 2>&1 || \
      (echo "PyPI install failed, trying GitHub..." && \
       pip install --no-cache-dir git+https://github.com/datalab-to/chandra.git))) && \
    (pip show chandra-ocr || pip show chandra || (echo "ERROR: chandra-ocr not installed!" && exit 1))

# Copy and run verification script
COPY verify_install.py /app/
RUN python3 /app/verify_install.py

COPY ocr_api.py /app/

# تعيين المنفذ
EXPOSE 5000

# الأمر الافتراضي
CMD ["python3", "ocr_api.py"]
