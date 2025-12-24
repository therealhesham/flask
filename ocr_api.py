from flask import Flask, request, jsonify
import os
import tempfile
import subprocess
import sys

# Try different import paths for process_file from chandra
process_file = None
OCR = None

# Diagnostic: Check what's available in chandra package
chandra_module = None
chandra_attrs = []

try:
    import chandra
    chandra_module = chandra
    chandra_attrs = [x for x in dir(chandra) if not x.startswith('_')]
    print(f"✓ chandra module imported successfully from: {chandra.__file__}")
    print(f"Available attributes: {chandra_attrs}")
except ImportError as e:
    print(f"⚠ Could not import chandra module: {e}")

# Also try chandra_ocr (with underscore)
try:
    import chandra_ocr
    print(f"✓ chandra_ocr module imported successfully from: {chandra_ocr.__file__}")
    chandra_ocr_attrs = [x for x in dir(chandra_ocr) if not x.startswith('_')]
    print(f"Available attributes: {chandra_ocr_attrs}")
    # Merge attributes if chandra_module is None
    if chandra_module is None:
        chandra_module = chandra_ocr
        chandra_attrs = chandra_ocr_attrs
except ImportError as e:
    print(f"⚠ Could not import chandra_ocr module: {e}")

# First, try to import process_file from various locations
import_paths = [
    ('chandra', 'process_file'),
    ('chandra_ocr', 'process_file'),
    ('chandra.processing', 'process_file'),
    ('chandra.core', 'process_file'),
    ('chandra.utils', 'process_file'),
    ('chandra.cli', 'process_file'),
    ('chandra_ocr.processing', 'process_file'),
    ('chandra_ocr.core', 'process_file'),
]

for module_path, func_name in import_paths:
    try:
        module = __import__(module_path, fromlist=[func_name])
        if hasattr(module, func_name):
            process_file = getattr(module, func_name)
            print(f"✓ Found process_file in {module_path}")
            break
    except (ImportError, AttributeError) as e:
        continue

# If process_file not found, try to import OCR class from various locations
if process_file is None:
    ocr_import_paths = [
        ('chandra', 'OCR'),
        ('chandra_ocr', 'OCR'),
        ('chandra.ocr', 'OCR'),
        ('chandra_ocr.ocr', 'OCR'),
    ]
    
    for module_path, class_name in ocr_import_paths:
        try:
            module = __import__(module_path, fromlist=[class_name])
            if hasattr(module, class_name):
                OCR = getattr(module, class_name)
                print(f"✓ Found OCR class in {module_path}")
                break
        except (ImportError, AttributeError):
            continue
    
    # If still not found, try direct attribute access on imported modules
    if OCR is None and chandra_module is not None:
        # Check direct attributes
        if hasattr(chandra_module, 'OCR'):
            OCR = chandra_module.OCR
            print("✓ Found OCR class via direct attribute access")
        elif hasattr(chandra_module, 'ocr'):
            ocr_submodule = getattr(chandra_module, 'ocr')
            if hasattr(ocr_submodule, 'OCR'):
                OCR = ocr_submodule.OCR
                print("✓ Found OCR class via chandra.ocr.OCR")
        
        # Explore submodules dynamically
        if OCR is None:
            try:
                import os
                chandra_dir = os.path.dirname(chandra_module.__file__)
                if os.path.exists(chandra_dir):
                    for item in os.listdir(chandra_dir):
                        if item.endswith('.py') and not item.startswith('__'):
                            module_name = item[:-3]
                            try:
                                submod = __import__(f'{chandra_module.__name__}.{module_name}', 
                                                   fromlist=[module_name])
                                if hasattr(submod, 'OCR'):
                                    OCR = submod.OCR
                                    print(f"✓ Found OCR class in {chandra_module.__name__}.{module_name}")
                                    break
                                elif hasattr(submod, 'process_file'):
                                    process_file = submod.process_file
                                    print(f"✓ Found process_file in {chandra_module.__name__}.{module_name}")
                                    break
                            except Exception:
                                pass
            except Exception as e:
                print(f"⚠ Error exploring submodules: {e}")

# Check if we have at least one working method
if process_file is None and OCR is None:
    print("⚠ WARNING: Could not find process_file or OCR class.")
    print("⚠ Please ensure chandra-ocr is properly installed.")
    if chandra_module:
        print(f"⚠ Available attributes in {chandra_module.__name__}: {chandra_attrs}")
        print("⚠ Try checking the chandra-ocr documentation for the correct import path.")

app = Flask(__name__)

