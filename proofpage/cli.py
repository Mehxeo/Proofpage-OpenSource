import argparse
import json

from .core import Store, import_file, preview


def main():
    parser = argparse.ArgumentParser(description='Proofpage local evidence workspace')
    parser.add_argument('--home', help='Local data directory')
    sub = parser.add_subparsers(dest='command', required=True)
    server = sub.add_parser('serve')
    server.add_argument('--port', type=int, default=8765)
    collect = sub.add_parser('collect')
    collect.add_argument('url')
    search = sub.add_parser('search')
    search.add_argument('query')
    imp = sub.add_parser('import')
    imp.add_argument('path')
    imp.add_argument('--select', action='append', help='Exact entry name from preview; repeat for multiple entries')
    imp.add_argument('--profile', help='Account-specific import profile ID')
    profile = sub.add_parser('profile')
    profile.add_argument('name')
    profile.add_argument('--provider', required=True)
    profile.add_argument('--account', required=True)
    profile.add_argument('--adapter', default='auto')
    watch = sub.add_parser('watch')
    watch.add_argument('directory')
    watch.add_argument('--profile', required=True)
    watch.add_argument('--category', action='append', required=True)
    scan = sub.add_parser('scan')
    scan.add_argument('watch_id')
    back = sub.add_parser('backup')
    back.add_argument('destination')
    restoration = sub.add_parser('restore')
    restoration.add_argument('backup_path')
    restoration.add_argument('directory')
    validator = sub.add_parser('validate-dataset')
    validator.add_argument('path')
    validator.add_argument('--sha256')
    hosted = sub.add_parser('hosted')
    hosted.add_argument('--port', type=int, default=8000)
    hosted.add_argument('--bind', default='127.0.0.1')
    invite = sub.add_parser('invite')
    invite.add_argument('email')
    sub.add_parser('remote-mcp')
    sub.add_parser('mcp')
    sub.add_parser('desktop')
    args = parser.parse_args()
    if args.command == 'hosted':
        import uvicorn
        from .hosted import create_app
        uvicorn.run(create_app(root=args.home), host=args.bind, port=args.port, proxy_headers=False, access_log=False)
        return
    if args.command == 'invite':
        import os
        from .accounts import Accounts
        print(Accounts(args.home or os.environ.get('PROOFPAGE_HOSTED_HOME','~/.proofpage-hosted')).invite(args.email))
        return
    if args.command == 'remote-mcp':
        from .remote import run
        run()
        return
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
        serve(store, args.port)
        return
    if args.command == 'mcp':
        from .mcp import run
        run(store)
        return
    if args.command == 'profile':
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
    else:
        from pathlib import Path
        path = Path(args.path)
        with path.open('rb') as handle:
            data = handle.read(8 * 1024 * 1024 + 1)
        if args.select and not args.profile:
            parser.error('Importing requires --profile. Create one with the profile command.')
        result = import_file(store, path.name, data, args.select, args.profile) if args.select else preview(path.name, data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
