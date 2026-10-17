"""Hosted-only identity, sessions and quotas. Local workspaces never consult billing."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PLANS = {'free': {'pages': 100, 'models': 0, 'writes': 2000, 'storage': 100*1024*1024},
         'pro': {'pages': 5000, 'models': 100, 'writes': 50000, 'storage': 1024*1024*1024}}


def hashed(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise ValueError('Use a password between 12 and 256 characters.')
    salt = salt or secrets.token_hex(16)
    derived = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**15, r=8, p=1, maxmem=64*1024*1024).hex()
    return salt + ':' + derived


def password_matches(password, encoded):
    try:
        return hmac.compare_digest(password_hash(password, encoded.split(':')[0]), encoded)
    except (ValueError, TypeError):
        return False


def email_address(email):
    if not isinstance(email, str) or len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        raise ValueError('Enter a valid email address.')
    return email.strip().lower()


class Accounts:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / 'accounts.sqlite3'
        with self.db() as db:
            db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE,password TEXT,recovery TEXT,created REAL,customer TEXT UNIQUE,subscription TEXT,paid_until REAL DEFAULT 0,billing_status TEXT DEFAULT 'none');
            CREATE TABLE IF NOT EXISTS invites(hash TEXT PRIMARY KEY,email TEXT,expires REAL);
            CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,user_id TEXT,csrf TEXT,expires REAL);
            CREATE TABLE IF NOT EXISTS keys(hash TEXT PRIMARY KEY,id TEXT UNIQUE,user_id TEXT,name TEXT,scope TEXT,created REAL,expires REAL);
            CREATE TABLE IF NOT EXISTS usage(user_id TEXT,month TEXT,kind TEXT,amount INTEGER,PRIMARY KEY(user_id,month,kind));
            CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY,window INTEGER,amount INTEGER);
            CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,processed REAL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id TEXT,action TEXT,created REAL);
            CREATE TABLE IF NOT EXISTS host_limits(host TEXT PRIMARY KEY,next_attempt REAL,day TEXT,attempts INTEGER);
            ''')
        os.chmod(self.path, 0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def audit(self, user_id, action):
        with self.db() as db:
            db.execute('INSERT INTO audit(user_id,action,created) VALUES(?,?,?)',(user_id,action,time.time()))

    def rate_limit(self, key, maximum=10, seconds=300):
        window = int(time.time()) // seconds
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM limits WHERE window<?', (window-2,))
            row = db.execute('SELECT * FROM limits WHERE key=?',(key,)).fetchone()
            amount = row['amount'] if row and row['window'] == window else 0
            if amount >= maximum:
                raise ValueError('Too many requests. Try again later.')
            db.execute('INSERT OR REPLACE INTO limits VALUES(?,?,?)',(key,window,amount+1))

    def invite(self, email):
        token = secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('INSERT INTO invites VALUES(?,?,?)',(hashed(token),email_address(email),time.time()+7*86400))
        return token

    def register(self, email, password, invite):
        email = email_address(email)
        encoded = password_hash(password)
        user_id, recovery = uuid.uuid4().hex, secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM invites WHERE hash=? AND email=? AND expires>?',(hashed(invite),email,time.time())).fetchone()
            if not row or db.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone():
                raise ValueError('Invitation is invalid, expired, or already used.')
            db.execute('INSERT INTO users(id,email,password,recovery,created) VALUES(?,?,?,?,?)',(user_id,email,encoded,hashed(recovery),time.time()))
            db.execute('DELETE FROM invites WHERE hash=?',(hashed(invite),))
        self.audit(user_id, 'account.created')
        return user_id, recovery

    def login(self, email, password):
        with self.db() as db:
            row = db.execute('SELECT * FROM users WHERE email=?',(email_address(email),)).fetchone()
        # Constant-cost dummy derivation for unknown accounts.
        encoded = row['password'] if row else '00'*16+':'+'00'*64
        if not password_matches(password, encoded) or not row:
            raise ValueError('Email or password is incorrect.')
        return self.session(row['id'])

    def session(self, user_id):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashed(token),user_id,csrf,time.time()+7*86400))
        return token, csrf

    def authenticate(self, token):
        with self.db() as db:
            row = db.execute('SELECT user_id,csrf FROM sessions WHERE hash=? AND expires>?',(hashed(token),time.time())).fetchone()
        if not row:
            raise PermissionError('Sign in to your hosted workspace.')
        return dict(row)

    def recover(self, email, code, password):
        encoded, recovery = password_hash(password), secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT id,recovery FROM users WHERE email=?',(email_address(email),)).fetchone()
            if not row or not hmac.compare_digest(row['recovery'],hashed(code)):
                raise ValueError('Invalid recovery credentials.')
            db.execute('UPDATE users SET password=?,recovery=? WHERE id=?',(encoded,hashed(recovery),row['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?',(row['id'],))
            db.execute('DELETE FROM keys WHERE user_id=?',(row['id'],))
        self.audit(row['id'], 'account.recovered')
        return recovery

    def user(self, user_id):
        with self.db() as db:
            row = db.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
        if not row:
            raise PermissionError('Account unavailable.')
        return dict(row)

    def plan(self, user_id):
        user = self.user(user_id)
        return 'pro' if user['billing_status'] in ('active','trialing') and user['paid_until'] > time.time() else 'free'

    def consume(self, user_id, kind, amount=1):
        maximum = PLANS[self.plan(user_id)][kind]
        month = datetime.now(timezone.utc).strftime('%Y-%m')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT amount FROM usage WHERE user_id=? AND month=? AND kind=?',(user_id,month,kind)).fetchone()
            used = row['amount'] if row else 0
            if used+amount > maximum:
                raise ValueError(f'Hosted {kind} allowance reached. Upgrade or wait for the next UTC month. Local use has no hosted quota.')
            db.execute('INSERT INTO usage VALUES(?,?,?,?) ON CONFLICT(user_id,month,kind) DO UPDATE SET amount=amount+excluded.amount',(user_id,month,kind,amount))

    def account(self, user_id):
        user = self.user(user_id)
        month = datetime.now(timezone.utc).strftime('%Y-%m')
        with self.db() as db:
            usage = {r['kind']:r['amount'] for r in db.execute('SELECT kind,amount FROM usage WHERE user_id=? AND month=?',(user_id,month))}
            keys = [dict(r) for r in db.execute('SELECT id,name,scope,created,expires FROM keys WHERE user_id=?',(user_id,))]
        return {'email':user['email'],'plan':self.plan(user_id),'billing_status':user['billing_status'],'paid_until':user['paid_until'],
                'limits':PLANS[self.plan(user_id)],'usage':usage,'month':month,'keys':keys}

    def create_key(self, user_id, name, scope):
        if scope not in ('read','collect') or not isinstance(name,str) or not 1 <= len(name.strip()) <= 100:
            raise ValueError('Choose a key name and read or collect scope.')
        value, key_id = 'pp_'+secrets.token_urlsafe(32), uuid.uuid4().hex
        with self.db() as db:
            db.execute('DELETE FROM keys WHERE expires<?',(time.time(),))
            if db.execute('SELECT COUNT(*) FROM keys WHERE user_id=?',(user_id,)).fetchone()[0] >= 10:
                raise ValueError('Revoke an existing key before creating more than ten.')
            db.execute('INSERT INTO keys VALUES(?,?,?,?,?,?,?)',(hashed(value),key_id,user_id,name,scope,time.time(),time.time()+90*86400))
        self.audit(user_id,'key.created')
        return {'id':key_id,'key':value,'scope':scope,'expires_in_days':90}

    def authenticate_key(self, value):
        with self.db() as db:
            row = db.execute('SELECT user_id,scope FROM keys WHERE hash=? AND expires>?',(hashed(value),time.time())).fetchone()
        if not row:
            raise PermissionError('Invalid or expired agent key.')
        return dict(row)

    def reserve_host(self, hostname, user_id=None):
        """Shared host budget across ALL hosted tenants, not one limit per account."""
        day = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        maximum = PLANS[self.plan(user_id)]['pages'] if user_id else None
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM host_limits WHERE host=?',(hostname,)).fetchone()
            if row and row['next_attempt'] > time.time():
                raise ValueError('This host is cooling down across the hosted service.')
            attempts = row['attempts'] if row and row['day'] == day else 0
            if attempts >= 100:
                raise ValueError('Shared hosted daily destination budget reached.')
            if user_id:
                month=day[:7]
                used=db.execute("SELECT amount FROM usage WHERE user_id=? AND month=? AND kind='pages'",(user_id,month)).fetchone()
                if (used['amount'] if used else 0)>=maximum:
                    raise ValueError('Hosted pages allowance reached. Upgrade or wait for the next UTC month.')
                db.execute("INSERT INTO usage VALUES(?,?,'pages',1) ON CONFLICT(user_id,month,kind) DO UPDATE SET amount=amount+1",(user_id,month))
            db.execute('INSERT OR REPLACE INTO host_limits VALUES(?,?,?,?)',(hostname,time.time()+30,day,attempts+1))
