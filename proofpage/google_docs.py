"""Optional Google Docs connector: explicit document selection, OS credential vault."""
import hashlib
import importlib.util
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

from .core import now

SCOPE = 'https://www.googleapis.com/auth/documents.readonly'
SERVICE = 'Proofpage Google Docs'
BUNDLED_CLIENT_FILE = Path(__file__).with_name('google-desktop-client.json')
_LOCK = threading.Lock()


class GoogleDocsError(ValueError):
    """A connector-owned, credential-free message safe to show in the UI."""


def account(store):
    return hashlib.sha256(str(store.directory.resolve()).encode()).hexdigest()


def vault():
    # Discovery scans third-party plugins and can stall in a frozen HTTP worker.
    # Select only the native vault we support; never fall back to another backend.
    native = {'darwin': ('keyring.backends.macOS', 'Keyring'),
              'win32': ('keyring.backends.Windows', 'WinVaultKeyring'),
              'linux': ('keyring.backends.SecretService', 'Keyring')}.get(sys.platform)
    if native is None:
        raise ValueError('Configure a supported OS credential vault (Keychain, Windows Credential Locker, or Secret Service). Plaintext token storage is not supported.')
    try:
        backend = getattr(importlib.import_module(native[0]), native[1])()
        if backend.priority <= 0:
            raise ValueError('OS credential vault is unavailable.')
        return backend
    except Exception:
        raise ValueError('OS credential vault is unavailable. Unlock or configure your system vault; plaintext token storage is not supported.') from None


def client_file():
    configured = os.environ.get('PROOFPAGE_GOOGLE_CLIENT_FILE')
    if configured:
        return Path(configured).expanduser()
    config_directory = os.environ.get('PROOFPAGE_CONFIG_DIRECTORY')
    custom = (Path(config_directory).expanduser() if config_directory else Path.home() / '.config' / 'proofpage') / 'google-oauth.json'
    if custom.is_file() or not BUNDLED_CLIENT_FILE.is_file():
        return custom
    return BUNDLED_CLIENT_FILE


def load_client_config(path):
    """Validate native app metadata. Never accept web clients or user tokens."""
    try:
        with Path(path).open('rb') as handle:
            raw = handle.read(16 * 1024 + 1)
        if len(raw) > 16 * 1024:
            raise ValueError()
        config = json.loads(raw)
        if not isinstance(config, dict) or 'web' in config or not isinstance(config.get('installed'), dict):
            raise ValueError()
        def contains_tokens(value):
            if isinstance(value, dict):
                return bool(set(value) & {'access_token', 'refresh_token', 'id_token', 'token', 'private_key', 'private_key_id'}) or any(contains_tokens(v) for v in value.values())
            return isinstance(value, list) and any(contains_tokens(v) for v in value)
        if contains_tokens(config):
            raise ValueError()
        client = config['installed']
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.apps\.googleusercontent\.com', client.get('client_id', '')):
            raise ValueError()
        if not isinstance(client.get('client_secret'), str) or not 1 <= len(client['client_secret']) <= 1024:
            raise ValueError()
        if client.get('auth_uri') not in ('https://accounts.google.com/o/oauth2/auth', 'https://accounts.google.com/o/oauth2/v2/auth'):
            raise ValueError()
        if client.get('token_uri') != 'https://oauth2.googleapis.com/token':
            raise ValueError()
        redirects = client.get('redirect_uris', ['http://localhost'])
        if not isinstance(redirects, list) or not redirects or any(v not in ('http://localhost', 'http://127.0.0.1', 'http://[::1]') for v in redirects):
            raise ValueError()
        return {'installed': {key: client[key] for key in ('client_id', 'client_secret', 'auth_uri', 'token_uri')} | {'redirect_uris': redirects}}
    except (OSError, ValueError, TypeError, RecursionError):
        raise ValueError('Use a valid Google Desktop OAuth client configuration without user tokens or private keys.') from None


