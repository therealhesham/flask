from flask import Flask, request, jsonify
import os
import tempfile
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# Import datalab_converter
convert_document = None
try:
    from datalab_converter import convert_document
except ImportError:
    # If import fails, try adding current directory to path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    try:
        from datalab_converter import convert_document
    except ImportError as e:
        print(f"⚠ Warning: Could not import datalab_converter: {e}")
        print(f"  Current directory: {current_dir}")
        print(f"  Python path: {sys.path[:3]}...")  # Show first 3 entries
        print(f"  Files in current directory: {os.listdir(current_dir) if os.path.exists(current_dir) else 'N/A'}")
        # Don't raise - let the route handle the error gracefully

# Try different import paths for process_file from chandra
process_file = None
OCR = None
InferenceManager = None

# Diagnostic: Check what's available in chandra package
chandra_module = None
chandra_attrs = []

try:
    import chandra
    chandra_module = chandra
    chandra_attrs = [x for x in dir(chandra) if not x.startswith('_')]
    print(f"✓ chandra module imported successfully from: {chandra.__file__}")
    print(f"Available attributes: {chandra_attrs}")
    
    # Explore the actual directory structure
    chandra_dir = os.path.dirname(chandra.__file__)
    if os.path.exists(chandra_dir):
        print(f"✓ Exploring chandra directory: {chandra_dir}")
        try:
            dir_contents = os.listdir(chandra_dir)
            print(f"✓ Directory contents: {dir_contents}")
        except Exception as e:
            print(f"⚠ Could not list directory contents: {e}")
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

# If process_file not found, try to import OCR class or InferenceManager from various locations
if process_file is None:
    ocr_import_paths = [
        ('chandra', 'OCR'),
        ('chandra_ocr', 'OCR'),
        ('chandra.ocr', 'OCR'),
        ('chandra_ocr.ocr', 'OCR'),
        ('chandra.model', 'InferenceManager'),
        ('chandra_ocr.model', 'InferenceManager'),
        ('chandra.models', 'InferenceManager'),
        ('chandra_ocr.models', 'InferenceManager'),
    ]
    
    for module_path, class_name in ocr_import_paths:
        try:
            module = __import__(module_path, fromlist=[class_name])
            if hasattr(module, class_name):
                if class_name == 'InferenceManager':
                    InferenceManager = getattr(module, class_name)
                    print(f"✓ Found InferenceManager class in {module_path}")
                else:
                    OCR = getattr(module, class_name)
                    print(f"✓ Found OCR class in {module_path}")
                break
        except (ImportError, AttributeError) as e:
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
        if OCR is None and InferenceManager is None:
            try:
                chandra_dir = os.path.dirname(chandra_module.__file__)
                if os.path.exists(chandra_dir):
                    # First, try reading __init__.py to see what it exports
                    init_file = os.path.join(chandra_dir, '__init__.py')
                    if os.path.exists(init_file):
                        try:
                            with open(init_file, 'r', encoding='utf-8') as f:
                                init_content = f.read()
                                print(f"✓ __init__.py content preview: {init_content[:500]}")
                                # Look for import statements
                                if 'OCR' in init_content or 'InferenceManager' in init_content or 'process_file' in init_content:
                                    print(f"✓ Found potential exports in __init__.py")
                        except Exception as e:
                            print(f"⚠ Could not read __init__.py: {e}")
                    
                    # Try both .py files and directories
                    for item in os.listdir(chandra_dir):
                        item_path = os.path.join(chandra_dir, item)
                        if item.endswith('.py') and not item.startswith('__'):
                            module_name = item[:-3]
                            try:
                                submod = __import__(f'{chandra_module.__name__}.{module_name}', 
                                                   fromlist=[module_name])
                                # Check for OCR
                                if hasattr(submod, 'OCR'):
                                    OCR = submod.OCR
                                    print(f"✓ Found OCR class in {chandra_module.__name__}.{module_name}")
                                    break
                                # Check for InferenceManager
                                elif hasattr(submod, 'InferenceManager'):
                                    InferenceManager = submod.InferenceManager
                                    print(f"✓ Found InferenceManager class in {chandra_module.__name__}.{module_name}")
                                    break
                                # Check for process_file
                                elif hasattr(submod, 'process_file'):
                                    process_file = submod.process_file
                                    print(f"✓ Found process_file in {chandra_module.__name__}.{module_name}")
                                    break
                            except Exception as e:
                                print(f"⚠ Could not import {chandra_module.__name__}.{module_name}: {e}")
                        elif os.path.isdir(item_path) and not item.startswith('__'):
                            # Try importing as a package
                            try:
                                submod = __import__(f'{chandra_module.__name__}.{item}', fromlist=[item])
                                if hasattr(submod, 'OCR'):
                                    OCR = submod.OCR
                                    print(f"✓ Found OCR class in {chandra_module.__name__}.{item}")
                                    break
                                elif hasattr(submod, 'InferenceManager'):
                                    InferenceManager = submod.InferenceManager
                                    print(f"✓ Found InferenceManager class in {chandra_module.__name__}.{item}")
                                    break
                                elif hasattr(submod, 'process_file'):
                                    process_file = submod.process_file
                                    print(f"✓ Found process_file in {chandra_module.__name__}.{item}")
                                    break
                            except Exception as e:
                                pass
            except Exception as e:
                print(f"⚠ Error exploring submodules: {e}")

