"""Shared schedule validation for UI and MCP callers."""
import time


def configure(store, source_id, interval_seconds):
    if type(interval_seconds) is not int or (interval_seconds != 0 and not 300 <= interval_seconds <= 31536000):
        raise ValueError('Use 0 to pause, or an interval from 300 seconds to one year.')
    with store.db() as db:
        changed = db.execute("UPDATE sources SET interval_seconds=?,next_run=? WHERE id=? AND kind='web'",
                             (interval_seconds, time.time() + interval_seconds if interval_seconds else 0, source_id))
        if changed.rowcount != 1:
            raise ValueError('Choose an existing web source.')
    return {'saved': True, 'source_id': source_id, 'interval_seconds': interval_seconds,
            'state': 'scheduled' if interval_seconds else 'paused',
            'note': 'Scheduled collection runs while the Proofpage app/server is running. Site budgets and cooldowns still apply.'}