def status(store):
    installed = all(importlib.util.find_spec(name) is not None for name in ('google_auth_oauthlib', 'keyring'))
    path = client_file()
    configured = path.is_file()
    connected = False
    detail = ''
    if configured:
        try:
            load_client_config(path)
        except ValueError:
            configured = False
            detail = 'The Google client file is invalid. Choose a valid Desktop OAuth client in the setup guide.'
    if installed and configured:
        try:
            connected = bool(vault().get_password(SERVICE, account(store)))
        except Exception:
            detail = 'OS credential vault is unavailable.'
    return {'installed': installed, 'configured': configured, 'connected': connected, 'detail': detail,
            'configuration_source': 'bundled' if configured and path == BUNDLED_CLIENT_FILE else 'custom' if configured else 'missing',
            'scope': SCOPE, 'documents': store.rows('SELECT * FROM google_documents ORDER BY title,document_id')}


def connect(store):
    from google_auth_oauthlib.flow import InstalledAppFlow
    backend = vault()  # Fail before authorization if credentials cannot be stored securely.
    config_path = client_file()
    if not config_path.is_file():
        raise ValueError('Install a Google Desktop OAuth client JSON at ~/.config/proofpage/google-oauth.json or set PROOFPAGE_GOOGLE_CLIENT_FILE.')
    config = load_client_config(config_path)
    if not _LOCK.acquire(blocking=False):
        raise ValueError('A Google connection or sync is already running.')
    try:
        flow = InstalledAppFlow.from_client_config(config, [SCOPE], autogenerate_code_verifier=True)
        credentials = flow.run_local_server(host='127.0.0.1', port=0, open_browser=True,
                                            timeout_seconds=600, authorization_prompt_message='',
                                            success_message='Proofpage is connected. You can close this tab.', prompt='consent')
        backend.set_password(SERVICE, account(store), credentials.to_json())
        return {'connected': True}
    except Exception as exc:
        raise GoogleDocsError('Google sign-in did not finish. Retry sign-in in your system browser; no document was imported.') from None
    finally:
        _LOCK.release()


def disconnect(store):
    # Local disconnection; Google account grant can be revoked separately by the user.
    with _LOCK:
        backend = vault()
        if backend.get_password(SERVICE, account(store)):
            backend.delete_password(SERVICE, account(store))
        with store.db() as db:
            db.execute('UPDATE google_documents SET interval_seconds=0')
    return {'connected': False, 'detail': 'Local credentials removed and schedules paused. Existing evidence remains. Revoke the account grant in Google account permissions if desired.'}


def document_id(value):
    if not isinstance(value, str):
        raise GoogleDocsError('Provide a Google Docs document ID or URL.')
    match = re.fullmatch(r'https://docs\.google\.com/document/d/([A-Za-z0-9_-]+)(?:/[^\s]*)?', value.strip())
    identifier = match[1] if match else value.strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,200}', identifier):
        raise GoogleDocsError('Provide a valid Google Docs document ID or docs.google.com/document/d/ URL.')
    return identifier


def select(store, value, interval_seconds=0, owner_permission=False):
    identifier = document_id(value)
    if owner_permission is not True:
        raise GoogleDocsError('Confirm that you own this document or its owner permits keeping local snapshots for your personal context.')
    if type(interval_seconds) is not int or interval_seconds not in (0, 3600, 21600, 86400):
        raise GoogleDocsError('Choose manual, hourly, six-hourly, or daily refresh.')
    with store.db() as db:
        db.execute("INSERT INTO google_documents(document_id,title,interval_seconds,next_run,state,owner_permission,permission_at) VALUES(?,?,?,?,'selected',1,?) ON CONFLICT(document_id) DO UPDATE SET interval_seconds=excluded.interval_seconds,next_run=excluded.next_run,owner_permission=1,permission_at=excluded.permission_at", (identifier, identifier, interval_seconds, time.time() + interval_seconds if interval_seconds else 0, now()))
    return {'document_id': identifier, 'interval_seconds': interval_seconds, 'fetched': False}


def extract(document):
    """Extract body/table text from all tabs. Images and comments are not inferred."""
    sections = []
    def content(elements):
        for element in elements:
            paragraph = element.get('paragraph', {})
            for item in paragraph.get('elements', []):
                if 'textRun' in item:
                    sections.append(item['textRun'].get('content', ''))
            for row in element.get('table', {}).get('tableRows', []):
                for cell in row.get('tableCells', []):
                    content(cell.get('content', []))
            content(element.get('tableOfContents', {}).get('content', []))
    def tabs(items):
        for tab in items:
            title = tab.get('tabProperties', {}).get('title')
            if title: sections.append('\n' + title + '\n')
            content(tab.get('documentTab', {}).get('body', {}).get('content', []))
            tabs(tab.get('childTabs', []))
    if document.get('tabs'):
        tabs(document['tabs'])
    else:
        content(document.get('body', {}).get('content', []))
    return ''.join(sections)


