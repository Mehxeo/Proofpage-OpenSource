"""Rights Radar: machine-readable AI-usage signals observed with each capture.

Signals are advisory, and several are drafts or vendor conventions. The verdict is a conservative reading:
an explicit reservation always wins, and "unknown" never means permission. This is not legal advice.
"""
import hashlib
import json
import re
import urllib.parse
import urllib.robotparser
import uuid
from html.parser import HTMLParser

AS_OF = '2026-10'
USES = ('train', 'ai_use', 'search')
RANK = {'reserved': 3, 'conditional': 2, 'allowed': 1, 'unknown': 0}
BASES = {'licensed': 'Licensed from the publisher', 'own_content': 'Your own content', 'public_domain': 'Public domain', 'other': 'Other documented basis'}
STATUS = {
    'content_usage': 'IETF AIPREF draft; the vocabulary may still change',
    'content_signal': 'Cloudflare robots.txt convention',
    'tdmrep': 'TDM Reservation Protocol (W3C community report)',
    'noai': 'Informal noai convention',
    'ai_crawler': 'robots.txt rule naming an AI crawler',
    'rsl': 'Really Simple Licensing directive',
    'license': 'Published license',
}
# Crawler tokens and what their operators document them for, as of AS_OF. Names and purposes change.
AI_CRAWLERS = {
    'GPTBot': ('OpenAI', 'train'), 'OAI-SearchBot': ('OpenAI', 'search'), 'ChatGPT-User': ('OpenAI', 'ai_use'),
    'ClaudeBot': ('Anthropic', 'train'), 'anthropic-ai': ('Anthropic', 'train'), 'Claude-SearchBot': ('Anthropic', 'search'), 'Claude-User': ('Anthropic', 'ai_use'),
    'Google-Extended': ('Google', 'train'), 'Applebot-Extended': ('Apple', 'train'), 'CCBot': ('Common Crawl', 'train'),
    'Bytespider': ('ByteDance', 'train'), 'meta-externalagent': ('Meta', 'train'), 'Amazonbot': ('Amazon', 'train'),
    'cohere-training-data-crawler': ('Cohere', 'train'), 'PerplexityBot': ('Perplexity', 'search'), 'Perplexity-User': ('Perplexity', 'ai_use'),
    'MistralAI-User': ('Mistral AI', 'ai_use'), 'DuckAssistBot': ('DuckDuckGo', 'ai_use'),
}
USE_LABELS = {'train': 'AI training', 'ai_use': 'AI answers and grounding', 'search': 'Search indexing'}
CONTENT_USAGE = {'train-ai': 'train', 'train-genai': 'train', 'ai-use': 'ai_use', 'search': 'search'}
CONTENT_SIGNAL = {'ai-train': 'train', 'ai-input': 'ai_use', 'search': 'search'}
CC = re.compile(r'creativecommons\.org/(?:licenses/(by(?:-nc)?(?:-nd|-sa)?)|publicdomain/(zero|mark))(?:/([\d.]+))?', re.I)


def _flag(value):
    value = value.strip().strip('"').lower()
    return True if value in ('y', 'yes', '1', 'true') else False if value in ('n', 'no', '0', 'false') else None


def preferences(text):
    """Parse `train-ai=n, search=y` dictionaries used by Content-Usage and Content-Signal."""
    result = {}
    for part in re.split(r'[,;\s]+', text.strip()):
        key, sep, value = part.partition('=')
        flag = _flag(value) if sep else None
        if flag is not None:
            result[key.strip().lower()] = flag
    return result


def _matches(pattern, path):
    return re.match('^' + re.escape(pattern).replace(r'\*', '.*').replace(r'\$', '$'), path) is not None


def _signal(family, label, source, raw, effects, note=''):
    return {'family': family, 'label': label, 'source': source, 'raw': raw[:300], 'effects': effects, 'status': STATUS[family], 'note': note}


