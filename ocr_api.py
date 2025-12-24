from flask import Flask, request, jsonify
import os

# Try different import paths for chandra-ocr
try:
    from chandra_ocr import OCR
except ImportError:
    try:
        from chandra import OCR
    except ImportError:
        try:
            from chandra.ocr import OCR
        except ImportError:
            raise ImportError("Could not import OCR from chandra_ocr, chandra, or chandra.ocr. Please check chandra-ocr installation.")

app = Flask(__name__)
ocr = OCR(device="cpu")

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
        result_text = ocr.read_image(image_path)
        output = {"text": result_text}
    except Exception as e:
        output = {"error": str(e)}
    finally:
        os.remove(image_path)

    return jsonify(output)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