def fetch_document(store, identifier):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import AuthorizedSession
    backend = vault()
    saved = backend.get_password(SERVICE, account(store))
    if not saved:
        raise GoogleDocsError('Sign in with Google, then retry importing your selected document.')
    credentials = Credentials.from_authorized_user_info(json.loads(saved), scopes=[SCOPE])
    with AuthorizedSession(credentials) as session:
        with session.get('https://docs.googleapis.com/v1/documents/' + identifier,
                         params={'includeTabsContent': 'true', 'suggestionsViewMode': 'PREVIEW_WITHOUT_SUGGESTIONS'},
                         timeout=30, allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                if response.status_code == 401:
                    raise GoogleDocsError('Google authorization expired. Reconnect Google, then retry this document.')
                if response.status_code in (403, 404):
                    raise GoogleDocsError('Google could not open this document. Check the link and whether the connected Google account can read it.')
                if response.status_code == 429:
                    raise GoogleDocsError('Google is limiting requests. Wait a few minutes, then retry this document.')
                raise GoogleDocsError('Google could not read this document. Retry later; no new evidence was saved.')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 8 * 1024 * 1024:
                    raise GoogleDocsError('Google document exceeds the 8 MiB import limit. Import a smaller document or an exported file.')
                chunks.append(chunk)
            result = json.loads(b''.join(chunks))
    backend.set_password(SERVICE, account(store), credentials.to_json())
    return result


def sync(store, value):
    identifier = document_id(value)
    if not store.rows('SELECT 1 FROM google_documents WHERE document_id=? AND owner_permission=1', (identifier,)):
        raise ValueError('Select this document and confirm owner permission before syncing.')
    if not _LOCK.acquire(blocking=False):
        raise ValueError('A Google connection or sync is already running.')
    try:
        document = fetch_document(store, identifier)
        if document.get('documentId') != identifier:
            raise ValueError('Google returned a different document.')
        title = document.get('title', identifier)
        text = extract(document)
        if not text.strip():
            raise ValueError('No supported body text was returned; previous evidence was retained.')
        source = store.source(title, 'import', 'google-doc:' + identifier)
        store.save(source['id'], identifier, 'document', title, text, json.dumps(document, sort_keys=True),
                   {'adapter': 'google_docs', 'source_url': 'https://docs.google.com/document/d/' + identifier,
                    'data_use': 'personal_context_only', 'owner_permission': True,
                    'provider_revision': document.get('revisionId'), 'extractor': 'proofpage.google_docs/v1',
                    'coverage': 'Authorized Google Docs API body/table text across tabs. Images, comments and suggested edits are not included in extracted text. No HTTP receipt is asserted.'})
        with store.db() as db:
            db.execute("UPDATE google_documents SET title=?,state='available',last_sync=?,detail='',next_run=?+interval_seconds WHERE document_id=?", (title, now(), time.time(), identifier))
        revision = store.rows('SELECT current_revision FROM items WHERE source_id=? AND external_id=?', (source['id'], identifier))[0]['current_revision']
        return {'document_id': identifier, 'revision_id': revision, 'state': 'available'}
    except Exception as exc:
        message = str(exc) if isinstance(exc, GoogleDocsError) else 'Google Docs sync failed. Check your connection, reconnect Google if needed, and retry this document.'
        with store.db() as db:
            db.execute("UPDATE google_documents SET state='error',detail=?,next_run=?+MAX(interval_seconds,3600) WHERE document_id=?", (message, time.time(), identifier))
        raise GoogleDocsError(message + ' Existing evidence was retained.') from None
    finally:
        _LOCK.release()


def tick(store):
    rows = store.rows('SELECT document_id FROM google_documents WHERE interval_seconds>0 AND next_run<=? ORDER BY next_run LIMIT 1', (time.time(),))
    if rows:
        try: sync(store, rows[0]['document_id'])
        except ValueError: pass