def _preference_signals(family, mapping, values, source, raw):
    effects = {mapping[key]: 'allowed' if flag else 'reserved' for key, flag in values.items() if key in mapping}
    label = ', '.join(f'{key}={"y" if flag else "n"}' for key, flag in values.items())
    return [_signal(family, ('Content-Usage ' if family == 'content_usage' else 'Content-Signal ') + label, source, raw, effects)] if effects else []


def _license_signal(url, source, raw):
    match = CC.search(url)
    if match and match.group(2):
        name = 'CC0' if match.group(2).lower() == 'zero' else 'Public Domain Mark'
        return _signal('license', name, source, raw, {'train': 'allowed', 'ai_use': 'allowed'}, 'Dedicated to the public domain.')
    if match:
        code = match.group(1).upper()
        conditions = ['attribution'] + (['non-commercial use only'] if '-NC' in code else []) + (['no derivatives'] if '-ND' in code else []) + (['share alike'] if '-SA' in code else [])
        return _signal('license', f'CC {code} {match.group(3) or ""}'.strip(), source, raw, {'train': 'conditional', 'ai_use': 'conditional'}, 'Use is permitted with conditions: ' + ', '.join(conditions) + '.')
    return _signal('license', 'License published', source, raw, {'train': 'conditional'}, 'License terms are published; Proofpage records but does not interpret them.')


def robots_groups(text):
    """Split robots.txt into user-agent groups and global lines, keeping line numbers for evidence."""
    groups, global_lines, current, agent_run = [], [], None, False
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split('#', 1)[0].strip()
        field, sep, value = line.partition(':')
        if not sep:
            continue
        field, value = field.strip().lower(), value.strip()
        if field == 'user-agent':
            if current is None or not agent_run:
                current = {'agents': [], 'lines': []}
                groups.append(current)
            current['agents'].append((number, value.lower()))
            agent_run = True
            continue
        agent_run = False
        entry = (number, field, value, raw.strip())
        (global_lines if field in ('sitemap', 'license') or current is None else current['lines']).append(entry)
    return groups, global_lines


def _robots_signals(text, url):
    path = urllib.parse.urlsplit(url).path or '/'
    groups, global_lines = robots_groups(text)
    applicable = global_lines + [line for group in groups if any(agent in ('*', 'proofpage') for _, agent in group['agents']) for line in group['lines']]
    signals = []
    for field, family, mapping in (('content-usage', 'content_usage', CONTENT_USAGE), ('content-signal', 'content_signal', CONTENT_SIGNAL)):
        rules = []
        for number, name, value, raw in applicable:
            if name != field:
                continue
            first, _, rest = value.partition(' ')
            scope, prefs = (first, rest) if first.startswith('/') else ('/', value)
            if _matches(scope, path):
                rules.append((len(scope), number, prefs, raw))
        if rules:
            longest = max(rule[0] for rule in rules)
            for _, number, prefs, raw in sorted(r for r in rules if r[0] == longest):
                signals += _preference_signals(family, mapping, preferences(prefs), f'robots.txt line {number}', raw)
    for number, name, value, raw in global_lines:
        if name == 'license' and value:
            signals.append(_signal('rsl', 'RSL license', f'robots.txt line {number}', raw, {'train': 'conditional'}, 'Licensing terms are published in RSL; Proofpage records but does not fetch or interpret them.'))
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(text.splitlines())
    for token, (operator, use) in AI_CRAWLERS.items():
        lowered = token.lower()
        named = [number for group in groups for number, agent in group['agents'] if agent == lowered or agent.startswith(lowered + '/')]
        if named and not parser.can_fetch(token, url):
            signals.append(_signal('ai_crawler', f'{token} blocked', f'robots.txt line {named[0]}', f'User-agent: {token} (disallowed for this URL)', {use: 'reserved'},
                                   f'{operator} documents {token} for {USE_LABELS[use].lower()}.'))
    return signals