# Check if we have at least one working method
if process_file is None and OCR is None and InferenceManager is None:
    print("⚠ WARNING: Could not find process_file, OCR class, or InferenceManager.")
    print("⚠ Please ensure chandra-ocr is properly installed.")
    if chandra_module:
        print(f"⚠ Available attributes in {chandra_module.__name__}: {chandra_attrs}")
        chandra_dir = os.path.dirname(chandra_module.__file__)
        if os.path.exists(chandra_dir):
            try:
                print(f"⚠ Directory contents: {os.listdir(chandra_dir)}")
            except:
                pass
        print("⚠ Try checking the chandra-ocr documentation for the correct import path.")
        print("⚠ Try: pip install --upgrade git+https://github.com/datalab-to/chandra.git")

app = Flask(__name__)

# Configure Flask timeout settings
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

@app.route("/", methods=["GET"])
def hello():
    return jsonify({"message": "hello world", "status": "ok"})

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "ocr-api"}), 200

@app.route("/timeout-info", methods=["GET"])
def timeout_info():
    """Get timeout configuration information"""
    timeout_info = {
        "overall_timeout_seconds": 1800,
        "overall_timeout_minutes": 30,
        "gunicorn_timeout_seconds": 2400,
        "gunicorn_timeout_minutes": 40,
        "curl_timeout_seconds": 2400,
        "curl_timeout_minutes": 40,
        "note": "If you're using sslip.io or another reverse proxy, they may have their own timeout limits that override these settings.",
        "recommendations": [
            "If timeout persists, try accessing directly: http://YOUR_SERVER_IP:5000/ocr",
            "sslip.io may have a 60-120 second timeout limit",
            "Use a smaller or simpler image",
            "Check server logs for actual processing time"
        ]
    }
    return jsonify(timeout_info), 200

@app.route("/test-connection", methods=["GET"])
def test_connection():
    """Test endpoint to verify connection works without timeout"""
    import time
    return jsonify({
        "status": "ok",
        "message": "Connection test successful",
        "timestamp": time.time(),
        "server_time": time.strftime('%Y-%m-%d %H:%M:%S')
    }), 200

@app.route("/vllm-status", methods=["GET"])
def vllm_status():
    """Check vLLM service status and configuration"""
    import time
    status_info = {
        "timestamp": time.time(),
        "server_time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "vllm_configured": False,
        "vllm_environment": {},
        "note": "This endpoint shows vLLM configuration. Actual connection testing requires an OCR request."
    }
    
    # Check for vLLM environment variables
    vllm_vars = {
        "VLLM_HOST": os.environ.get("VLLM_HOST"),
        "VLLM_PORT": os.environ.get("VLLM_PORT"),
        "VLLM_BASE_URL": os.environ.get("VLLM_BASE_URL"),
        "VLLM_API_BASE": os.environ.get("VLLM_API_BASE"),
        "OPENAI_API_BASE": os.environ.get("OPENAI_API_BASE"),
    }
    
    status_info["vllm_environment"] = {k: v for k, v in vllm_vars.items() if v}
    status_info["vllm_configured"] = len(status_info["vllm_environment"]) > 0
    
    if not status_info["vllm_configured"]:
        status_info["message"] = "No vLLM environment variables found. vLLM may be using default settings or configured within chandra package."
        status_info["recommendation"] = "If experiencing connection errors, check chandra documentation for vLLM configuration."
    else:
        status_info["message"] = "vLLM environment variables detected."
        status_info["recommendation"] = "If experiencing connection errors, verify vLLM service is running and accessible."
    
    return jsonify(status_info), 200

