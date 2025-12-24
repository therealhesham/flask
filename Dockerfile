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
    pkg-config \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    tesseract-ocr \
    poppler-utils \
    libpoppler-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip setuptools wheel

# Install basic dependencies first (excluding chandra-ocr)
RUN pip install --no-cache-dir flask gunicorn torch transformers pillow numpy

# Install chandra-ocr from GitHub (more reliable than PyPI)
RUN pip install --no-cache-dir git+https://github.com/datalab-to/chandra.git || \
    (echo "GitHub install failed, trying PyPI..." && \
     pip install --no-cache-dir chandra-ocr)

# Verify chandra-ocr installation and show available attributes
RUN python3 -c "import chandra; print('✓ Chandra location:', chandra.__file__); attrs = [x for x in dir(chandra) if not x.startswith('_')]; print('✓ Chandra attributes:', attrs); import os; chandra_dir = os.path.dirname(chandra.__file__); print('✓ Chandra directory contents:', os.listdir(chandra_dir) if os.path.exists(chandra_dir) else 'N/A')" || \
    echo "⚠ WARNING: Could not import chandra properly"

# Verify installation
RUN pip show chandra-ocr || pip show chandra || echo "WARNING: chandra-ocr package info not found"

# Copy and run verification script (update verify_install.py to use correct imports like 'from chandra import process_file')
COPY verify_install.py /app/
RUN python3 /app/verify_install.py

COPY ocr_api.py /app/

# Expose the port
EXPOSE 5000

# Default command - use gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "2400", "--graceful-timeout", "120", "--keep-alive", "10", "--access-logfile", "-", "--error-logfile", "-", "ocr_api:app"]