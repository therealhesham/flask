#!/usr/bin/env python3
"""Test script to verify chandra_ocr installation"""
import sys

try:
    from chandra_ocr import OCR
    print("✓ Successfully imported chandra_ocr")
    print(f"✓ OCR class: {OCR}")
    sys.exit(0)
except ImportError as e:
    print(f"✗ Failed to import chandra_ocr: {e}")
    print("\nTrying to check installed packages...")
    import subprocess
    result = subprocess.run([sys.executable, "-m", "pip", "list"], 
                          capture_output=True, text=True)
    print(result.stdout)
    if "chandra" in result.stdout.lower():
        print("\n⚠ chandra-ocr appears to be installed but cannot be imported")
    else:
        print("\n⚠ chandra-ocr is not installed")
    sys.exit(1)

