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

# Install chandra-ocr - try GitHub repo if PyPI doesn't work
RUN pip install --no-cache-dir flask && \
    (pip install --no-cache-dir chandra-ocr || \
     pip install --no-cache-dir git+https://github.com/datalab-to/chandra.git)

# Verify the installation and find the correct import path
RUN python3 << 'PYEOF'
import sys
import os
import site
import subprocess

print("=== Checking installed packages ===")
result = subprocess.run([sys.executable, "-m", "pip", "show", "chandra-ocr"], 
                       capture_output=True, text=True)
if result.returncode == 0:
    print(result.stdout)
else:
    print("chandra-ocr package not found via pip show")

print("\n=== Checking site-packages for chandra modules ===")
found_modules = []
for sp in site.getsitepackages():
    if os.path.exists(sp):
        for item in os.listdir(sp):
            if 'chandra' in item.lower() and (item.endswith('.py') or os.path.isdir(os.path.join(sp, item))):
                found_modules.append(item)
                print(f"Found: {item}")

print("\n=== Attempting imports ===")
import_attempts = [
    ('chandra_ocr', 'from chandra_ocr import OCR'),
    ('chandraocr', 'from chandraocr import OCR'),
    ('chandra.ocr', 'from chandra import ocr'),
]

for module_name, import_stmt in import_attempts:
    try:
        exec(import_stmt)
        print(f"✓ Successfully imported: {import_stmt}")
        # Check if OCR class exists
        if 'OCR' in locals():
            print(f"✓ OCR class found: {OCR}")
        sys.exit(0)
    except Exception as e:
        print(f"✗ Failed {import_stmt}: {e}")

# If nothing worked, show what we found
if found_modules:
    print(f"\nFound chandra-related modules: {found_modules}")
    print("Try importing one of these manually")

print("\nERROR: Could not import chandra_ocr.OCR")
sys.exit(1)
PYEOF

COPY ocr_api.py /app/

# تعيين المنفذ
EXPOSE 5000

# الأمر الافتراضي
CMD ["python3", "ocr_api.py"]
