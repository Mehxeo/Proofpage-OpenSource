"""Native Tk desktop client sharing the collection and evidence store."""
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .core import import_file, preview


def run(store):
    root = tk.Tk()
    root.title('Proofpage — Local evidence')
    root.geometry('1100x740')
    events = queue.Queue()
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Proofpage', font=('Helvetica', 26, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='Local evidence · Static pages and supplied archives').pack(anchor='w', pady=(4, 20))
    toolbar = ttk.Frame(frame)
    toolbar.pack(fill='x')
    query = tk.StringVar()
    search = ttk.Entry(toolbar, textvariable=query)
    search.pack(side='left', fill='x', expand=True, padx=(0, 10))
    status = tk.StringVar(value='Ready. Select a record to inspect its evidence.')
    panes = ttk.Panedwindow(frame, orient='horizontal')
    panes.pack(fill='both', expand=True, pady=18)
    listing = ttk.Treeview(panes, columns=('kind',), show='tree headings', selectmode='browse')
    listing.heading('#0', text='Record')
    listing.heading('kind', text='Kind')
    listing.column('#0', width=260)
    listing.column('kind', width=100)
    detail = tk.Text(panes, wrap='word', padx=18, pady=16, background='#f5f2ea', foreground='#1c201e', relief='flat')
    panes.add(listing, weight=1)
    panes.add(detail, weight=2)
    ttk.Label(frame, textvariable=status, wraplength=1000).pack(anchor='w')

    def refresh():
        listing.delete(*listing.get_children())
        for item in store.search(query.get()):
            listing.insert('', 'end', iid=item['id'], text=item['title'], values=(item['kind'],))

    def background(work):
        status.set('Working…')
        def worker():
            try:
                events.put((True, work()))
            except Exception as exc:
                events.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll():
        try:
            while True:
                ok, result = events.get_nowait()
                status.set(str(result))
                if not ok:
                    messagebox.showerror('Proofpage', str(result), parent=root)
                refresh()
        except queue.Empty:
            pass
        root.after(100, poll)

    def selected():
        selection = listing.selection()
        return store.item(selection[0]) if selection else None

    def inspect(_=None):
        item = selected()
        if not item:
            return
        detail.configure(state='normal')
        detail.delete('1.0', 'end')
        detail.insert('end', f"{item['title']}\n\nSource: {item['source_name']}\nCaptured: {item['captured_at']}\nSource time: {item['source_time'] or 'Not supplied'}\nSHA-256: {item['hash']}\n\n{item['text']}\n\nCOVERAGE\n{item['metadata']}\n\nORIGINAL EVIDENCE\n{item['raw']}")
        detail.configure(state='disabled')

    def collect():
        url = simpledialog.askstring('Collect public page', 'Public HTTP(S) page URL:', parent=root)
        if url:
            def work():
                source = store.source(url, 'web', url)
                result = store.collect(source['id'])
                return result['state'] + ': ' + result['detail']
            background(work)

    def import_archive():
        filename = filedialog.askopenfilename(parent=root, title='Select supplied archive or document')
        if not filename:
            return
        try:
            with Path(filename).open('rb') as handle:
                data = handle.read(8 * 1024 * 1024 + 1)
            entries = preview(Path(filename).name, data)
        except Exception as exc:
            messagebox.showerror('Import preview', str(exc), parent=root)
            return
        dialog = tk.Toplevel(root)
        dialog.title('Select entries to import')
        dialog.geometry('650x480')
        ttk.Label(dialog, text='Choose categories. Fields remain as supplied.', padding=15).pack(anchor='w')
        profile_box = ttk.Combobox(dialog, state='readonly')
        profile_box.pack(fill='x', padx=15, pady=8)
        profiles = []
        def load_profiles():
            profiles[:] = store.rows('SELECT * FROM import_profiles ORDER BY name')
            profile_box['values'] = [p['name'] + ' · ' + p['account'] for p in profiles]
            if profiles:
                profile_box.current(len(profiles) - 1)
        def add_profile():
            from .imports import create_profile
            provider = simpledialog.askstring('Provider', 'Provider name (for example ChatGPT or LinkedIn):', parent=dialog)
            if not provider:
                return
            account = simpledialog.askstring('Account label', 'Account label (not a password):', parent=dialog)
            if not account:
                return
            try:
                create_profile(store, provider + ' · ' + account, provider, account, 'linkedin' if provider.lower() == 'linkedin' else 'auto')
                load_profiles()
            except ValueError as exc:
                messagebox.showerror('Import profile', str(exc), parent=dialog)
        ttk.Button(dialog, text='Create account profile', command=add_profile).pack(pady=5)
        load_profiles()
        files = tk.Listbox(dialog, selectmode='multiple', exportselection=False)
        files.pack(fill='both', expand=True, padx=15)
        for entry in entries:
            files.insert('end', entry['name'])
        def commit():
            names = [entries[index]['name'] for index in files.curselection()]
            if not names or profile_box.current() < 0:
                messagebox.showinfo('Import', 'Choose an account profile and at least one category.', parent=dialog)
                return
            profile_id = profiles[profile_box.current()]['id']
            dialog.destroy()
            background(lambda: import_file(store, Path(filename).name, data, names, profile_id))
        ttk.Button(dialog, text='Import selected entries', command=commit).pack(pady=15)

    def review():
        item = selected()
        if item and messagebox.askyesno('Review revision', 'Have you reviewed this revision and confirmed permission to include it in a clean corpus?', parent=root):
            store.review(item['current_revision'], True, True)
            status.set('This revision is approved for clean-corpus export.')

    def revoke():
        item = selected()
        if item:
            store.review(item['current_revision'], False, False)
            status.set('Permission revoked. Managed exports containing this revision are blocked.')

    def export():
        destination = filedialog.asksaveasfilename(parent=root, title='Export reviewed clean corpus', defaultextension='.jsonl')
        if not destination:
            return
        def work():
            dataset = store.freeze('Desktop reviewed corpus')
            Path(destination).write_text(store.export(dataset['id']), encoding='utf-8')
            return f"Exported {dataset['records']} reviewed records. This does not train a model."
        background(work)

    ttk.Button(toolbar, text='Search', command=refresh).pack(side='left', padx=3)
    ttk.Button(toolbar, text='Collect page', command=collect).pack(side='left', padx=3)
    ttk.Button(toolbar, text='Import', command=import_archive).pack(side='left', padx=3)
    reviews = ttk.Frame(frame)
    reviews.pack(fill='x', pady=12)
    ttk.Button(reviews, text='Approve selected revision', command=review).pack(side='left', padx=3)
    ttk.Button(reviews, text='Revoke permission', command=revoke).pack(side='left', padx=3)
    ttk.Button(reviews, text='Export reviewed corpus', command=export).pack(side='right', padx=3)
    listing.bind('<<TreeviewSelect>>', inspect)
    search.bind('<Return>', lambda event: refresh())
    refresh()
    poll()
    root.mainloop()
