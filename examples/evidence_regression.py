"""Run with python examples/evidence_regression.py after installing this checkout.

Offline fixture: an answer cites $20, the source changes to $30, and the
regression report identifies the affected answer while replay keeps $20.
"""
import json
import tempfile
from pathlib import Path
from proofpage.sdk import Proofpage


def main():
    with tempfile.TemporaryDirectory(prefix='proofpage-demo-') as directory:
        client = Proofpage(home=Path(directory) / 'workspace')
        source = client.store.source('Demo pricing', 'import', 'fixture:pricing')
        old = 'The plan costs $20 per month.'
        client.store.save(source['id'], 'pricing', 'text', 'Pricing', old, old)
        revision = client.store.rows('SELECT current_revision FROM items')[0]['current_revision']
        manifest = client.record([revision], dependencies=[{
            'output_id': 'pricing-answer', 'revision_id': revision,
            'start': 0, 'end': len(old), 'quote': old,
        }])
        path = Path(directory) / 'inputs.json'
        checksum = client.write(manifest, path)
        client.store.save(source['id'], 'pricing', 'text', 'Pricing', 'The plan costs $30 per month.', 'The plan costs $30 per month.')
        report = client.check(manifest)
        assert not report['ok']
        assert report['records'][0]['affected_outputs'] == ['pricing-answer']
        assert client.replay(path, checksum)['records'][0]['text'] == old
        print(json.dumps(report, indent=2))
        print('PASS: drift detected; pinned replay preserved the original input.')


if __name__ == '__main__':
    main()
