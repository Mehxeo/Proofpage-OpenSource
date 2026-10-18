"""Consistent SQLite backup and restore into a new workspace only."""
import os
import sqlite3
from pathlib import Path


def backup(store, destination):
    destination = Path(destination).expanduser().resolve()
    # Exclusive creation avoids overwriting an existing backup or live database.
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with store.db() as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup integrity check failed.')
            finally:
                target.close()
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    result = {'path': str(destination), 'integrity': 'ok'}
    with store.db() as db:
        if 'signing_keys' in {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} and db.execute('SELECT 1 FROM signing_keys').fetchone():
            result['note'] = 'This backup contains your receipt-signing key. Keep it private; anyone with it can sign receipts as this workspace.'
    return result


def restore(backup_path, directory):
    source_path = Path(backup_path).expanduser().resolve(strict=True)
    directory = Path(directory).expanduser().resolve()
    if directory.exists():
        raise ValueError('Restore requires a new workspace directory; existing data is never overwritten.')
    source = sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)
    try:
        if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Backup integrity check failed.')
        tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'sources', 'items', 'revisions', 'datasets', 'reviews'}.issubset(tables):
            raise ValueError('This file is not a Proofpage backup.')
        directory.mkdir(mode=0o700)
        target = sqlite3.connect(directory / 'proofpage.sqlite3')
        try:
            source.backup(target)
            # Restoring must not trigger external collection as an incidental effect.
            target.execute('UPDATE sources SET interval_seconds=0')
            if 'watches' in tables:
                target.execute("UPDATE watches SET enabled=0,state='paused',detail='Restored; explicitly resume this folder watch.'")
            if 'crawl_jobs' in tables:
                target.execute("UPDATE crawl_jobs SET state='cancelled',lease_until=0,detail='Restored; create a new crawl to resume collection.' WHERE state IN ('queued','running')")
            if 'watch_leases' in tables:
                target.execute('DELETE FROM watch_leases')
            target.execute("UPDATE runs SET state='interrupted' WHERE state='running'")
            target.commit()
        finally:
            target.close()
        os.chmod(directory / 'proofpage.sqlite3', 0o600)
    finally:
        source.close()
    return {'directory': str(directory), 'integrity': 'ok', 'automation': 'paused'}
