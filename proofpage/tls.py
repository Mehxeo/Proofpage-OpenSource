"""Use verified TLS, including Python.org macOS installs without a bundled CA file."""
import ssl
from pathlib import Path


def context():
    result = ssl.create_default_context()
    if not ssl.get_default_verify_paths().cafile and Path('/etc/ssl/cert.pem').is_file():
        result.load_verify_locations('/etc/ssl/cert.pem')
    return result