def _header_signals(headers):
    signals = []
    if headers.get('content-usage'):
        signals += _preference_signals('content_usage', CONTENT_USAGE, preferences(headers['content-usage']), 'HTTP header Content-Usage', 'Content-Usage: ' + headers['content-usage'])
    if headers.get('tdm-reservation', '').strip() in ('0', '1'):
        reserved = headers['tdm-reservation'].strip() == '1'
        policy = headers.get('tdm-policy', '')
        signals.append(_signal('tdmrep', 'TDM reserved' if reserved else 'TDM not reserved', 'HTTP header tdm-reservation', 'tdm-reservation: ' + headers['tdm-reservation'],
                               {'train': 'reserved' if reserved else 'allowed'}, ('Licensing policy: ' + policy) if policy else ''))
    tokens = [token.strip().lower() for token in re.split(r'[,\s]+', headers.get('x-robots-tag', ''))]
    if 'noai' in tokens:
        signals.append(_signal('noai', 'noai', 'HTTP header X-Robots-Tag', 'X-Robots-Tag: ' + headers['x-robots-tag'], {'train': 'reserved'}))
    for match in re.finditer(r'<([^>]+)>\s*;[^,]*rel="?license"?', headers.get('link', ''), re.I):
        signals.append(_license_signal(match.group(1), 'HTTP header Link rel=license', 'Link: <' + match.group(1) + '>; rel="license"'))
    return signals


