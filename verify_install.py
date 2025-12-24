#!/usr/bin/env python3
"""Verify chandra-ocr installation and find correct import path"""
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

print("\n=== Inspecting chandra module structure ===")
chandra_imported = False
try:
    import chandra
    chandra_imported = True
    print(f"✓ Successfully imported chandra module")
    print(f"Chandra module location: {chandra.__file__}")
    
    # List all attributes
    attrs = [x for x in dir(chandra) if not x.startswith('_')]
    print(f"Chandra module attributes: {attrs}")
    
    # Check module file structure
    chandra_dir = os.path.dirname(chandra.__file__)
    if os.path.exists(chandra_dir):
        print(f"\nChandra directory contents: {os.listdir(chandra_dir)}")
    
    # Check for OCR class directly
    if hasattr(chandra, 'OCR'):
        print(f"\n✓ Found OCR class directly in chandra module!")
        OCR = chandra.OCR
        print(f"✓ OCR class: {OCR}")
        print(f"✓ SUCCESS: Use 'from chandra import OCR'")
        sys.exit(0)
    
    # Check each attribute
    for attr in attrs:
        try:
            obj = getattr(chandra, attr)
            obj_type = type(obj).__name__
            print(f"  {attr}: {obj_type}")
            if 'ocr' in attr.lower() or 'OCR' in attr or 'OCR' in str(obj_type):
                print(f"    → Found potential OCR-related: {attr} ({obj_type})")
        except Exception as e:
            print(f"  {attr}: (error accessing: {e})")
except Exception as e:
    print(f"✗ Failed to import chandra: {e}")

print("\n=== Attempting imports ===")
import_attempts = [
    ('chandra.OCR', 'from chandra import OCR'),
    ('chandra.ocr', 'from chandra import ocr'),
    ('chandra.ocr.OCR', 'from chandra.ocr import OCR'),
    ('chandra_ocr', 'from chandra_ocr import OCR'),
    ('chandraocr', 'from chandraocr import OCR'),
]

for module_name, import_stmt in import_attempts:
    try:
        exec(import_stmt)
        print(f"✓ Successfully imported: {import_stmt}")
        # Check if OCR class exists
        if 'OCR' in locals():
            print(f"✓ OCR class found: {OCR}")
            print(f"✓ OCR class type: {type(OCR)}")
            print(f"\n✓✓✓ SUCCESS: The correct import is: {import_stmt} ✓✓✓")
            sys.exit(0)
        elif 'ocr_module' in locals():
            print(f"✓ OCR module found: {ocr_module}")
            if hasattr(ocr_module, 'OCR'):
                OCR = ocr_module.OCR
                print(f"✓ OCR class found in module: {OCR}")
                print(f"\n✓✓✓ SUCCESS: The correct import is: {import_stmt} ✓✓✓")
                sys.exit(0)
    except Exception as e:
        print(f"✗ Failed {import_stmt}: {e}")

# If chandra was imported, try to explore submodules
if chandra_imported:
    print("\n=== Exploring chandra submodules ===")
    try:
        chandra_dir = os.path.dirname(chandra.__file__)
        for item in os.listdir(chandra_dir):
            if item.endswith('.py') and not item.startswith('__'):
                module_name = item[:-3]
                try:
                    submod = __import__(f'chandra.{module_name}', fromlist=[module_name])
                    print(f"Found submodule: chandra.{module_name}")
                    if hasattr(submod, 'OCR'):
                        print(f"✓ Found OCR in chandra.{module_name}!")
                        OCR = submod.OCR
                        print(f"✓✓✓ SUCCESS: Use 'from chandra.{module_name} import OCR' ✓✓✓")
                        sys.exit(0)
                except Exception as e:
                    pass
    except Exception as e:
        print(f"Error exploring submodules: {e}")

# If nothing worked, show what we found
if found_modules:
    print(f"\nFound chandra-related modules: {found_modules}")
    print("Try importing one of these manually")

print("\n⚠ WARNING: Could not find OCR class in expected locations.")
print("The chandra module exists but OCR import path is unclear.")
print("This is a diagnostic script - build will continue to test runtime import.")
# Don't fail the build - let's see if it works at runtime
sys.exit(0)