@app.route("/diagnostics", methods=["GET"])
def diagnostics():
    """Diagnostic endpoint to check chandra package availability"""
    diagnostics_info = {
        "process_file_available": process_file is not None,
        "OCR_available": OCR is not None,
        "InferenceManager_available": InferenceManager is not None,
        "chandra_module": None,
        "chandra_ocr_module": None,
        "cli_available": False,
        "vllm_info": {},
    }
    
    # Check vLLM related environment variables
    vllm_env_vars = [
        "VLLM_HOST", "VLLM_PORT", "VLLM_BASE_URL", 
        "VLLM_API_BASE", "OPENAI_API_BASE", "OPENAI_API_KEY"
    ]
    diagnostics_info["vllm_info"]["environment_variables"] = {}
    for var in vllm_env_vars:
        value = os.environ.get(var)
        if value:
            # Mask sensitive values
            if "KEY" in var or "SECRET" in var:
                diagnostics_info["vllm_info"]["environment_variables"][var] = "***" if value else None
            else:
                diagnostics_info["vllm_info"]["environment_variables"][var] = value
        else:
            diagnostics_info["vllm_info"]["environment_variables"][var] = None
    
    # Add note about vLLM connection errors
    diagnostics_info["vllm_info"]["note"] = "If you see 'Connection error' messages, vLLM service may be unavailable or unreachable. Check vLLM service status and network connectivity."
    diagnostics_info["vllm_info"]["common_issues"] = [
        "vLLM service not running",
        "Network connectivity issues",
        "Incorrect vLLM URL/port configuration",
        "vLLM service overloaded or slow to respond"
    ]
    
    # Add directory structure info if chandra module exists
    try:
        import chandra
        chandra_dir = os.path.dirname(chandra.__file__)
        if os.path.exists(chandra_dir):
            diagnostics_info["chandra_directory_contents"] = os.listdir(chandra_dir)
    except:
        pass
    
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
    import time
    start_time = time.time()
    
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400

    file = request.files["image"]
    image_path = os.path.join("/tmp", file.filename)
    file.save(image_path)
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting OCR for: {file.filename}")

    # Overall timeout for the entire OCR operation (30 minutes)
    overall_timeout = 1800
    try:
        # Send initial response headers to keep connection alive
        # This helps with reverse proxies that timeout on idle connections
        
        # Wrap the entire OCR processing in a timeout
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(process_ocr_image, image_path, file)
            try:
                # Get result with timeout - this will wait up to overall_timeout seconds
                # Log progress periodically to keep connection alive
                import threading
                log_interval = 60  # Log every minute
                last_log_time = start_time
                
                def log_progress():
                    nonlocal last_log_time
                    while not future.done():
                        current_time = time.time()
                        if current_time - last_log_time >= log_interval:
                            elapsed = current_time - start_time
                            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] OCR still processing... ({elapsed:.0f}s elapsed)")
                            last_log_time = current_time
                        time.sleep(10)  # Check every 10 seconds
                
                # Start logging thread
                log_thread = threading.Thread(target=log_progress, daemon=True)
                log_thread.start()
                
                # Wait for result with timeout
                output = future.result(timeout=overall_timeout)
                elapsed_time = time.time() - start_time
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] OCR completed in {elapsed_time:.2f} seconds")
                return jsonify(output)
            except FutureTimeoutError:
                elapsed_time = time.time() - start_time
                error_msg = f"OCR operation timed out after {elapsed_time:.0f} seconds. "
                error_msg += "Possible causes: 1) Image is too complex, 2) Service is overloaded, "
                error_msg += "3) sslip.io or reverse proxy has a timeout limit (check /timeout-info endpoint). "
                error_msg += "Try: smaller image, or access the service directly without sslip.io."
                print(f"ERROR: {error_msg}")
                return jsonify({
                    "error": error_msg, 
                    "timeout_seconds": elapsed_time,
                    "suggestion": "If using sslip.io, it may have a timeout limit. Try accessing the service directly or use a different reverse proxy."
                }), 504  # 504 Gateway Timeout
    except Exception as e:
        error_msg = str(e)
        print(f"ERROR processing image: {error_msg}")
        status_code = 500 if "No OCR method available" in error_msg or "Failed to process" in error_msg else 400
        return jsonify({"error": error_msg}), status_code
    finally:
        if os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                print(f"Warning: Could not remove temp file {image_path}: {e}")