@app.route("/", methods=["GET"])
def hello():
    return jsonify({"message": "hello world", "status": "ok"})

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "ocr-api"}), 200

@app.route("/diagnostics", methods=["GET"])
def diagnostics():
    """Diagnostic endpoint to check chandra package availability"""
    diagnostics_info = {
        "process_file_available": process_file is not None,
        "OCR_available": OCR is not None,
        "chandra_module": None,
        "chandra_ocr_module": None,
        "cli_available": False,
    }
    
    # Try to get more info about chandra module
    try:
        import chandra
        diagnostics_info["chandra_module"] = {
            "location": chandra.__file__,
            "attributes": [x for x in dir(chandra) if not x.startswith('_')]
        }
    except Exception as e:
        diagnostics_info["chandra_module"] = {"error": str(e)}
    
    # Try to get more info about chandra_ocr module
    try:
        import chandra_ocr
        diagnostics_info["chandra_ocr_module"] = {
            "location": chandra_ocr.__file__,
            "attributes": [x for x in dir(chandra_ocr) if not x.startswith('_')]
        }
    except Exception as e:
        diagnostics_info["chandra_ocr_module"] = {"error": str(e)}
    
    # Check if CLI is available
    try:
        result = subprocess.run(['chandra', '--help'], 
                              capture_output=True, 
                              text=True, 
                              timeout=5)
        diagnostics_info["cli_available"] = result.returncode == 0
        if diagnostics_info["cli_available"]:
            diagnostics_info["cli_help"] = result.stdout[:500]  # First 500 chars
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        diagnostics_info["cli_available"] = False
    
    return jsonify(diagnostics_info)

@app.route("/ocr", methods=["POST"])
def ocr_image():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    image_path = os.path.join("/tmp", file.filename)
    file.save(image_path)

    try:
        if OCR is not None:
            # Use OCR class if available (direct method, no output directory needed)
            print(f"Using OCR class for image: {image_path}")
            ocr_instance = OCR(device="cpu")
            result_text = ocr_instance.read_image(image_path)
            output = {"text": result_text}
        elif process_file is not None:
            # Use process_file function (requires output directory)
            print(f"Using process_file for image: {image_path}")
            with tempfile.TemporaryDirectory() as output_dir:
                try:
                    # Try different method parameters
                    try:
                        process_file(image_path, output_dir, method="hf")
                    except Exception as e1:
                        print(f"process_file with method='hf' failed: {e1}, trying without method parameter")
                        try:
                            process_file(image_path, output_dir)
                        except Exception as e2:
                            print(f"process_file without method parameter failed: {e2}")
                            raise Exception(f"process_file failed: {e2}")
                    
                    # Find output file (chandra creates markdown files)
                    base_name = os.path.splitext(os.path.basename(file.filename))[0]
                    md_path = os.path.join(output_dir, f"{base_name}.md")
                    
                    if os.path.exists(md_path):
                        with open(md_path, 'r', encoding='utf-8') as f:
                            result_text = f.read()
                    else:
                        # Check for any markdown or text files in output directory
                        output_files = [f for f in os.listdir(output_dir) 
                                       if f.endswith(('.md', '.txt', '.markdown'))]
                        if output_files:
                            md_path = os.path.join(output_dir, output_files[0])
                            with open(md_path, 'r', encoding='utf-8') as f:
                                result_text = f.read()
                        else:
                            # List what files were created for debugging
                            created_files = os.listdir(output_dir)
                            result_text = f"No output file found. Created files: {created_files}"
                    
                    output = {"text": result_text}
                except Exception as e:
                    raise Exception(f"Failed to process image with process_file: {str(e)}")
        else:
            # Provide detailed error message with diagnostic info
            error_details = ["No OCR method available. Please ensure chandra-ocr is properly installed with either OCR class or process_file function."]
            
            # Add diagnostic information
            if chandra_module:
                error_details.append(f"Found chandra module at: {chandra_module.__file__}")
                error_details.append(f"Available attributes: {chandra_attrs}")
            else:
                error_details.append("Could not import chandra module. Try: pip install git+https://github.com/datalab-to/chandra.git")
            
            error_details.append("Check /diagnostics endpoint for more information.")
            raise Exception(" ".join(error_details))
    except Exception as e:
        error_msg = str(e)
        print(f"ERROR processing image: {error_msg}")
        # Return error with status code 500 for server errors, 400 for client errors
        status_code = 500 if "No OCR method available" in error_msg or "Failed to process" in error_msg else 400
        output = {"error": error_msg}
        return jsonify(output), status_code
    finally:
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                print(f"Warning: Could not remove temp file {image_path}: {e}")

    return jsonify(output)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)