class _Signals(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.links, self.jsonld, self._script = [], [], [], None

    def handle_starttag(self, tag, attrs):
        a = {key.lower(): value or '' for key, value in attrs}
        line = self.getpos()[0]
        if tag == 'meta' and a.get('name'):
            self.meta.append((a['name'].strip().lower(), a.get('content', ''), line))
        elif tag in ('link', 'a') and 'license' in a.get('rel', '').lower().split() and a.get('href'):
            self.links.append((a['href'], line, tag))
        elif tag == 'script' and a.get('type', '').strip().lower() == 'application/ld+json':
            self._script = []

    def handle_endtag(self, tag):
        if tag == 'script' and self._script is not None:
            self.jsonld.append(''.join(self._script))
            self._script = None

    def handle_data(self, data):
        if self._script is not None:
            self._script.append(data)


def _jsonld_licenses(value, depth=0):
    if depth > 6:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key == 'license':
                for entry in item if isinstance(item, list) else [item]:
                    url = entry if isinstance(entry, str) else entry.get('url') or entry.get('@id') if isinstance(entry, dict) else None
                    if isinstance(url, str):
                        yield url
            else:
                yield from _jsonld_licenses(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            yield from _jsonld_licenses(item, depth + 1)


def _html_signals(html, base):
    parser = _Signals()
    try:
        parser.feed(html)
    except Exception:
        return []
    signals, licenses = [], {}
    meta = {name: (content, line) for name, content, line in parser.meta}
    if 'tdm-reservation' in meta and meta['tdm-reservation'][0].strip() in ('0', '1'):
        content, line = meta['tdm-reservation']
        reserved = content.strip() == '1'
        policy = meta.get('tdm-policy', ('', 0))[0]
        signals.append(_signal('tdmrep', 'TDM reserved' if reserved else 'TDM not reserved', f'HTML meta tdm-reservation (line {line})', f'<meta name="tdm-reservation" content="{content}">',
                               {'train': 'reserved' if reserved else 'allowed'}, ('Licensing policy: ' + policy) if policy else ''))
    for name, content, line in parser.meta:
        tokens = [token.strip().lower() for token in content.split(',')]
        if name == 'robots' and 'noai' in tokens:
            signals.append(_signal('noai', 'noai', f'HTML meta robots (line {line})', f'<meta name="robots" content="{content}">', {'train': 'reserved'}))
        if name in ('license', 'dcterms.license') and content.strip():
            licenses.setdefault(urllib.parse.urljoin(base, content.strip()), (f'HTML meta {name} (line {line})', f'<meta name="{name}" content="{content}">'))
    for href, line, tag in parser.links:
        licenses.setdefault(urllib.parse.urljoin(base, href), (f'HTML {tag} rel=license (line {line})', f'<{tag} rel="license" href="{href}">'))
    for block in parser.jsonld:
        try:
            for url in _jsonld_licenses(json.loads(block)):
                licenses.setdefault(urllib.parse.urljoin(base, url), ('JSON-LD license', f'"license": "{url}"'))
        except ValueError:
            continue
    for url, (source, raw) in licenses.items():
        signals.append(_license_signal(url, source, raw))
    return signals


def _tdmrep_signals(data, path):
    if not isinstance(data, list):
        return []
    for index, rule in enumerate(data, 1):
        location = rule.get('location') if isinstance(rule, dict) else None
        reservation = rule.get('tdm-reservation') if isinstance(rule, dict) else None
        if isinstance(location, str) and reservation in (0, 1) and _matches(location if location.startswith('/') else '/' + location, path):
            policy = rule.get('tdm-policy') or ''
            # The protocol applies the first matching rule.
            return [_signal('tdmrep', 'TDM reserved' if reservation else 'TDM not reserved', f'/.well-known/tdmrep.json rule {index}', json.dumps(rule, sort_keys=True),
                            {'train': 'reserved' if reservation else 'allowed'}, ('Licensing policy: ' + policy) if policy else '')]
    return []


def combine(signals):
    verdict = {}
    for use in USES:
        values = [signal['effects'][use] for signal in signals if use in signal['effects']]
        verdict[use] = max(values, key=RANK.get) if values else 'unknown'
    return verdict


def summarize(verdict, signals):
    def reasons(use, value):
        return '; '.join(sorted({s['label'] for s in signals if s['effects'].get(use) == value}))
    lead = {
        'reserved': 'AI training is reserved by the publisher: ' + reasons('train', 'reserved') + '.',
        'conditional': 'AI training is allowed only under published terms: ' + reasons('train', 'conditional') + '.',
        'allowed': 'AI training is explicitly permitted: ' + reasons('train', 'allowed') + '.',
        'unknown': 'No machine-readable AI-training signal was found. Unknown is not permission.',
    }[verdict['train']]
    extra = [f'{USE_LABELS[use]} reserved ({reasons(use, "reserved")}).' for use in ('ai_use', 'search') if verdict[use] == 'reserved']
    return ' '.join([lead] + extra)


def observe(url, headers=None, html='', robots_text=None, robots_status=None, tdmrep=None):
    """Read every supported signal for one fetched page. Returns verdicts, the exact evidence, and what was checked."""
    path = urllib.parse.urlsplit(url).path or '/'
    signals, checked = [], {}
    if robots_status == 200:
        checked['robots.txt'] = 'read'
        signals += _robots_signals(robots_text or '', url)
    else:
        checked['robots.txt'] = 'not checked' if robots_status is None else 'not published' if robots_status == 404 else f'unavailable (HTTP {robots_status})'
    checked['HTTP headers'] = 'read' if headers is not None else 'not available'
    signals += _header_signals(headers or {})
    if html and '<' in html:
        checked['HTML'] = 'read'
        signals += _html_signals(html, url)
    else:
        checked['HTML'] = 'not HTML'
    tdmrep = tdmrep or {'status': 'not_checked'}
    checked['/.well-known/tdmrep.json'] = {'read': 'read', 'missing': 'not published', 'invalid': 'invalid JSON', 'not_checked': 'not checked'}.get(tdmrep['status'], tdmrep.get('detail') or 'unavailable')
    if tdmrep['status'] == 'read':
        signals += _tdmrep_signals(tdmrep.get('data'), path)
    verdict = combine(signals)
    return {'verdict': verdict, 'signals': signals, 'checked': checked, 'summary': summarize(verdict, signals), 'as_of': AS_OF}


# ---------- Storage ----------

def record(store, db, capture_id, source_id, url, observation, observed_at):
    """Persist an observation and report drift from the previous observation of the same URL."""
    origin = (urllib.parse.urlsplit(url).hostname or '').lower()
    verdict = dict(observation['verdict'], summary=observation['summary'])
    body = json.dumps({'verdict': verdict, 'signals': observation['signals'], 'checked': observation['checked']}, sort_keys=True)
    previous = db.execute('SELECT verdict FROM rights_observations WHERE url=? ORDER BY observed_at DESC, rowid DESC LIMIT 1', (url,)).fetchone()
    observation_id = uuid.uuid4().hex
    db.execute('INSERT INTO rights_observations VALUES(?,?,?,?,?,?,?,?,?,?)', (observation_id, capture_id, source_id, origin, url, observed_at, json.dumps(verdict, sort_keys=True),
                                                                             json.dumps(observation['signals'], sort_keys=True), json.dumps(observation['checked'], sort_keys=True), hashlib.sha256(body.encode()).hexdigest()))
    drift = None
    if previous:
        before = json.loads(previous['verdict'])
        changes = {use: [before.get(use), verdict[use]] for use in USES if before.get(use) != verdict[use]}
        if changes:
            affected = [row[0] for row in db.execute('SELECT DISTINCT dataset_id FROM dataset_rights WHERE revision_id IN (SELECT revision_id FROM captures WHERE final_url=? AND revision_id IS NOT NULL)', (url,))]
            if 'train' in changes:
                db.execute('UPDATE dataset_rights SET drifted=1 WHERE revision_id IN (SELECT revision_id FROM captures WHERE final_url=? AND revision_id IS NOT NULL)', (url,))
            drift = {'url': url, 'source_id': source_id, 'changes': changes, 'summary': verdict['summary'], 'datasets': affected}
            db.execute('INSERT INTO inbox VALUES(?,?,?,?,?,0)', (uuid.uuid4().hex, 'rights_drift', source_id, observed_at, json.dumps(drift, sort_keys=True)))
    return {'id': observation_id, **verdict, 'drift': drift}


def _observation(row):
    if not row:
        return None
    return {'id': row['id'], 'url': row['url'], 'observed_at': row['observed_at'], 'verdict': json.loads(row['verdict']),
            'signals': json.loads(row['signals']), 'checked': json.loads(row['checked']), 'hash': row['hash']}


def revision_rights(store, revision_id):
    """Rights for one revision: what was published when it was captured, what is published now, and the stricter of both."""
    rows = store.rows('SELECT s.kind,r.metadata FROM revisions r JOIN items i ON i.id=r.item_id JOIN sources s ON s.id=i.source_id WHERE r.id=?', (revision_id,))
    if not rows:
        raise ValueError('Revision not found.')
    if rows[0]['kind'] != 'web':
        return {'state': 'user_supplied', **{use: 'user_supplied' for use in USES}, 'drifted': False,
                'summary': 'Supplied by you in an archive or export. No publisher signal applies; confirm your own rights to use it.'}
    first = store.rows('SELECT o.* FROM rights_observations o JOIN captures c ON c.id=o.capture_id WHERE c.revision_id=? ORDER BY o.observed_at ASC, o.rowid ASC LIMIT 1', (revision_id,))
    url = first[0]['url'] if first else json.loads(rows[0]['metadata'] or '{}').get('url')
    latest = store.rows('SELECT * FROM rights_observations WHERE url=? ORDER BY observed_at DESC, rowid DESC LIMIT 1', (url,)) if url else []
    at_capture, current = _observation(first[0] if first else None), _observation(latest[0] if latest else None)
    if not current:
        return {'state': 'not_recorded', **{use: 'not_recorded' for use in USES}, 'drifted': False, 'url': url,
                'summary': 'Captured before Rights Radar recorded publisher signals. Collect the source again to check.'}
    observations = [o for o in (at_capture, current) if o]
    effective = {use: max((o['verdict'][use] for o in observations), key=RANK.get) for use in USES}
    drifted = bool(at_capture and at_capture['verdict'] != current['verdict'])
    summary = current['verdict']['summary'] + (' This changed after the revision was captured.' if drifted else '')
    return {'state': 'observed', **effective, 'drifted': drifted, 'url': url, 'summary': summary, 'at_capture': at_capture, 'current': current}


def check_basis(store, revision_id, basis, note=''):
    """Granting dataset permission for a reserved page requires a recorded basis."""
    if basis and basis not in BASES:
        raise ValueError('Choose a listed rights basis.')
    if basis == 'other' and not (note or '').strip():
        raise ValueError('Describe the other rights basis.')
    info = revision_rights(store, revision_id)
    if info['train'] == 'reserved' and not basis:
        raise ValueError('The publisher reserves AI training for this page. ' + info['summary'] + ' Record your rights basis (a license, your own content, public domain, or another documented basis) to grant dataset permission.')
    return info


def _rows_in(store, sql, ids, before=()):
    """Run `sql` (with one `{marks}` placeholder list) over ids in chunks that stay under SQLite's variable limit."""
    rows = []
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        rows += store.rows(sql.format(marks=','.join('?' * len(chunk))), [*before, *chunk])
    return rows


def export_blockers(store, dataset_id, revision_ids):
    """Revisions whose source now reserves AI training and that have no rights basis recorded, at freeze or since."""
    reserved_urls = {row['url'] for row in store.rows('SELECT DISTINCT url FROM rights_observations WHERE verdict LIKE ?', ('%"train": "reserved"%',))}
    if not revision_ids or not reserved_urls:
        return []
    rows = _rows_in(store, 'SELECT r.id,r.metadata,(SELECT c.final_url FROM captures c WHERE c.revision_id=r.id ORDER BY c.requested_at,c.rowid LIMIT 1) url FROM revisions r WHERE r.id IN ({marks})', revision_ids)
    suspects = sorted(row['id'] for row in rows if (row['url'] or json.loads(row['metadata'] or '{}').get('url')) in reserved_urls)
    if not suspects:
        return []
    with_basis = {row['revision_id'] for row in _rows_in(store, 'SELECT revision_id FROM dataset_rights WHERE dataset_id=? AND basis IS NOT NULL AND revision_id IN ({marks})', suspects, (dataset_id,))}
    with_basis |= {row['revision_id'] for row in _rows_in(store, 'SELECT revision_id FROM reviews WHERE rights_basis IS NOT NULL AND revision_id IN ({marks})', suspects)}
    return [revision_id for revision_id in suspects if revision_id not in with_basis and revision_rights(store, revision_id)['train'] == 'reserved']


def blocked_message(store, blocked):
    titles = [row['title'] for row in _rows_in(store, 'SELECT i.title FROM revisions r JOIN items i ON i.id=r.item_id WHERE r.id IN ({marks}) ORDER BY i.title', blocked[:3])]
    more = f', and {len(blocked) - 3} more' if len(blocked) > 3 else ''
    return (f'Export blocked: {len(blocked)} source revision(s) in this dataset now carry an AI-training reservation without a recorded rights basis '
            f'({"; ".join(titles)}{more}). Open them in the library, review the Rights tab, and record a basis, or freeze a new dataset without them.')


def freeze_snapshot(store, revision_ids):
    """Verdicts at freeze time. Reserved pages without a recorded basis block the freeze."""
    snapshot, blocked = {}, []
    for revision_id in revision_ids:
        info = revision_rights(store, revision_id)
        basis = (store.rows('SELECT rights_basis FROM reviews WHERE revision_id=?', (revision_id,)) or [{}])[0].get('rights_basis')
        if info['train'] == 'reserved' and not basis:
            blocked.append(revision_id)
        snapshot[revision_id] = (info['train'], basis)
    if blocked:
        raise ValueError(f'{len(blocked)} selected revision(s) now carry an AI-training reservation without a recorded rights basis. Open them in the library, review the Rights tab, and record a basis or remove permission.')
    return snapshot


def save_snapshot(db, dataset_id, snapshot):
    for revision_id, (verdict, basis) in sorted(snapshot.items()):
        db.execute('INSERT INTO dataset_rights(dataset_id,revision_id,verdict,basis) VALUES(?,?,?,?)', (dataset_id, revision_id, verdict, basis))


def snapshot_counts(snapshot):
    counts = {}
    for verdict, basis in snapshot.values():
        key = verdict + ('_with_basis' if basis and verdict == 'reserved' else '')
        counts[key] = counts.get(key, 0) + 1
    return counts
