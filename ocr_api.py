from flask import Flask, request, jsonify
import os
import tempfile
import subprocess
import sys

# Try different import paths for process_file from chandra
process_file = None
OCR = None

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

# If neither found, raise error
if process_file is None and OCR is None:
    raise ImportError("Could not import process_file or OCR from chandra package. Please check chandra-ocr installation.")

app = Flask(__name__)

@app.route("/", methods=["GET"])
def hello():
    return jsonify({"message": "hello world"})

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
                    process_file(image_path, output_dir, method="hf")
                else:
                    # Fallback: use CLI command
                    result = subprocess.run(
                        ['chandra', image_path, output_dir],
                        capture_output=True,
                        text=True,
                        timeout=300
                    )
                    if result.returncode != 0:
                        raise Exception(f"CLI error: {result.stderr}")
                
                base_name = os.path.splitext(file.filename)[0]
                md_path = os.path.join(output_dir, f"{base_name}.md")
                
                if os.path.exists(md_path):
                    with open(md_path, 'r', encoding='utf-8') as f:
                        result_text = f.read()
                else:
                    # Check for other output files
                    output_files = [f for f in os.listdir(output_dir) if f.endswith('.md') or f.endswith('.txt')]
                    if output_files:
                        md_path = os.path.join(output_dir, output_files[0])
                        with open(md_path, 'r', encoding='utf-8') as f:
                            result_text = f.read()
                    else:
                        result_text = "No output generated"
                
                output = {"text": result_text}
    except Exception as e:
        output = {"error": str(e)}
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

    return jsonify(output)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)