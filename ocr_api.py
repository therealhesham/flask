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
            pass

# Check if CLI is available (try both direct command and python -m)
cli_available = False
cli_command = None

# Try direct 'chandra' command
try:
    result = subprocess.run(['chandra', '--help'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0 or 'chandra' in result.stderr.lower() or 'chandra' in result.stdout.lower():
        cli_available = True
        cli_command = ['chandra']
        print("✓ chandra CLI command is available")
except (FileNotFoundError, subprocess.TimeoutExpired):
    pass

# Try 'python -m chandra' if direct command not found
if not cli_available:
    try:
        result = subprocess.run([sys.executable, '-m', 'chandra', '--help'], 
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0 or 'chandra' in result.stderr.lower() or 'chandra' in result.stdout.lower():
            cli_available = True
            cli_command = [sys.executable, '-m', 'chandra']
            print("✓ chandra CLI available via 'python -m chandra'")
    except Exception:
        pass

if not cli_available:
    print("⚠ chandra CLI command not found (tried 'chandra' and 'python -m chandra')")

# If nothing found, use CLI as fallback (don't fail at import time)
if process_file is None and OCR is None and not cli_available:
    print("⚠ WARNING: Could not find process_file, OCR class, or CLI. Will attempt to use CLI anyway.")

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
        "cli_available": cli_available,
        "cli_command": cli_command if cli_command else None,
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
    
    # Check CLI
    try:
        result = subprocess.run(['which', 'chandra'], capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            diagnostics_info["cli_path"] = result.stdout.strip()
        else:
            # Try on Windows
            result = subprocess.run(['where', 'chandra'], capture_output=True, text=True, timeout=2, shell=True)
            if result.returncode == 0:
                diagnostics_info["cli_path"] = result.stdout.strip()
    except Exception as e:
        diagnostics_info["cli_check_error"] = str(e)
    
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
            ocr_instance = OCR(device="cpu")
            result_text = ocr_instance.read_image(image_path)
            output = {"text": result_text}
        else:
            # Use process_file or CLI (requires output directory)
            with tempfile.TemporaryDirectory() as output_dir:
                if process_file is not None:
                    # Use process_file function if available
                    try:
                        process_file(image_path, output_dir, method="hf")
                    except Exception as e:
                        print(f"process_file failed: {e}, falling back to CLI")
                        # Fall back to CLI if process_file fails
                        if cli_command:
                            result = subprocess.run(
                                cli_command + [image_path, output_dir],
                                capture_output=True,
                                text=True,
                                timeout=300
                            )
                            if result.returncode != 0:
                                raise Exception(f"CLI error: {result.stderr}")
                        else:
                            raise Exception(f"process_file failed and CLI not available: {e}")
                else:
                    # Use CLI command (primary method based on documentation)
                    if cli_command:
                        result = subprocess.run(
                            cli_command + [image_path, output_dir],
                            capture_output=True,
                            text=True,
                            timeout=300
                        )
                        if result.returncode != 0:
                            error_msg = result.stderr if result.stderr else result.stdout
                            raise Exception(f"CLI error (exit code {result.returncode}): {error_msg}")
                    else:
                        raise Exception("No OCR method available: process_file, OCR class, and CLI are all unavailable")
                
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
        output = {"error": str(e)}
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

    return jsonify(output)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)