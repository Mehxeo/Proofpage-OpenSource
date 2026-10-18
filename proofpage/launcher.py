"""Small native controller for the full browser workspace; Python is bundled."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import webbrowser

from .core import Store
from .server import serve


class WorkspaceLock:
    """Hold an OS lock for the whole app lifetime, released even after a crash."""
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.file = (directory / '.desktop.lock').open('a+b')
        if (directory / '.desktop.lock').stat().st_size == 0:
            self.file.write(b'0')
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RuntimeError('Proofpage is already running for this workspace. Open its existing window.')

    def close(self):
        if not self.file.closed:
            if os.name == 'nt':
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            self.file.close()


def main():
    import tkinter as tk
    from tkinter import messagebox
    # Used only by release validation; an ordinary double click has no arguments.
    report = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test' else None
    folder = report.parent / 'workspace' if report else Path.home() / 'Proofpage'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name in ('data', 'backups', 'exports'):
        (folder / name).mkdir(exist_ok=True, mode=0o700)
    root = tk.Tk()
    if report:
        def callback_error(kind, value, tb):
            import traceback
            report.write_text(json.dumps({'ready': False, 'error': ''.join(traceback.format_exception(kind, value, tb))}))
            root.destroy()
        root.report_callback_exception = callback_error
        root.after(30000, lambda: (report.write_text(json.dumps({'ready': False, 'error': 'GUI startup timed out'})), root.destroy()))
    root.title('Proofpage')
    root.geometry('600x390')
    root.minsize(580, 370)
    paper, ink, muted, accent = '#f5f2ea', '#1c201e', '#5f665f', '#1e5b43'  # Archival ink palette (static/style.css).
    root.configure(bg=paper)
    try:
        lock = WorkspaceLock(folder / 'data')
    except RuntimeError as exc:
        root.withdraw()
        messagebox.showinfo('Proofpage is already open', str(exc), parent=root)
        root.destroy()
        return
    events = queue.Queue()
    server = None
    stopping = False
    status = tk.StringVar(value='Starting your private workspace…')
    url = tk.StringVar(value='Everything stays on this computer.')
    frame = tk.Frame(root, bg=paper, padx=30, pady=26)
    frame.pack(fill='both', expand=True)
    tk.Label(frame, text='Proofpage', font=('Georgia', 30, 'bold'), fg=accent, bg=paper).pack(anchor='w')
    tk.Label(frame, text='Your sources. Your evidence.', font=('Helvetica', 14), fg=muted, bg=paper).pack(anchor='w', pady=(6, 22))
    tk.Label(frame, textvariable=status, font=('Helvetica', 13), fg=ink, bg=paper, wraplength=460, justify='left').pack(anchor='w')
    tk.Label(frame, textvariable=url, font=('Helvetica', 11), fg=muted, bg=paper).pack(anchor='w', pady=(6, 18))

    def open_workspace():
        if server:
            webbrowser.open(f'http://127.0.0.1:{server.server_address[1]}')

    def open_folder():
        if sys.platform == 'win32':
            os.startfile(str(folder))
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', str(folder)])
        else:
            subprocess.Popen(['xdg-open', str(folder)])

    buttons = tk.Frame(frame, bg=paper)
    buttons.pack(anchor='w', pady=8)
    launch = tk.Button(buttons, text='Open workspace', command=open_workspace, state='disabled', padx=14, pady=8)
    launch.pack(side='left', padx=(0, 10))
    tk.Button(buttons, text='Show data folder', command=open_folder, padx=10, pady=8).pack(side='left')
    tk.Button(buttons, text='App updates', command=lambda: webbrowser.open(f'http://127.0.0.1:{server.server_address[1]}/#/settings') if server else None, padx=10, pady=8).pack(side='left', padx=(10, 0))
    tk.Label(frame, text='Keep this window open while you work.\nClosing it stops collection; your saved evidence stays safe.', font=('Helvetica', 11), fg=muted, bg=paper, justify='left').pack(anchor='w', pady=(18, 0))

    def worker():
        try:
            store = Store(folder / 'data')
            serve(store, port=0, on_ready=lambda httpd: events.put(('ready', httpd)))
        except Exception as exc:
            events.put(('error', str(exc)))
        finally:
            events.put(('stopped', None))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    def stop():
        nonlocal stopping
        if stopping:
            return
        stopping = True
        launch.configure(state='disabled')
        status.set('Stopping Proofpage. Finishing any active captures…')
        if server:
            threading.Thread(target=server.shutdown, daemon=True).start()
        elif not thread.is_alive():
            root.destroy()

    def check():
        nonlocal server
        try:
            while True:
                event, value = events.get_nowait()
                if event == 'ready':
                    server = value
                    if stopping:
                        threading.Thread(target=server.shutdown, daemon=True).start()
                        continue
                    address = f'http://127.0.0.1:{server.server_address[1]}'
                    status.set('Your workspace is ready.')
                    url.set(address)
                    launch.configure(state='normal')
                    if report:
                        from urllib.request import urlopen, Request
                        with urlopen(address + '/api/session', timeout=5) as response:
                            token = json.load(response)['token']
                        with urlopen(Request(address + '/api/state', headers={'Authorization': 'Bearer ' + token}), timeout=5) as response:
                            state = json.load(response)
                        with urlopen(address, timeout=5) as response:
                            assert b'Proofpage' in response.read()
                        with urlopen(Request(address + '/api/mcp-setup', headers={'Authorization': 'Bearer ' + token}), timeout=5) as response:
                            connection = json.load(response)
                        # Exercise new routes in the frozen runtime, without network collection.
                        payload = json.dumps({'citations': [{'quote': 'Packaged fixture quote', 'url': None}], 'collect_missing': False}).encode()
                        with urlopen(Request(address + '/api/claim-check', data=payload, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}), timeout=5) as response:
                            checked = json.load(response)
                        assert checked['state'] == 'complete' and checked['items'][0]['result']['status'] == 'no_source'
                        from . import verify
                        assert Path(verify.__file__).with_suffix('.py').is_file(), 'Offline verifier source missing from bundle'
                        report.write_text(json.dumps({'ready': True, 'gui': True, 'records': len(state['items']), 'quote_check': True, 'offline_verifier': True, 'mcp': connection['config']['mcpServers']['proofpage']}))
                        stop()
                    else:
                        open_workspace()
                elif event == 'error':
                    status.set('Could not start your workspace.')
                    if report:
                        report.write_text(json.dumps({'ready': False, 'error': value}))
                        root.destroy()
                        return
                    else:
                        messagebox.showerror('Proofpage could not start', value, parent=root)
                elif event == 'stopped':
                    if stopping:
                        root.destroy()
                        return
                    status.set('Workspace stopped. Close and reopen Proofpage to retry.')
                    launch.configure(state='disabled')
        except queue.Empty:
            pass
        root.after(100, check)

    root.protocol('WM_DELETE_WINDOW', stop)
    root.after(100, check)
    try:
        root.mainloop()
    finally:
        lock.close()
