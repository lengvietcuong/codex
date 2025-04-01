import chardet

def detect_encoding(content_bytes):
    """
    Detect the encoding of binary content
    Returns a tuple of (encoding, confidence)
    """
    result = chardet.detect(content_bytes)
    return result['encoding'], result['confidence']

def safe_decode(content_bytes):
    """
    Try to decode binary content with the most likely encoding
    Falls back to simpler encodings if detection fails
    Returns a tuple of (decoded_text, encoding_used)
    """
    # List of encodings to try in order of preference
    preferred_encodings = ['utf-8', 'latin-1', 'ascii', 'windows-1252']
    
    # First try to detect encoding
    detected, confidence = detect_encoding(content_bytes)
    
    # If we detected with high confidence, try that first
    if detected and confidence > 0.7:
        try:
            return content_bytes.decode(detected), detected
        except UnicodeDecodeError:
            pass
    
    # Otherwise, try our preferred encodings in order
    for encoding in preferred_encodings:
        try:
            return content_bytes.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    
    # If all fails, use latin-1 which can decode any byte stream
    # even if the result might not be perfect
    return content_bytes.decode('latin-1'), 'latin-1'
