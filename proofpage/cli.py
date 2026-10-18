import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from .core import Store, import_file, preview


def main():
    parser = argparse.ArgumentParser(description='Proofpage local evidence workspace')
    parser.add_argument('--version', action='version', version='Proofpage 0.2.2')
    parser.add_argument('--home', help='Local data directory (default: PROOFPAGE_HOME or ~/.proofpage)')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('doctor', help='Check Python, SQLite search, and the workspace path')
    server = sub.add_parser('serve', help='Open the local browser workspace')
    server.add_argument('--port', type=int, default=8765)
    server.add_argument('--open', action='store_true', help='Open the workspace in your default browser')
    collect = sub.add_parser('collect', help='Capture a public web page')
    collect.add_argument('url')
    search = sub.add_parser('search', help='Search saved evidence; returns JSON')
    search.add_argument('query')
    rights = sub.add_parser('rights', help='Show the AI-usage signals recorded for a source; returns JSON')
    rights.add_argument('source', help='Source ID or its exact URL')
    claim = sub.add_parser('check-answer', help='Preview or check quoted citations in a UTF-8 document')
    claim.add_argument('path')
    claim.add_argument('--preview', action='store_true', help='Show citation pairing without saving or fetching')
    claim.add_argument('--collect', action='store_true', help='Authorize collection of missing/stale public pages')
    claim.add_argument('--max-age', type=int, default=86400)
    job = sub.add_parser('quote-check', help='Read, advance, cancel, or export a saved quote check')
    job.add_argument('job_id')
    operation = job.add_mutually_exclusive_group()
    operation.add_argument('--step', action='store_true')
    operation.add_argument('--cancel', action='store_true')
    operation.add_argument('--format', choices=['json', 'markdown', 'html'])
    checker = sub.add_parser('verify', help='Verify a proof bundle (.zip) or web archive (.wacz) offline')
    checker.add_argument('path')
    archive = sub.add_parser('export-wacz', help='Export a source as a WACZ web archive with signed receipts')
    archive.add_argument('source', help='Source ID or its exact URL')
    archive.add_argument('--output', required=True, help='New file to create, for example ~/Proofpage/exports/site.wacz')
    proof = sub.add_parser('proof-bundle', help='Write a proof bundle for one revision')
    proof.add_argument('revision')
    proof.add_argument('--output', required=True, help='New ZIP file to create')
    sub.add_parser('receipts', help='Show the signing key and re-check the receipt chain; returns JSON')
    sub.add_parser('anchor', help='Timestamp receipts issued since the last anchor (requires anchoring settings)')
    imp = sub.add_parser('import', help='Preview an archive or import selected entries')
    imp.add_argument('path')
    imp.add_argument('--select', action='append', help='Exact entry name from preview; repeat for multiple entries')
    imp.add_argument('--profile', help='Account-specific import profile ID')
    profile = sub.add_parser('profile', help='Create an archive import profile')
    profile.add_argument('name')
    profile.add_argument('--provider', required=True)
    profile.add_argument('--account', required=True)
    profile.add_argument('--adapter', default='auto')
    watch = sub.add_parser('watch', help='Watch a folder for supplied exports')
    watch.add_argument('directory')
    watch.add_argument('--profile', required=True)
    watch.add_argument('--category', action='append', required=True)
    scan = sub.add_parser('scan', help='Scan a watched folder once')
    scan.add_argument('watch_id')
    back = sub.add_parser('backup', help='Create a consistent database backup')
    back.add_argument('destination')
    restoration = sub.add_parser('restore', help='Restore a backup into a new workspace')
    restoration.add_argument('backup_path')
    restoration.add_argument('directory')
    validator = sub.add_parser('validate-dataset', help='Validate an exported corpus')
    validator.add_argument('path')
    validator.add_argument('--sha256')
    hosted = sub.add_parser('hosted', help='Run the optional hosted edition')
    hosted.add_argument('--port', type=int, default=8000)
    hosted.add_argument('--bind', default='127.0.0.1')
    invite = sub.add_parser('invite', help='Create a hosted account invitation')
    invite.add_argument('email')
    sub.add_parser('remote-mcp', help='Connect an agent to a hosted workspace')
    sub.add_parser('mcp', help='Run the local MCP server over stdio')
    sub.add_parser('desktop', help='Open the optional Tk desktop interface')
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    if args.command == 'doctor':
        with sqlite3.connect(':memory:') as db:
            try:
                db.execute('CREATE VIRTUAL TABLE check_search USING fts5(text)')
                fts = True
            except sqlite3.OperationalError:
                fts = False
        directory = Path(args.home or os.environ.get('PROOFPAGE_HOME', '~/.proofpage')).expanduser().resolve()
        print(json.dumps({'python': sys.version.split()[0], 'sqlite': sqlite3.sqlite_version,
                          'fts5': fts, 'workspace': str(directory),
                          'workspace_exists': directory.exists(),
                          'ready': sys.version_info >= (3, 11) and fts}, indent=2))
        if not fts or sys.version_info < (3, 11):
            raise SystemExit(1)
        return
    if args.command == 'hosted':
        import uvicorn
        from .hosted import create_app
        uvicorn.run(create_app(root=args.home), host=args.bind, port=args.port, proxy_headers=False, access_log=False)
        return
    if args.command == 'invite':
        from .accounts import Accounts
        print(Accounts(args.home or os.environ.get('PROOFPAGE_HOSTED_HOME','~/.proofpage-hosted')).invite(args.email))
        return
    if args.command == 'remote-mcp':
        from .remote import run
        run()
        return
    if args.command == 'verify':
        from .verify import verify_path
        report = verify_path(args.path)
        print('\n'.join(report.lines))
        print(f"\n{'VERIFIED' if not report.failures else 'NOT VERIFIED'}: {report.failures} failed check(s).")
        raise SystemExit(1 if report.failures else 0)
    if args.command == 'validate-dataset':
        from .datasets import load_corpus
        records = load_corpus(args.path, args.sha256)
        print(json.dumps({'valid': True, 'records': len(records), 'splits': {split: sum(r['split'] == split for r in records) for split in ('train', 'validation', 'test')}}, indent=2))
        return
    if args.command == 'restore':
        from .backup import restore
        print(json.dumps(restore(args.backup_path, args.directory), indent=2))
        return
    store = Store(args.home)
    if args.command == 'desktop':
        from .desktop import run
        run(store)
        return
    if args.command == 'serve':
        from .server import serve
        serve(store, args.port, open_browser=args.open)
        return
    if args.command == 'mcp':
        from .mcp import run
        run(store)
        return
    if args.command == 'check-answer':
        from . import claims
        with Path(args.path).open(encoding='utf-8') as handle:
            text = handle.read(claims.MAX_TEXT + 1)
        previewed = claims.extract(text)
        result = previewed if args.preview else claims.create(store, previewed['citations'], text, args.collect, args.max_age)
    elif args.command == 'quote-check':
        from . import claims
        if args.format:
            print(claims.export(store, args.job_id, args.format)[0])
            return
        result = claims.step(store, args.job_id) if args.step else claims.cancel(store, args.job_id) if args.cancel else claims.get(store, args.job_id)
    elif args.command == 'profile':
        from .imports import create_profile
        result = create_profile(store, args.name, args.provider, args.account, args.adapter)
    elif args.command == 'watch':
        from .watch import create_watch
        result = create_watch(store, args.profile, args.directory, args.category)
    elif args.command == 'scan':
        from .watch import scan_watch
        result = scan_watch(store, args.watch_id)
    elif args.command == 'backup':
        from .backup import backup
        result = backup(store, args.destination)
    elif args.command == 'collect':
        source = store.source(args.url, 'web', args.url)
        result = store.collect(source['id'])
    elif args.command == 'search':
        result = store.search(args.query)
    elif args.command in ('export-wacz', 'proof-bundle'):
        target = Path(args.output).expanduser()
        if target.exists():
            parser.error('Choose a new output file; existing files are never overwritten.')
        if args.command == 'export-wacz':
            from .wacz import export_wacz
            sources = store.rows('SELECT id FROM sources WHERE id=? OR location=?', (args.source, args.source))
            if not sources:
                parser.error('Source not found. Use a source ID or its exact URL.')
            data, summary = export_wacz(store, sources[0]['id'])
        else:
            from .receipts import proof_bundle
            data, summary = proof_bundle(store, args.revision), {}
        with open(target, 'xb') as handle:
            handle.write(data)
        result = {'path': str(target.resolve()), 'bytes': len(data), **summary}
    elif args.command == 'receipts':
        from .receipts import key_info, verify_chain
        result = {'key': key_info(store), 'chain': verify_chain(store)}
    elif args.command == 'anchor':
        from .receipts import anchor
        result = anchor(store, force=True)
    elif args.command == 'rights':
        sources = store.rows('SELECT * FROM sources WHERE id=? OR location=?', (args.source, args.source))
        if not sources:
            parser.error('Source not found. Use a source ID or its exact URL.')
        rows = store.rows('SELECT o.* FROM rights_observations o WHERE o.source_id=? AND o.rowid=(SELECT x.rowid FROM rights_observations x WHERE x.url=o.url ORDER BY x.observed_at DESC, x.rowid DESC LIMIT 1) ORDER BY o.url', (sources[0]['id'],))
        result = {'source': sources[0]['name'], 'location': sources[0]['location'], 'pages': [
            {'url': r['url'], 'observed_at': r['observed_at'], 'verdict': json.loads(r['verdict']), 'signals': json.loads(r['signals']), 'checked': json.loads(r['checked'])} for r in rows]}
        if not rows:
            result['note'] = 'No rights observations yet. Collect the source to record publisher signals.'
    else:
        path = Path(args.path)
        with path.open('rb') as handle:
            data = handle.read(8 * 1024 * 1024 + 1)
        if args.select and not args.profile:
            parser.error('Importing requires --profile. Create one with the profile command.')
        result = import_file(store, path.name, data, args.select, args.profile) if args.select else preview(path.name, data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
