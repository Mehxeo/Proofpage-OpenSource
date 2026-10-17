"""Use verified TLS, including Python.org macOS installs without a bundled CA file."""
import ssl
import sys
from pathlib import Path


def context():
    if getattr(sys, 'frozen', False):
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    result = ssl.create_default_context()
    if not ssl.get_default_verify_paths().cafile and Path('/etc/ssl/cert.pem').is_file():
        result.load_verify_locations('/etc/ssl/cert.pem')
    return result
