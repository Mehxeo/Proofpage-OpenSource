"""Additive, transactional schema migrations for existing local workspaces."""

MIGRATIONS = [
    (1, [
        "CREATE TABLE import_profiles(id TEXT PRIMARY KEY,name TEXT NOT NULL,provider TEXT NOT NULL,account TEXT NOT NULL,adapter TEXT NOT NULL,mapping TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,UNIQUE(provider,account))",
        "CREATE TABLE watches(id TEXT PRIMARY KEY,profile_id TEXT NOT NULL,directory TEXT NOT NULL,categories TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,state TEXT NOT NULL DEFAULT 'ready',detail TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,UNIQUE(profile_id,directory))",
        "CREATE TABLE watch_files(watch_id TEXT NOT NULL,path TEXT NOT NULL,signature TEXT NOT NULL,first_seen REAL NOT NULL,content_hash TEXT,state TEXT NOT NULL DEFAULT 'settling',detail TEXT NOT NULL DEFAULT '',PRIMARY KEY(watch_id,path))",
        "CREATE TABLE watch_leases(watch_id TEXT PRIMARY KEY,owner TEXT NOT NULL,expires REAL NOT NULL)",
        "CREATE TABLE observations(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,run_id TEXT NOT NULL,state TEXT NOT NULL,observed_at TEXT NOT NULL,detail TEXT NOT NULL)",
    ]),
    (2, [
        "CREATE TABLE run_targets(run_id TEXT PRIMARY KEY,url TEXT NOT NULL)",
        "CREATE TABLE candidates(id TEXT PRIMARY KEY,revision_id TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,citations TEXT NOT NULL,origin TEXT NOT NULL,notes TEXT NOT NULL,mapping TEXT NOT NULL,findings TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'draft',hash TEXT NOT NULL,created_at TEXT NOT NULL,parent_id TEXT)",
        "CREATE TABLE dataset_manifests(dataset_id TEXT PRIMARY KEY,format TEXT NOT NULL,manifest TEXT NOT NULL,candidate_ids TEXT NOT NULL)",
        "CREATE TABLE crawl_jobs(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,state TEXT NOT NULL,options TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,next_attempt REAL NOT NULL DEFAULT 0,owner INTEGER,lease_until REAL NOT NULL DEFAULT 0,detail TEXT NOT NULL DEFAULT '')",
        "CREATE TABLE crawl_pages(job_id TEXT NOT NULL,url TEXT NOT NULL,depth INTEGER NOT NULL,state TEXT NOT NULL DEFAULT 'queued',run_id TEXT,detail TEXT NOT NULL DEFAULT '',PRIMARY KEY(job_id,url))",
        "CREATE TABLE model_events(id TEXT PRIMARY KEY,revision_id TEXT,model TEXT NOT NULL,purpose TEXT NOT NULL,state TEXT NOT NULL,detail TEXT NOT NULL,created_at TEXT NOT NULL)",
        "CREATE TABLE extraction_recipes(id TEXT PRIMARY KEY,name TEXT NOT NULL,fields TEXT NOT NULL,created_at TEXT NOT NULL)",
        "CREATE TABLE extractions(id TEXT PRIMARY KEY,recipe_id TEXT NOT NULL,revision_id TEXT NOT NULL,result TEXT NOT NULL,origin TEXT NOT NULL,created_at TEXT NOT NULL)",
    ]),
]


def migrate(db):
    db.execute('BEGIN IMMEDIATE')
    db.execute('CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY)')
    for version, statements in MIGRATIONS:
        if db.execute('SELECT 1 FROM schema_versions WHERE version=?', (version,)).fetchone():
            continue
        for statement in statements:
            db.execute(statement)
        db.execute('INSERT INTO schema_versions VALUES(?)', (version,))
