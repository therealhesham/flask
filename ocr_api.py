from flask import Flask, request, jsonify
import os
import torch
import logging
from PIL import Image
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variables for the model
MODEL_INSTANCE = None
MODEL_TYPE = None # 'OCR', 'InferenceManager', or 'process_file'

def initialize_chandra():
    global MODEL_INSTANCE, MODEL_TYPE
    
    # Determine device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    try:
        # Attempt 1: InferenceManager (The most common modern entry point for Chandra)
        try:
            from chandra.models import InferenceManager
            MODEL_INSTANCE = InferenceManager(device=device)
            MODEL_TYPE = 'InferenceManager'
            logger.info("✓ Initialized InferenceManager from chandra.models")
            return
        except ImportError:
            pass

        # Attempt 2: OCR class
        try:
            from chandra import OCR
            MODEL_INSTANCE = OCR(device=device)
            MODEL_TYPE = 'OCR'
            logger.info("✓ Initialized OCR class from chandra")
            return
        except ImportError:
            pass

        # Attempt 3: process_file (Legacy/CLI style)
        try:
            from chandra import process_file
            MODEL_INSTANCE = process_file
            MODEL_TYPE = 'process_file'
            logger.info("✓ Found process_file function")
            return
        except ImportError:
            pass

    except Exception as e:
        logger.error(f"Failed to initialize Chandra: {e}")

# Run initialization
initialize_chandra()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy" if MODEL_TYPE else "degraded",
        "model_loaded": MODEL_TYPE,
        "device": "cuda" if torch.cuda.is_available() else "cpu"
    })

@app.route("/ocr", methods=["POST"])
def ocr_image():
    if not MODEL_INSTANCE:
        return jsonify({"error": "OCR engine not initialized. Check server logs."}), 500
    
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    
    # Use a secure temp directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        image_path = os.path.join(tmp_dir, file.filename)
        file.save(image_path)

        try:
            if MODEL_TYPE == 'InferenceManager':
                # InferenceManager usually expects a batch: list of dicts
                # Most Chandra versions use 'image' and 'prompt' keys
                batch = [{
                    'image': image_path,
                    'prompt': 'ocr' # Standard prompt for GOT-OCR based models
                }]
                
                # Try the .generate method (common for transformer models)
                if hasattr(MODEL_INSTANCE, 'generate'):
                    result = MODEL_INSTANCE.generate(batch=batch)
                else:
                    # Fallback to direct call
                    result = MODEL_INSTANCE(batch)
                
                # Handle return formats (list vs string)
                if isinstance(result, list) and len(result) > 0:
                    text = result[0]
                else:
                    text = str(result)

            elif MODEL_TYPE == 'OCR':
                # Direct OCR class usage
                text = MODEL_INSTANCE.read_image(image_path)

            elif MODEL_TYPE == 'process_file':
                # process_file writes to a directory
                MODEL_INSTANCE(image_path, tmp_dir)
                # Find the generated markdown file
                files = os.listdir(tmp_dir)
                md_files = [f for f in files if f.endswith('.md')]
                if md_files:
                    with open(os.path.join(tmp_dir, md_files[0]), 'r') as f:
                        text = f.read()
                else:
                    text = "File processed but no markdown output found."

            return jsonify({"text": text.strip()})

        except Exception as e:
            logger.error(f"OCR Processing Error: {str(e)}")
            return jsonify({"error": f"Processing failed: {str(e)}"}), 500

if __name__ == "__main__":
    # Ensure model is loaded before starting app
    if not MODEL_INSTANCE:
        print("CRITICAL: Could not find Chandra OCR modules.")
    app.run(host="0.0.0.0", port=5000)