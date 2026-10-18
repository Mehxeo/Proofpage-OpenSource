import json
import tempfile
import unittest
from unittest.mock import patch
from proofpage import claims, mcp, service
from proofpage.core import Store


class QuoteTests(unittest.TestCase):
    def test_extract_markdown_footnotes_and_blockquotes(self):
        text = '“First quote” [source](https://example.com/a).\n\n"Second quote" [1]\n\n> Third quote\nhttps://example.com/c\n\n[1]: https://example.com/b'
        result = claims.extract(text)
        self.assertEqual([r['url'] for r in result['citations']], ['https://example.com/a','https://example.com/b','https://example.com/c'])
        for r in result['citations']: self.assertEqual(text[r['start']:r['end']],r['quote'])
        self.assertIsNone(claims.extract('“No source”\n\nhttps://example.com/')['citations'][0]['url'])

    def test_normalized_offsets_and_changed_numbers(self):
        text = 'Prefix Ｈello\nWORLD — Straße! suffix'
        hit = claims.match('hello world - STRASSE!',text)
        self.assertEqual(hit['status'],'verified')
        self.assertEqual(text[hit['start']:hit['end']], 'Ｈello\nWORLD — Straße!')
        altered = claims.match('The subscription costs $25 per month, billed monthly.', 'The subscription costs $20 per month, billed monthly.')
        self.assertEqual(altered['status'],'close')
        self.assertIsNone(claims.match('cats', 'dogs'))
        combined = claims.match('café', 'Cafe\u0301!')
        self.assertEqual((combined['status'], combined['excerpt']), ('verified', 'Cafe\u0301'))

    def test_limits_and_url_validation(self):
        for value in ('', 'a'*50001):
            with self.assertRaises(ValueError): claims.extract(value)
        for url in ('file:///etc/passwd','https://user:secret@example.com'):
            with self.assertRaises(ValueError): claims.clean_url(url)
        with self.assertRaises(ValueError): claims.validate_citations([{'quote':'x'*2001,'url':None}])


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.store=Store(self.tmp.name)
        self.url='https://example.com/pricing'
        with patch('proofpage.core.validate_url'): self.source=self.store.source('Pricing','web',self.url)
        self.old='The subscription costs $20 per month, billed monthly.'
        self.new='The subscription costs $25 per month, billed monthly.'
        self.save(self.old)

    def tearDown(self): self.tmp.cleanup()

    def save(self,text): self.store.save(self.source['id'],self.url,'document','Pricing',text,text)

    def test_offline_exact_close_drift_and_missing(self):
        with patch('proofpage.core.fetch',side_effect=AssertionError('No network')):
            job=claims.create(self.store,[{'url':self.url,'quote':self.old}])
            self.assertEqual(job['items'][0]['result']['status'],'verified')
            self.save(self.new)
            r=claims.create(self.store,[{'url':self.url,'quote':self.old}])['items'][0]['result']
            self.assertEqual(r['status'],'drifted')
            self.assertEqual(r['match_kind'],'verified')
            results=claims.create(self.store,[{'url':None,'quote':'no citation'},{'url':'https://other.example/','quote':'not captured'}])
            self.assertEqual([i['result']['status'] for i in results['items']],['no_source','not_captured'])

    def test_authorized_collection_lease_cancel_and_restart(self):
        citations=[{'url':self.url,'quote':self.old}]
        with patch.object(self.store,'collect') as collect:
            job=claims.create(self.store,citations,collect_missing=True)
            collect.assert_not_called()
            with self.store.db() as db: db.execute('UPDATE claim_checks SET lease_until=9999999999 WHERE id=?',(job['id'],))
            claims.step(self.store,job['id']); collect.assert_not_called()
            with self.store.db() as db: db.execute('UPDATE claim_checks SET lease_until=0 WHERE id=?',(job['id'],))
            with patch('proofpage.core.validate_url'):
                result=claims.step(self.store,job['id'])
            self.assertEqual(result['state'],'complete'); collect.assert_called_once()
        job=claims.create(self.store,citations,collect_missing=True)
        claims.cancel(self.store,job['id'])
        with patch.object(self.store,'collect') as collect:
            self.assertEqual(claims.step(self.store,job['id'])['state'],'cancelled'); collect.assert_not_called()
        reopened=Store(self.tmp.name)
        self.assertEqual(claims.get(reopened,job['id'])['state'],'cancelled')

    def test_cooldown_then_resume(self):
        job=claims.create(self.store,[{'url':self.url,'quote':self.old}],collect_missing=True)
        with self.store.db() as db: db.execute('INSERT INTO cooldowns VALUES(?,?)',('example.com',9999999999))
        with patch.object(self.store,'collect') as collect:
            result=claims.step(self.store,job['id']); collect.assert_not_called()
        self.assertEqual(result['state'],'queued'); self.assertGreater(result['next_attempt'],0)

    def test_failure_keeps_archived_evidence_and_safe_html(self):
        with self.store.db() as db:
            db.execute("INSERT INTO run_targets VALUES('run',?)",(self.url,))
            db.execute("INSERT INTO observations VALUES('obs',?,'run','failed','2026-10-18T00:00:00+00:00','HTTP 404; unavailable')",(self.source['id'],))
        job=claims.create(self.store,[{'url':self.url,'quote':self.old}],'<script>alert(1)</script>')
        r=job['items'][0]['result']; self.assertEqual(r['status'],'unreachable'); self.assertEqual(r['archived_match'],'verified')
        exported,mime=claims.export(self.store,job['id'],'html')
        self.assertNotIn('<script>',exported); self.assertIn('&lt;script&gt;',exported)
        self.assertEqual(json.loads(claims.export(self.store,job['id'],'json')[0])['id'],job['id'])

    def test_service_and_mcp_schema(self):
        status,preview,_=service.post(self.store,'/api/claim-preview',{'text':f'“{self.old}” {self.url}'})
        self.assertEqual(status,200)
        report=mcp.call(self.store,'proofpage_check_answer',{'text':preview['text']})
        self.assertEqual(report['state'],'complete')
        with self.assertRaises(ValueError): mcp.call(self.store,'proofpage_verify_quotes',{'citations':preview['citations'],'collect_missing':1})
        self.assertEqual(mcp.field_schema('array')['items']['required'],['url','quote'])
        response=service.get(self.store,'/api/claim-checks/'+report['id'],{'format':['html']})
        self.assertIsInstance(response[1],bytes)

    def test_restore_pauses_network_and_model_is_explicit(self):
        from proofpage.backup import backup, restore
        from proofpage.receipts import save_settings, settings
        from pathlib import Path
        job=claims.create(self.store,[{'url':self.url,'quote':self.old}],collect_missing=True)
        save_settings(self.store,{'anchor_tsa_url':'https://tsa.example/','anchor_ots':True})
        path=Path(self.tmp.name)/'backup.sqlite3'; backup(self.store,path)
        restore(path,Path(self.tmp.name)/'restored')
        restored=Store(Path(self.tmp.name)/'restored')
        self.assertEqual(claims.get(restored,job['id'])['state'],'cancelled')
        self.assertEqual(settings(restored)['anchor_tsa_url'],'')
        self.assertEqual(settings(restored)['anchor_ots'],'0')
        report=claims.create(self.store,[{'url':self.url,'quote':self.old}])
        with patch('proofpage.models.configuration',return_value={'configured':True,'model':'test'}), patch('proofpage.models.complete_json',return_value={'assessment':'supported','explanation':'Fixture review'}) as model:
            result=claims.model_review(self.store,report['id'],0)
            model.assert_called_once()
        self.assertEqual(result['items'][0]['result']['status'],'verified')
        self.assertEqual(result['items'][0]['result']['model_review']['status'],'unreviewed')
