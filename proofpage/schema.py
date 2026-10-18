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
    (3, [
        # One row per page fetch. Revision hashes stay unchanged; transport provenance lives here.
        "CREATE TABLE captures(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,source_id TEXT NOT NULL,url TEXT NOT NULL,final_url TEXT NOT NULL,requested_at TEXT NOT NULL,status INTEGER,headers TEXT NOT NULL,body_sha256 TEXT NOT NULL,body_bytes INTEGER NOT NULL,raw_exact INTEGER NOT NULL,peer_ip TEXT,tls TEXT NOT NULL DEFAULT '{}',redirects TEXT NOT NULL DEFAULT '[]',revision_id TEXT,robots_sha256 TEXT)",
        "CREATE INDEX captures_revision ON captures(revision_id)",
        "CREATE INDEX captures_url ON captures(final_url,requested_at)",
        "CREATE TABLE capture_payloads(sha256 TEXT PRIMARY KEY,data BLOB NOT NULL)",
        "CREATE TABLE policy_documents(id TEXT PRIMARY KEY,origin TEXT NOT NULL,kind TEXT NOT NULL,url TEXT NOT NULL,fetched_at TEXT NOT NULL,status INTEGER,sha256 TEXT,body TEXT NOT NULL DEFAULT '',detail TEXT NOT NULL DEFAULT '')",
        "CREATE INDEX policy_documents_lookup ON policy_documents(origin,kind,fetched_at)",
        "CREATE TABLE rights_observations(id TEXT PRIMARY KEY,capture_id TEXT NOT NULL,source_id TEXT NOT NULL,origin TEXT NOT NULL,url TEXT NOT NULL,observed_at TEXT NOT NULL,verdict TEXT NOT NULL,signals TEXT NOT NULL,checked TEXT NOT NULL,hash TEXT NOT NULL)",
        "CREATE INDEX rights_url ON rights_observations(url,observed_at)",
        "CREATE TABLE inbox(id TEXT PRIMARY KEY,kind TEXT NOT NULL,subject_id TEXT NOT NULL,created_at TEXT NOT NULL,detail TEXT NOT NULL,seen INTEGER NOT NULL DEFAULT 0)",
        "CREATE TABLE dataset_rights(dataset_id TEXT NOT NULL,revision_id TEXT NOT NULL,verdict TEXT NOT NULL,basis TEXT,drifted INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(dataset_id,revision_id))",
        "ALTER TABLE reviews ADD COLUMN rights_basis TEXT",
        "ALTER TABLE reviews ADD COLUMN rights_note TEXT NOT NULL DEFAULT ''",
    ]),
    (4, [
        # Signed, hash-chained receipts. The key lives in the database so backups and hosted exports keep proofs verifiable.
        "CREATE TABLE signing_keys(id TEXT PRIMARY KEY,algorithm TEXT NOT NULL,public_key TEXT NOT NULL,private_key TEXT NOT NULL,created_at TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1)",
        "CREATE TABLE receipts(seq INTEGER PRIMARY KEY,id TEXT NOT NULL UNIQUE,capture_id TEXT NOT NULL,key_id TEXT NOT NULL,body TEXT NOT NULL,hash TEXT NOT NULL UNIQUE,prev_hash TEXT,signature TEXT NOT NULL,created_at TEXT NOT NULL,anchor_id TEXT)",
        "CREATE INDEX receipts_capture ON receipts(capture_id)",
        "CREATE INDEX receipts_anchor ON receipts(anchor_id)",
        "CREATE TABLE anchors(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,first_seq INTEGER NOT NULL,last_seq INTEGER NOT NULL,root TEXT NOT NULL,imprint TEXT NOT NULL,tsa_url TEXT,tsa_token BLOB,tsa_time TEXT,tsa_state TEXT NOT NULL DEFAULT 'off',tsa_detail TEXT NOT NULL DEFAULT '',ots_calendar TEXT,ots_proof BLOB,ots_state TEXT NOT NULL DEFAULT 'off',ots_detail TEXT NOT NULL DEFAULT '')",
        "CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)",
        "ALTER TABLE captures ADD COLUMN http_version TEXT",
        "ALTER TABLE captures ADD COLUMN reason TEXT",
    ]),
    (5, [
        "CREATE TABLE claim_checks(id TEXT PRIMARY KEY,text TEXT NOT NULL,created_at TEXT NOT NULL,state TEXT NOT NULL,collect_missing INTEGER NOT NULL,max_age INTEGER NOT NULL,next_attempt REAL NOT NULL DEFAULT 0,lease_until REAL NOT NULL DEFAULT 0,detail TEXT NOT NULL DEFAULT '')",
        "CREATE TABLE claim_items(job_id TEXT NOT NULL,position INTEGER NOT NULL,url TEXT,quote TEXT NOT NULL,start INTEGER,end INTEGER,result TEXT,state TEXT NOT NULL DEFAULT 'queued',PRIMARY KEY(job_id,position))",
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
