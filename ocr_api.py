from flask import Flask, request, jsonify
import os
import tempfile
import subprocess
import sys

# Try different import paths for process_file from chandra
process_file = None
OCR = None

# Diagnostic: Check what's available in chandra package
try:
    import chandra
    print(f"✓ chandra module imported successfully from: {chandra.__file__}")
    print(f"Available attributes: {[x for x in dir(chandra) if not x.startswith('_')]}")
except ImportError as e:
    print(f"⚠ Could not import chandra module: {e}")

# First, try to import process_file
import_paths = [
    ('chandra', 'process_file'),
    ('chandra.processing', 'process_file'),
    ('chandra.core', 'process_file'),
    ('chandra.utils', 'process_file'),
    ('chandra.cli', 'process_file'),
]

for module_path, func_name in import_paths:
    try:
        module = __import__(module_path, fromlist=[func_name])
        if hasattr(module, func_name):
            process_file = getattr(module, func_name)
            print(f"✓ Found process_file in {module_path}")
            break
    except (ImportError, AttributeError):
        continue

# If process_file not found, try to import OCR class
if process_file is None:
    try:
        from chandra import OCR
        print("✓ Found OCR class in chandra")
    except ImportError:
        try:
            from chandra_ocr import OCR
            print("✓ Found OCR class in chandra_ocr")
        except ImportError:
            # Try alternative import paths
            try:
                import chandra
                if hasattr(chandra, 'OCR'):
                    OCR = chandra.OCR
                    print("✓ Found OCR class via chandra.OCR")
                elif hasattr(chandra, 'ocr'):
                    OCR = chandra.ocr.OCR
                    print("✓ Found OCR class via chandra.ocr.OCR")
            except Exception as e:
                print(f"⚠ Could not import OCR class: {e}")
                pass

# Check if we have at least one working method
if process_file is None and OCR is None:
    print("⚠ WARNING: Could not find process_file or OCR class.")
    print("⚠ Please ensure chandra-ocr is properly installed.")

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
            raise Exception("No OCR method available. Please ensure chandra-ocr is properly installed with either OCR class or process_file function.")
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