import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from .core import Store, import_file, preview


def main():
    parser = argparse.ArgumentParser(description='Proofpage local evidence workspace')
    parser.add_argument('--version', action='version', version='Proofpage 0.4.0')
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
    ev = sub.add_parser('evidence', help='Record, replay, check, or explicitly refresh pinned inputs')
    ev.add_argument('operation', choices=['record', 'replay', 'check', 'refresh'])
    ev.add_argument('path', help='Manifest JSON path; record creates a new file')
    ev.add_argument('--revision', action='append', default=[])
    ev.add_argument('--dependencies', help='JSON file of output IDs and exact quote ranges')
    ev.add_argument('--sha256', help='Trusted manifest checksum')
    ev.add_argument('--name', default='Evidence run')
    runs = sub.add_parser('evidence-run', help='Track retrieved agent inputs and output dependencies')
    runs.add_argument('operation', choices=['record-context', 'list', 'replay', 'check', 'affected', 'export'])
    runs.add_argument('identifier', nargs='?', help='Run ID, or item ID for affected')
    runs.add_argument('--query')
    runs.add_argument('--output-id')
    runs.add_argument('--name', default='Evidence run')
    runs.add_argument('--output', help='New manifest file for export')
    business_parser = sub.add_parser('business', help='Local business context profiles and portable exports')
    business_parser.add_argument('operation', choices=['create', 'list', 'get', 'attach', 'draft', 'review', 'export', 'bookmarks-preview', 'bookmarks-import'])
    business_parser.add_argument('--id')
    business_parser.add_argument('--name')
    business_parser.add_argument('--revision')
    business_parser.add_argument('--role', choices=['business', 'customer', 'reference', 'writing'])
    business_parser.add_argument('--text')
    business_parser.add_argument('--decision', choices=['draft', 'approved', 'rejected'])
    business_parser.add_argument('--permission', action='store_true')
    business_parser.add_argument('--acknowledge', action='store_true')
    business_parser.add_argument('--path')
    business_parser.add_argument('--select', type=int, action='append')
    google = sub.add_parser('google-docs', help='Connect and sync explicitly selected Google Docs (optional google extra)')
    google.add_argument('operation', choices=['status', 'connect', 'disconnect', 'select', 'sync'])
    google.add_argument('--document')
    google.add_argument('--interval', type=int, default=0, choices=[0, 3600, 21600, 86400])
    google.add_argument('--owner-permission', action='store_true', help='Confirm owner permission to retain personal-context snapshots')
    http_mcp = sub.add_parser('mcp-http', help='Serve read-only OAuth-protected MCP behind your HTTPS reverse proxy')
    http_mcp.add_argument('--port', type=int, default=8910)
    skill = sub.add_parser('install-skill', help='Install the bundled skill in a chosen project without overwriting')
    skill.add_argument('--project', required=True)
    skill.add_argument('--client', required=True, choices=['codex', 'claude'])
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    if args.command == 'install-skill':
        from .skill_install import install
        try: print(json.dumps(install(args.project, args.client), indent=2))
        except (ValueError, OSError) as exc:
            print(json.dumps({'error': str(exc)})); raise SystemExit(2)
        return
    if args.command == 'mcp-http':
        from .mcp_http import run
        run(Store(args.home), args.port)
        return
    if args.command == 'google-docs':
        from . import google_docs
        try:
            workspace = Store(args.home)
            if args.operation == 'select': result = google_docs.select(workspace, args.document, args.interval, args.owner_permission)
            elif args.operation == 'sync': result = google_docs.sync(workspace, args.document)
            else: result = getattr(google_docs, args.operation)(workspace)
            print(json.dumps(result, indent=2))
        except (ImportError, ValueError, OSError):
            print(json.dumps({'error': 'Google Docs operation failed. Install the google extra and check OAuth configuration, OS vault, and selected document access.'}))
            raise SystemExit(2)
        return
    if args.command == 'business':
        from . import business
        try:
            workspace = Store(args.home)
            op = args.operation
            if op == 'create': result = business.create(workspace, args.name)
            elif op == 'list': result = workspace.rows('SELECT * FROM business_profiles ORDER BY created_at DESC')
            elif op == 'get': result = business.get(workspace, args.id)
            elif op == 'attach': result = business.attach(workspace, args.id, args.revision, args.role)
            elif op == 'draft': result = business.draft(workspace, args.id)
            elif op == 'review': result = business.review(workspace, args.id, args.text, args.decision, args.permission, args.acknowledge)
            elif op.startswith('bookmarks-'):
                if not args.path: raise ValueError('Provide --path to a bookmark HTML export.')
                with open(args.path, encoding='utf-8') as handle: html = handle.read(2 * 1024 * 1024 + 1)
                result = business.bookmark_preview(html) if op == 'bookmarks-preview' else business.import_bookmarks(workspace, html, args.select)
            else:
                if not args.path: raise ValueError('Provide --path for a new ZIP file.')
                payload = business.export_pack(workspace, args.id)
                descriptor = os.open(args.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, 'wb') as handle: handle.write(payload)
                result = {'path': args.path, 'bytes': len(payload)}
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except (ValueError, OSError) as exc:
            print(json.dumps({'error': str(exc)})); raise SystemExit(2)
        return
    if args.command == 'evidence-run':
        from . import evidence_runs, evidence
        try:
            workspace = Store(args.home)
            if args.operation == 'record-context':
                result = evidence_runs.record_context(workspace, args.query, args.output_id, args.name)
            elif args.operation == 'list':
                result = evidence_runs.list_runs(workspace)
            elif args.operation == 'export':
                if not args.output:
                    raise ValueError('Provide --output with a new file path.')
                result = {'sha256': evidence.write(evidence_runs.get(workspace, args.identifier), args.output)}
            else:
                operation = {'replay': evidence_runs.replay_context, 'check': evidence_runs.check, 'affected': evidence_runs.affected}[args.operation]
                result = operation(workspace, args.identifier)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if args.operation == 'check' and not result['ok']:
                raise SystemExit(1)
        except (ValueError, OSError) as exc:
            print(json.dumps({'error': str(exc)}))
            raise SystemExit(2)
        return
    if args.command == 'evidence':
        from . import evidence
        try:
            if args.operation == 'record':
                dependencies = json.loads(Path(args.dependencies).read_text()) if args.dependencies else []
                manifest = evidence.record(Store(args.home), args.revision, dependencies, args.name)
                checksum = evidence.write(manifest, args.path)
                result = {'path': str(Path(args.path).resolve()), 'sha256': checksum}
            else:
                manifest = evidence.replay(args.path, args.sha256)
                result = manifest if args.operation == 'replay' else evidence.compare(Store(args.home), manifest) if args.operation == 'check' else evidence.refresh(Store(args.home), manifest)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if args.operation == 'check' and not result['ok']:
                raise SystemExit(1)
            if args.operation == 'refresh' and (not result['comparison']['ok'] or any(r.get('state') != 'available' for r in result['refresh'])):
                raise SystemExit(1)
        except (ValueError, OSError) as exc:
            print(json.dumps({'error': str(exc)}))
            raise SystemExit(2)
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
