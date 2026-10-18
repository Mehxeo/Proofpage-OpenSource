"""Bundled browser assets. Only allowlisted file types inside the static folder are served."""
from pathlib import Path

STATIC = Path(__file__).resolve().parent / 'static'
TYPES = {'.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.woff2': 'font/woff2'}


def read_asset(path):
    """Return (bytes, content_type) for a public asset, or None. HTML pages are routed explicitly."""
    parts = [part for part in path.split('/') if part]
    if not parts or any(part.startswith('.') or '\\' in part for part in parts):
        return None
    candidate = STATIC.joinpath(*parts).resolve()
    if STATIC not in candidate.parents or candidate.suffix not in TYPES or not candidate.is_file():
        return None
    return candidate.read_bytes(), TYPES[candidate.suffix]
