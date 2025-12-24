from flask import Flask, request, jsonify
import os
import tempfile
from chandra import process_file

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
        with tempfile.TemporaryDirectory() as output_dir:
            process_file(image_path, output_dir, method="hf")  # Use 'hf' for local HuggingFace inference on CPU (may be slow)
            
            base_name = os.path.splitext(file.filename)[0]
            md_path = os.path.join(output_dir, f"{base_name}.md")
            
            if os.path.exists(md_path):
                with open(md_path, 'r') as f:
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