def execute_with_pattern_timeout(pattern_func, pattern_name, timeout_seconds=600):
    """
    Execute a pattern function with its own timeout.
    This prevents one hanging pattern from blocking all other attempts.
    timeout_seconds: Default 10 minutes per pattern attempt (allows time for vLLM retries)
    """
    import time
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(pattern_func)
        
        # Log progress every 60 seconds for long-running operations
        def log_progress():
            while not future.done():
                elapsed = time.time() - start_time
                if elapsed > 60 and elapsed % 60 < 2:  # Log roughly every minute
                    print(f"  ⏳ Pattern '{pattern_name}' still running... ({elapsed:.0f}s elapsed)")
                time.sleep(5)
        
        import threading
        log_thread = threading.Thread(target=log_progress, daemon=True)
        log_thread.start()
        
        try:
            result = future.result(timeout=timeout_seconds)
            elapsed = time.time() - start_time
            if elapsed > 30:  # Only log if it took significant time
                print(f"  ✓ Pattern '{pattern_name}' completed in {elapsed:.1f}s")
            return result, None
        except FutureTimeoutError:
            elapsed = time.time() - start_time
            error_msg = f"Pattern '{pattern_name}' timed out after {elapsed:.0f} seconds"
            print(f"⚠ {error_msg}")
            return None, error_msg
        except Exception as e:
            elapsed = time.time() - start_time
            error_str = str(e).lower()
            # Check if it's a vLLM connection error - these are expected and will retry
            if "vllm" in error_str or "connection error" in error_str:
                print(f"  ⚠ Pattern '{pattern_name}' encountered vLLM connection error (chandra will retry automatically)")
            return None, str(e)

