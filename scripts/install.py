"""Install this release in an isolated, user-owned folder. No administrator access."""
import argparse
import os
from pathlib import Path
import shlex
import sqlite3
import subprocess
import sys
import venv


def install():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path.home() / 'Proofpage', help='New install folder (default: ~/Proofpage)')
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error('Install Python 3.11 or newer first: https://www.python.org/downloads/')
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE VIRTUAL TABLE check_search USING fts5(text)')
    target = args.directory.expanduser().resolve()
    if target.exists():
        parser.error(f'{target} already exists. Choose a new --directory; existing data will not be overwritten.')
    source = Path(__file__).resolve().parents[1]
    wheels = sorted(source.glob('proofpage-*.whl'))
    package = wheels[0] if len(wheels) == 1 else source
    if not wheels and not (source / 'pyproject.toml').exists():
        parser.error('Run this installer from the extracted release folder or source checkout.')
    target.mkdir(parents=True, mode=0o700)
    for name in ('data', 'backups', 'exports'):
        (target / name).mkdir(mode=0o700)
    runtime = target / 'runtime'
    print(f'Installing into {target}', flush=True)
    venv.EnvBuilder(with_pip=True).create(runtime)
    python = runtime / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', str(package)], check=True)
    if os.name == 'nt':
        # %~dp0 resolves to the launcher folder even when launched from Explorer.
        command = '@echo off\r\n"%~dp0runtime\\Scripts\\python.exe" -m proofpage --home "%~dp0data"'
        (target / 'Start Proofpage.cmd').write_text(command + ' serve --open\r\npause\r\n')
        (target / 'proofpage.cmd').write_text(command + ' %*\r\n')
    else:
        command = f'exec {shlex.quote(str(python))} -m proofpage --home {shlex.quote(str(target / "data"))}'
        for name, tail in [('Start Proofpage.command', ' serve --open'), ('proofpage', ' "$@"')]:
            launcher = target / name
            launcher.write_text('#!/bin/sh\n' + command + tail + '\n')
            launcher.chmod(0o700)
    (target / 'READ ME.txt').write_text('PROOFPAGE\n\nOpen Start Proofpage to launch your local workspace. Keep its terminal open.\nPress Ctrl+C in that terminal to stop.\n\ndata/     Private evidence and settings. Keep this folder.\nbackups/  Suggested location for backups made with the backup command.\nexports/  Suggested location for downloaded datasets.\nruntime/  Isolated Python installation.\n\nThe proofpage launcher provides the CLI; run it with --help.\nDo not move this installation: its Python environment uses absolute paths.\nNo account or subscription required.\n')
    subprocess.run([str(python), '-m', 'proofpage', '--home', str(target / 'data'), 'doctor'], check=True)
    print(f'\nReady. Open the Start Proofpage launcher in {target}.')


if __name__ == '__main__':
    try:
        install()
    except (OSError, subprocess.CalledProcessError, sqlite3.Error) as exc:
        raise SystemExit(f'Installation failed: {exc}\nIf an incomplete folder was created, choose a new --directory to retry. Your existing workspaces are unchanged.')
