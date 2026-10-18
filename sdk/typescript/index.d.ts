export interface Options { revisions?: string[]; dependencies?: string; sha256?: string; signal?: AbortSignal }
export interface Dependency { output_id: string; revision_id: string; start: number; end: number; quote: string }
export interface Manifest { schema: 'proofpage.evidence/v1'; name: string; sha256: string; records: Array<{ revision_id: string; text: string; text_sha256: string; original: { representation: string; base64: string; sha256: string } }>; dependencies: Dependency[] }
export interface Comparison { ok: boolean; scope: string; records: Array<{ revision_id: string; state: 'missing' | 'unchanged' | 'changed'; affected_outputs: string[]; quotes: Array<{output_id: string; quote: string; present_in_current: boolean}> }> }
export class ProofpageError extends Error { code: string | number; report?: unknown }
export class Proofpage {
  constructor(options?: { python?: string; home?: string; timeoutMs?: number });
  recordContext(query: string, outputId: string, name?: string): Promise<{recording: {run_id: string; sha256: string} | null; excerpts: unknown[]}>;
  listRuns(): Promise<Array<{id: string; name: string; created_at: string; sha256: string}>>;
  replayRun(id: string): Promise<{run_id: string; sha256: string; excerpts: Dependency[]}>;
  checkRun(id: string): Promise<Comparison>;
  affectedOutputs(id: string): Promise<{item_id: string; affected_outputs: unknown[]}>;
  exportRun(id: string, output: string): Promise<{sha256: string}>;
  record(path: string, options: Options): Promise<{path: string; sha256: string}>;
  replay(path: string, options?: Options): Promise<Manifest>;
  check(path: string, options?: Options): Promise<Comparison>;
  refresh(path: string, options?: Options): Promise<{refresh: unknown[]; comparison: Comparison}>;
}