def process_ocr_image(image_path, file):
    """Process OCR on the image - called within timeout wrapper"""
    try:
        if OCR is not None:
            # Use OCR class if available (direct method, no output directory needed)
            print(f"Using OCR class for image: {image_path}")
            # Direct call - timeout is handled by outer wrapper
            ocr_instance = OCR(device="cpu")
            result_text = ocr_instance.read_image(image_path)
            output = {"text": result_text}
        elif InferenceManager is not None:
            # Use InferenceManager if available
            print(f"Using InferenceManager for image: {image_path}")
            try:
                # Check if InferenceManager is a class or an instance
                import inspect
                is_class = inspect.isclass(InferenceManager)
                
                if is_class:
                    # It's a class, so we need to instantiate it
                    try:
                        # Try instantiating with device parameter
                        manager = InferenceManager(device="cpu")
                    except TypeError:
                        # If that fails, try without parameters
                        try:
                            manager = InferenceManager()
                        except Exception as e:
                            raise Exception(f"Failed to instantiate InferenceManager class: {str(e)}")
                else:
                    # It's already an instance, use it directly
                    manager = InferenceManager
                
                # Get all available methods/attributes for diagnostics
                available_methods = [attr for attr in dir(manager) if not attr.startswith('_') and callable(getattr(manager, attr, None))]
                print(f"InferenceManager available methods: {available_methods}")
                
                # Now use the manager instance to process the image
                # Try various method names that might be used
                result_text = None
                method_tried = None
                last_error = None
                
                # List of possible method names to try
                possible_methods = [
                    'generate', 'process', 'read_image', 'infer', 'predict', 'ocr', 
                    'extract_text', 'run', 'execute', 'forward', '__call__'
                ]
                
                # Try to load image as PIL Image for methods that might need it
                pil_image = None
                try:
                    from PIL import Image
                    pil_image = Image.open(image_path)
                    print(f"Loaded image as PIL Image: {pil_image.size}")
                except Exception as e:
                    print(f"Could not load image as PIL Image: {e}")
                
                for method_name in possible_methods:
                    if hasattr(manager, method_name):
                        method = getattr(manager, method_name)
                        if callable(method):
                            # Special handling for 'generate' method which requires 'batch' parameter
                            if method_name == 'generate':
                                # Inspect method signature to understand expected parameters
                                try:
                                    import inspect
                                    sig = inspect.signature(method)
                                    print(f"generate method signature: {sig}")
                                    params = list(sig.parameters.keys())
                                    print(f"generate method parameters: {params}")
                                except Exception as e:
                                    print(f"Could not inspect generate method signature: {e}")
                                
                                # Try different batch formats
                                # Reordered: Most successful patterns first (ImagePrompt PIL works!)
                                batch_patterns = []
                                
                                # Define ImagePrompt class first (used by successful patterns)
                                class ImagePrompt:
                                    def __init__(self, image, prompt):
                                        self.image = image
                                        self.prompt = prompt
                                
                                # Pattern 1: ImagePrompt with PIL Image (KNOWN TO WORK - try first!)
                                if pil_image is not None:
                                    batch_patterns.append(('batch=[ImagePrompt] PIL', 
                                        lambda: method(batch=[ImagePrompt(pil_image, 'Extract text from this image')])))
                                
                                # Pattern 2: ImagePrompt with path (also works, but PIL is better)
                                batch_patterns.append(('batch=[ImagePrompt] path', 
                                    lambda: method(batch=[ImagePrompt(image_path, 'Extract text from this image')])))
                                
                                # Pattern 3: List of PIL Images (simple fallback)
                                if pil_image is not None:
                                    batch_patterns.append(('batch=[PIL]', lambda: method(batch=[pil_image])))
                                
                                # Pattern 4: List of image paths (simple fallback)
                                batch_patterns.append(('batch=[path]', lambda: method(batch=[image_path])))
                                
                                # Pattern 5: List of dicts with 'image' and 'prompt' keys (PIL Image)
                                if pil_image is not None:
                                    batch_patterns.append(('batch=[{image, prompt}] PIL', 
                                        lambda: method(batch=[{'image': pil_image, 'prompt': 'Extract text from this image'}])))
                                
                                # Pattern 6: List of dicts with 'img' key and PIL Image
                                if pil_image is not None:
                                    batch_patterns.append(('batch=[{img, prompt}] PIL', 
                                        lambda: method(batch=[{'img': pil_image, 'prompt': 'Extract text from this image'}])))
                                
                                # Pattern 7: List of dicts with 'image' and 'prompt' keys (image path)
                                batch_patterns.append(('batch=[{image, prompt}] path', 
                                    lambda: method(batch=[{'image': image_path, 'prompt': 'Extract text from this image'}])))
                                
                                # Pattern 8: List of dicts with 'img' key
                                batch_patterns.append(('batch=[{img, prompt}]', 
                                    lambda: method(batch=[{'img': image_path, 'prompt': 'Extract text from this image'}])))
                                
                                # Pattern 9: List of dicts with different key names
                                batch_patterns.append(('batch=[{image_path, prompt}]', 
                                    lambda: method(batch=[{'image_path': image_path, 'prompt': 'Extract text from this image'}])))
                                
                                # Pattern 10: Simple object-like dict with prompt
                                batch_patterns.append(('batch=[{image, prompt}] OCR', 
                                    lambda: method(batch=[{'image': image_path, 'prompt': 'What text is in this image?'}])))
                                
                                # Pattern 11: Positional batch with dict
                                batch_patterns.append(('batch=[{image, prompt}] positional', 
                                    lambda: method([{'image': image_path, 'prompt': 'Extract text from this image'}])))
                                
                                # Pattern 12: Empty prompt or no prompt (least likely to work)
                                batch_patterns.append(('batch=[{image}] no prompt', 
                                    lambda: method(batch=[{'image': image_path}])))
                                
                                # Try each batch pattern with individual timeouts
                                # Each pattern gets 10 minutes - allows time for vLLM retries and prevents one hanging pattern from blocking others
                                pattern_timeout = 600  # 10 minutes per pattern (default, allows for vLLM retries)
                                for pattern_name, pattern_func in batch_patterns:
                                    method_tried = f"{method_name}({pattern_name})"
                                    print(f"Trying pattern: {method_tried} (timeout: {pattern_timeout}s)")
                                    
                                    result, error = execute_with_pattern_timeout(pattern_func, pattern_name, pattern_timeout)
                                    
                                    if result is not None:
                                        # Handle result - might be a list or single value
                                        if isinstance(result, list):
                                            result_text = result[0] if len(result) > 0 else str(result)
                                        else:
                                            result_text = result
                                        print(f"✓ Successfully used method: {method_tried}")
                                        break
                                    else:
                                        # Pattern failed or timed out
                                        last_error = error or "Unknown error"
                                        error_str = last_error.lower()
                                        print(f"✗ Method {method_name} with {pattern_name} failed: {last_error}")
                                        
                                        # Check if it's a vLLM connection error
                                        if "vllm" in error_str or "connection error" in error_str:
                                            print(f"⚠ vLLM connection error detected. This may indicate:")
                                            print(f"  - vLLM service is not running or unreachable")
                                            print(f"  - Network connectivity issues")
                                            print(f"  - vLLM service is overloaded")
                                            print(f"  - Check /vllm-status endpoint for configuration info")
                                        
                                        # Continue to next pattern
                                        continue
                                
                                if result_text is not None:
                                    break
                            else:
                                # Try various calling patterns for other methods
                                patterns_to_try = []
                                
                                # Pattern 1: Direct file path (positional)
                                patterns_to_try.append(('positional path', lambda: method(image_path)))
                                
                                # Pattern 2: File path as keyword 'image'
                                patterns_to_try.append(('keyword image', lambda: method(image=image_path)))
                                
                                # Pattern 3: File path as keyword 'image_path'
                                patterns_to_try.append(('keyword image_path', lambda: method(image_path=image_path)))
                                
                                # Pattern 4: File path as keyword 'path'
                                patterns_to_try.append(('keyword path', lambda: method(path=image_path)))
                                
                                # Pattern 5: PIL Image (positional)
                                if pil_image is not None:
                                    patterns_to_try.append(('PIL Image positional', lambda: method(pil_image)))
                                
                                # Pattern 6: PIL Image as keyword 'image'
                                if pil_image is not None:
                                    patterns_to_try.append(('PIL Image keyword', lambda: method(image=pil_image)))
                                
                                # Pattern 7: Direct call on manager (for __call__)
                                if method_name == '__call__':
                                    patterns_to_try.insert(0, ('direct call', lambda: manager(image_path)))
                                
                                # Try each pattern with individual timeouts
                                # Each pattern gets 10 minutes - allows time for vLLM retries and prevents one hanging pattern from blocking others
                                pattern_timeout = 600  # 10 minutes per pattern (default, allows for vLLM retries)
                                for pattern_name, pattern_func in patterns_to_try:
                                    method_tried = f"{method_name}({pattern_name})"
                                    print(f"Trying pattern: {method_tried} (timeout: {pattern_timeout}s)")
                                    
                                    result, error = execute_with_pattern_timeout(pattern_func, pattern_name, pattern_timeout)
                                    
                                    if result is not None:
                                        result_text = result
                                        print(f"✓ Successfully used method: {method_tried}")
                                        break
                                    else:
                                        # Pattern failed or timed out
                                        last_error = error or "Unknown error"
                                        error_str = last_error.lower()
                                        print(f"✗ Method {method_name} with {pattern_name} failed: {last_error}")
                                        
                                        # Check if it's a vLLM connection error
                                        if "vllm" in error_str or "connection error" in error_str:
                                            print(f"⚠ vLLM connection error detected. This may indicate:")
                                            print(f"  - vLLM service is not running or unreachable")
                                            print(f"  - Network connectivity issues")
                                            print(f"  - vLLM service is overloaded")
                                            print(f"  - Check /vllm-status endpoint for configuration info")
                                        
                                        # Continue to next pattern
                                        continue
                                
                                if result_text is not None:
                                    break
                
                if result_text is None:
                    # Provide detailed error with available methods and last error
                    error_msg = f"InferenceManager found but no known method to process image. "
                    error_msg += f"Available methods: {available_methods}. "
                    error_msg += f"Tried methods: {possible_methods}. "
                    if last_error:
                        if "timed out" in last_error.lower():
                            error_msg += f"Last error: {last_error}. "
                            error_msg += "All patterns timed out - the method may be hanging or taking too long. "
                            error_msg += "Consider checking the InferenceManager documentation for the correct usage."
                        elif "vllm" in last_error.lower() or "connection error" in last_error.lower() or "Connection error" in last_error:
                            error_msg += f"Last error: {last_error}. "
                            error_msg += "vLLM connection errors detected. This usually means: "
                            error_msg += "1) vLLM service is not running or unreachable, "
                            error_msg += "2) Network connectivity issues, or "
                            error_msg += "3) vLLM service is overloaded. "
                            error_msg += "Check /vllm-status endpoint for configuration info. "
                            error_msg += "Note: chandra automatically retries vLLM connections, so the request may still succeed after retries."
                        else:
                            error_msg += f"Last error: {last_error}"
                    raise Exception(error_msg)
                
                output = {"text": result_text}
            except Exception as e:
                raise Exception(f"Failed to use InferenceManager: {str(e)}")
        elif process_file is not None:
            # Use process_file function (requires output directory)
            print(f"Using process_file for image: {image_path}")
            with tempfile.TemporaryDirectory() as output_dir:
                try:
                    # Try different method parameters - timeout handled by outer wrapper
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
            error_details = ["No OCR method available. Please ensure chandra-ocr is properly installed with either OCR class, InferenceManager, or process_file function."]
            
            # Add diagnostic information
            if chandra_module:
                error_details.append(f"Found chandra module at: {chandra_module.__file__}")
                error_details.append(f"Available attributes: {chandra_attrs}")
                chandra_dir = os.path.dirname(chandra_module.__file__)
                if os.path.exists(chandra_dir):
                    try:
                        dir_contents = os.listdir(chandra_dir)
                        error_details.append(f"Directory contents: {dir_contents}")
                    except:
                        pass
            else:
                error_details.append("Could not import chandra module. Try: pip install --upgrade git+https://github.com/datalab-to/chandra.git")
            
            error_details.append("Check /diagnostics endpoint for more information.")
            raise Exception(" ".join(error_details))
    except Exception as e:
        error_msg = str(e)
        print(f"ERROR processing image: {error_msg}")
        raise Exception(error_msg)
    
    return output

