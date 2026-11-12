"""Add maintainer-supplied native OAuth metadata before signing a desktop build.

Native clients cannot keep their app metadata confidential. This is not a web
client secret, service-account key, or a user's authorization. Those must never
be included. Input stays outside Git; only the distributable receives metadata.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from proofpage.google_docs import load_client_config


def configure(bundle, client_file):
    bundle = Path(bundle).resolve()
    if bundle.suffix == '.app':
        executables = bundle / 'Contents' / 'MacOS'
        destination = bundle / 'Contents' / 'Resources' / 'proofpage'
    else:
        executables = bundle
        destination = bundle / '_internal' / 'proofpage'
    if not bundle.is_dir() or not any((executables / name).is_file() for name in ('Proofpage-Engine', 'Proofpage-Engine.exe')):
        raise ValueError('Select a built Proofpage desktop directory, not a source checkout.')
    if not destination.is_dir() or not destination.resolve().is_relative_to(bundle):
        raise ValueError('The desktop resource directory is missing or outside the bundle.')
    config = load_client_config(client_file)
    target = destination / 'google-desktop-client.json'
    data = (json.dumps(config, sort_keys=True) + '\n').encode()
    if target.exists():
        if target.read_bytes() == data:
            return
        raise ValueError('The build already contains a different Google client. Use a fresh build.')
    descriptor, temporary = tempfile.mkstemp(prefix='.google-client-', dir=destination)
    try:
        os.chmod(temporary, 0o644)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--client-file', type=Path, required=True)
    arguments = parser.parse_args()
    try:
        configure(arguments.bundle, arguments.client_file)
    except ValueError as exc:
        parser.exit(1, str(exc) + '\n')
    print('Built desktop configured for shared Google Docs sign-in. Sign and verify it before distribution.')
