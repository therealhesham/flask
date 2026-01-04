import os
import time
import requests

API_URL = "https://www.datalab.to/api/v1/marker"

def convert_document(file_path, output_format="markdown", mode="balanced", api_key=None):
    """
    Convert document using Datalab API
    
    Args:
        file_path: Path to the PDF file
        output_format: Output format (default: "markdown")
        mode: Conversion mode (default: "balanced")
        api_key: API key for Datalab API (optional, defaults to DATALAB_API_KEY env var)
    
    Returns:
        dict: Result containing the converted document
    
    Raises:
        Exception: If conversion fails or times out
    """
    # Use provided API key or fall back to environment variable
    if api_key is None:
        api_key = os.getenv("DATALAB_API_KEY")
    
    if not api_key:
        raise Exception("DATALAB_API_KEY environment variable is not set or api_key parameter not provided")
    
    headers = {"X-API-Key": api_key}

    # Submit request
    with open(file_path, "rb") as f:
        response = requests.post(
            API_URL,
            files={"file": (os.path.basename(file_path), f, "application/pdf")},
            data={
                "output_format": output_format,
                "mode": mode
            },
            headers=headers
        )
    
    # Check for errors in initial response
    if response.status_code != 200:
        raise Exception(f"API request failed with status {response.status_code}: {response.text}")

    data = response.json()
    check_url = data.get("request_check_url")
    
    if not check_url:
        raise Exception(f"No request_check_url in API response: {data}")

    # Poll for completion
    for _ in range(300):
        response = requests.get(check_url, headers=headers)
        result = response.json()

        if result["status"] == "complete":
            return result
        elif result["status"] == "failed":
            raise Exception(f"Conversion failed: {result.get('error')}")

        time.sleep(2)

    raise Exception("Timeout waiting for conversion")

# Usage example
if __name__ == "__main__":
    result = convert_document("document.pdf", mode="balanced")
    print(result["markdown"])