@app.route("/convert-document", methods=["POST"])
def convert_document_route():
    """
    Convert document using Datalab API
    Accepts PDF files and converts them to markdown or other formats
    """
    # Check if convert_document function is available
    if convert_document is None:
        return jsonify({
            "error": "datalab_converter module not found. Please ensure datalab_converter.py is in the same directory as ocr_api.py"
        }), 500
    
    # Check if API key is configured
    api_key = "VeQhnKsKghLRJJCzWLmwFPSxFUwwI5zC4sNIHPnEK9Q"
    if not api_key:
        return jsonify({
            "error": "DATALAB_API_KEY environment variable is not set"
        }), 500
    
    # Check if file is provided
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    # Get parameters from request
    output_format = request.form.get("output_format", "markdown")
    mode = request.form.get("mode", "balanced")
    
    # Save uploaded file temporarily
    temp_file_path = None
    start_time = time.time()
    try:
        # Create temp file
        temp_fd, temp_file_path = tempfile.mkstemp(suffix=os.path.splitext(file.filename)[1])
        os.close(temp_fd)  # Close the file descriptor
        file.save(temp_file_path)
        
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting document conversion for: {file.filename}")
        print(f"  Output format: {output_format}, Mode: {mode}")
        
        # Use the convert_document function from datalab_converter
        result = convert_document(temp_file_path, output_format=output_format, mode=mode)
        
        elapsed_time = time.time() - start_time
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Document conversion completed in {elapsed_time:.2f} seconds")
        
        return jsonify({
            "status": "success",
            "result": result
        }), 200
        
    except Exception as e:
        error_msg = str(e)
        print(f"ERROR processing document: {error_msg}")
        return jsonify({"error": error_msg}), 500
    finally:
        # Clean up temp file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                print(f"Warning: Could not remove temp file {temp_file_path}: {e}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)