"""Windowed entry point. Redirect diagnostics when a console is unavailable."""
import os
from pathlib import Path
import sys

if sys.stdout is None or sys.stderr is None:
    log_dir = Path.home() / 'Proofpage'
    log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    log = log_dir / 'launcher.log'
    if log.exists() and log.stat().st_size > 1024 * 1024:
        log.replace(log.with_suffix('.previous.log'))
    handle = log.open('a', encoding='utf-8', buffering=1)
    sys.stdout = handle
    sys.stderr = handle

if __name__ == '__main__':
    try:
        from proofpage.launcher import main
        main()
    except Exception:
        import traceback
        detail = traceback.format_exc()
        print(detail, file=sys.stderr)
        if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test':
            import json
            Path(sys.argv[2]).write_text(json.dumps({'ready': False, 'error': detail}))
        else:
            from tkinter import messagebox
            messagebox.showerror('Proofpage could not start', 'Please see Proofpage/launcher.log in your user folder for details.')
        raise SystemExit(1)
