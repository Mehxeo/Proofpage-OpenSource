"""Install the bundled skill into a user-selected project without overwriting."""
from pathlib import Path


def install(project, client):
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise ValueError('Choose an existing project directory.')
    folders = {'codex': '.agents', 'claude': '.claude'}
    if client not in folders:
        raise ValueError('Choose codex or claude.')
    target = root / folders[client] / 'skills' / 'proofpage' / 'SKILL.md'
    if not target.resolve().is_relative_to(root):
        raise ValueError('Skill destination must remain inside the selected project.')
    content = (Path(__file__).parent / 'skills' / 'proofpage' / 'SKILL.md').read_bytes()
    if target.exists():
        if target.read_bytes() == content:
            return {'path': str(target), 'state': 'already_installed'}
        raise ValueError('A different skill already exists. Review it before replacing it; no file was changed.')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as handle: handle.write(content)
    return {'path': str(target), 'state': 'installed', 'note': 'Restart or reload your client if required. A skill does not configure MCP.'}
