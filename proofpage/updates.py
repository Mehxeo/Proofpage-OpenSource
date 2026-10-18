"""Explicit release checks. Never installs code or changes workspace data."""
import json
import platform
import re
import ssl
import urllib.request

CURRENT = '0.4.0'
RELEASES = 'https://github.com/Mehxeo/Proofpage-OpenSource/releases'
API = 'https://api.github.com/repos/Mehxeo/Proofpage-OpenSource/releases/latest'


def release_info(data):
    tag = data.get('tag_name', '')
    if data.get('draft') or data.get('prerelease') or not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise ValueError('No stable release is available. Try again later.')
    version = tag[1:]
    newer = tuple(map(int, version.split('.'))) > tuple(map(int, CURRENT.split('.')))
    system = platform.system().lower()
    arch = platform.machine().lower().replace('amd64', 'x86_64').replace('aarch64', 'arm64')
    suffix = 'tar.gz' if system == 'linux' else 'zip'
    name = f'Proofpage-{version}-{system}-{arch}.{suffix}'
    expected = f'{RELEASES}/download/{tag}/{name}'
    asset = next((a for a in data.get('assets', []) if a.get('name') == name and
                  a.get('state') == 'uploaded' and a.get('browser_download_url') == expected), None)
    return {'current': CURRENT, 'latest': version, 'available': newer,
            'download': expected if asset and newer else None,
            'release_url': f'{RELEASES}/tag/{tag}'}


def check():
    context = ssl.create_default_context()
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    request = urllib.request.Request(API, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'Proofpage-update-check'})
    try:
        with urllib.request.urlopen(request, timeout=15, context=context) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError('Release response is too large.')
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError('Invalid release response.')
        return release_info(data)
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Could not check for updates. Check your connection and try again, or open the releases page.') from exc
