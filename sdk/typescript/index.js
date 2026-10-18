import { spawn } from 'node:child_process';

export class ProofpageError extends Error {
  constructor(message, code, report) { super(message); this.name = 'ProofpageError'; this.code = code; this.report = report; }
}
/** Local CLI bridge. Python must have this repository's Proofpage installed. */
export class Proofpage {
  constructor({ python = 'python3', home, timeoutMs = 30000 } = {}) {
    this.python = python; this.home = home; this.timeoutMs = timeoutMs;
  }
  async run(operation, path, { revisions = [], dependencies, sha256, signal, commandGroup = 'evidence', query, outputId, name, output } = {}) {
    const args = ['-m', 'proofpage'];
    if (this.home) args.push('--home', this.home);
    args.push(commandGroup, operation);
    if (path !== undefined) args.push(path);
    for (const [flag, value] of [['--query', query], ['--output-id', outputId], ['--name', name], ['--output', output]]) {
      if (value !== undefined) args.push(flag, value);
    }
    for (const revision of revisions) args.push('--revision', revision);
    if (dependencies) args.push('--dependencies', dependencies);
    if (sha256) args.push('--sha256', sha256);
    return new Promise((resolve, reject) => {
      const child = spawn(this.python, args, { shell: false, signal });
      child.stdout.setEncoding('utf8'); child.stderr.setEncoding('utf8');
      let stdout = '', stderr = '', size = 0;
      const timer = setTimeout(() => { child.kill(); reject(new ProofpageError('Proofpage timed out', 'TIMEOUT')); }, this.timeoutMs);
      child.stdout.on('data', data => {
        size += data.length;
        if (size > 96 * 1024 * 1024) { child.kill(); reject(new ProofpageError('Output limit exceeded', 'LIMIT')); }
        else stdout += data;
      });
      child.stderr.on('data', data => { if (stderr.length < 8192) stderr += data; });
      child.on('error', error => { clearTimeout(timer); reject(error); });
      child.on('close', code => {
        clearTimeout(timer);
        try {
          const report = JSON.parse(stdout);
          if (code === 0 || (code === 1 && ['check', 'refresh'].includes(operation))) resolve(report);
          else reject(new ProofpageError(report.error || stderr || 'Proofpage failed', code, report));
        } catch (error) { reject(new ProofpageError(stderr || error.message, code)); }
      });
    });
  }
  recordContext(query, outputId, name = outputId) { return this.run('record-context', undefined, { commandGroup: 'evidence-run', query, outputId, name }); }
  listRuns() { return this.run('list', undefined, { commandGroup: 'evidence-run' }); }
  replayRun(id) { return this.run('replay', id, { commandGroup: 'evidence-run' }); }
  checkRun(id) { return this.run('check', id, { commandGroup: 'evidence-run' }); }
  affectedOutputs(id) { return this.run('affected', id, { commandGroup: 'evidence-run' }); }
  exportRun(id, output) { return this.run('export', id, { commandGroup: 'evidence-run', output }); }
  record(path, options) { return this.run('record', path, options); }
  replay(path, options) { return this.run('replay', path, options); }
  check(path, options) { return this.run('check', path, options); }
  refresh(path, options) { return this.run('refresh', path, options); }
}
