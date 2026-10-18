import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { Proofpage } from './index.js';

test('real Python bridge records, replays, checks and rejects a bad pin', async () => {
  const home = await mkdtemp(join(tmpdir(), 'proofpage-sdk-'));
  const python = process.env.PROOFPAGE_TEST_PYTHON || 'python3';
  try {
    const rid = execFileSync(python, ['-c', `from proofpage.core import Store
import sys
s=Store(sys.argv[1]); src=s.source('fixture','import','fixture:sdk')
s.save(src['id'],'1','text','Example','Unicode café 📖','original')
print(s.rows('SELECT id FROM revisions')[0]['id'])`, home], { encoding: 'utf8' }).trim();
    const client = new Proofpage({ python, home });
    const path = join(home, 'run.json');
    const saved = await client.record(path, { revisions: [rid] });
    assert.equal((await client.replay(path, { sha256: saved.sha256 })).records[0].text, 'Unicode café 📖');
    assert.equal((await client.check(path)).ok, true);
    await assert.rejects(client.replay(path, { sha256: 'bad' }));
    const recorded = await client.recordContext('Unicode', 'answer-1');
    assert.ok(recorded.recording.run_id);
    assert.equal((await client.listRuns()).length, 1);
    assert.equal((await client.replayRun(recorded.recording.run_id)).excerpts[0].quote, 'Unicode café 📖');
    assert.equal((await client.checkRun(recorded.recording.run_id)).ok, true);
  } finally { await rm(home, { recursive: true, force: true }); }
});
