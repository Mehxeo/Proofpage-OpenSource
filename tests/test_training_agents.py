import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

from proofpage.core import Store
from proofpage import training, agent, crawl, models
from proofpage.quality import grouped_splits


class TrainingAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        self.source = self.store.source('Fixture', 'import', 'fixture:training')
        self.store.save(self.source['id'], 'article', 'document', 'Plants', 'Plants use sunlight for photosynthesis. Contact gardener@example.org.', 'fixture')
        self.rev = self.store.search()[0]['current_revision']

    def tearDown(self):
        self.temp.cleanup()

    def candidate(self, **kwargs):
        return training.create_candidate(self.store, self.rev, 'sft', {'messages': [{'role':'user','content':'What do plants use?'},{'role':'assistant','content':'Plants use sunlight.'}]}, 'Plants use sunlight for photosynthesis.', **kwargs)

    def approve(self, candidate):
        self.store.review(self.rev, True, False)
        return training.review_candidate(self.store, candidate['id'], 'approved', True)

    def test_grounding_and_review_are_required(self):
        c = self.candidate()
        with self.assertRaises(ValueError):
            training.review_candidate(self.store, c['id'], 'approved')
        with self.assertRaises(ValueError):
            training.freeze_training(self.store, 'No', [c['id']], 'sft')
        with self.assertRaises(ValueError):
            training.create_candidate(self.store, self.rev, 'evaluation', {'prompt':'Question','reference':'Answer'}, 'Invented quote')
        self.approve(c)
        self.assertEqual(training.get_candidate(self.store,c['id'])['status'],'approved')

    def test_bundle_roundtrip_and_revocation(self):
        c=self.approve(self.candidate())
        d=training.freeze_training(self.store,'Plants',[c['id']],'sft')
        payload=training.export_bundle(self.store,d['id'])
        self.assertEqual(payload,training.export_bundle(self.store,d['id']))
        with tempfile.TemporaryDirectory() as directory:
            with zipfile.ZipFile(io.BytesIO(payload)) as z:
                z.extractall(directory)
            result=subprocess.run([sys.executable,str(Path(directory)/'validate.py')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            Path(directory,'train.jsonl').write_text('tampered')
            self.assertNotEqual(subprocess.run([sys.executable,str(Path(directory)/'validate.py')],capture_output=True).returncode,0)
        training.review_candidate(self.store,c['id'],'revoked')
        with self.assertRaises(ValueError):training.export_bundle(self.store,d['id'])
        self.approve(c)
        self.store.review(self.rev,False,False)
        with self.assertRaises(ValueError):training.export_bundle(self.store,d['id'])

    def test_redaction_and_immutable_edits(self):
        self.store.save(self.source['id'],'secret','document','Secret','password=abcdefgh12345 and gardener@example.org','fixture')
        rev=self.store.rows("SELECT current_revision FROM items WHERE external_id='secret'")[0]['current_revision']
        payload={'prompt':'What is recorded?','completion':'password=abcdefgh12345 and gardener@example.org'}
        c=training.create_candidate(self.store,rev,'correction',payload,'password=abcdefgh12345')
        self.store.review(rev,True,False)
        with self.assertRaises(ValueError):training.review_candidate(self.store,c['id'],'approved',True)
        clean=training.create_candidate(self.store,rev,'correction',payload,'password=abcdefgh12345',redact_sensitive=True,parent_id=c['id'])
        training.review_candidate(self.store,clean['id'],'approved',True)
        self.assertNotIn('abcdefgh',json.dumps(clean['payload']))
        self.assertEqual(training.get_candidate(self.store,c['id'])['status'],'draft')

    def test_warning_acknowledgment(self):
        c=training.create_candidate(self.store,self.rev,'evaluation',{'prompt':'Contact?','reference':'gardener@example.org'},'gardener@example.org')
        self.store.review(self.rev,True,False)
        with self.assertRaises(ValueError):training.review_candidate(self.store,c['id'],'approved')
        training.review_candidate(self.store,c['id'],'approved',True)

    def test_preference_requires_reason_and_difference(self):
        for payload,notes in [({'prompt':'Q','chosen':'A','rejected':'A'},'reason'),({'prompt':'Q','chosen':'A','rejected':'B'},'')]:
            with self.assertRaises(ValueError):training.create_candidate(self.store,self.rev,'preference',payload,'Plants',notes)

    def test_dedup_and_groups(self):
        a=self.approve(self.candidate());b=self.approve(self.candidate())
        self.assertEqual(training.freeze_training(self.store,'Dedup',[a['id'],b['id']],'sft')['records'],1)
        rows=[{'text':' '.join(['word'+str(i) for i in range(100)]),'source_id':'a'},{'text':' '.join(['word'+str(i) for i in range(99)]+['changed']),'source_id':'b'},{'text':'different','source_id':'a'}]
        self.assertEqual(len(set(grouped_splits(rows))),1)

    def test_context_exact_offsets_and_archive_freshness(self):
        result=agent.context(self.store,'sunlight')
        self.assertEqual(len(result['excerpts']),1)
        e=result['excerpts'][0];r=self.store.revision(e['revision_id'])
        self.assertEqual(e['text'],r['text'][e['start']:e['end']])
        self.assertEqual(agent.ensure_fresh(self.store,self.source['id'])['state'],'archive_only')

    def test_trace_must_be_observed(self):
        with self.assertRaises(ValueError):training.create_candidate(self.store,self.rev,'trace',{'events':[{'type':'outcome','text':'invented'}]},'Plants')
        agent.observed_tool(self.store,'proofpage_get_context',{'query':'sunlight'},{'found':True})
        item=self.store.rows("SELECT current_revision FROM items WHERE kind='agent_trace'")[0]
        revision=self.store.revision(item['current_revision']);events=json.loads(revision['metadata'])['observed_events']
        c=training.create_candidate(self.store,item['current_revision'],'trace',{'events':events},revision['text'][:100])
        self.assertEqual(c['payload']['events'],events)
        self.assertEqual(len(agent.context(self.store,'sunlight')['excerpts']),1)

    def test_extraction_schema_and_grounding(self):
        recipe=models.create_recipe(self.store,'Plant fact',{'energy':'Energy source','author':'Named author'})
        values={'energy':{'value':'sunlight','quote':'Plants use sunlight'},'author':{'value':None,'quote':None}}
        self.assertEqual(models.save_extraction(self.store,recipe['id'],self.rev,values)['state'],'unreviewed')
        values['energy']['quote']='invented'
        with self.assertRaises(ValueError):models.save_extraction(self.store,recipe['id'],self.rev,values)

    def test_actual_local_model_http_roundtrip(self):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                received.append((self.path,json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                body=json.dumps({'choices':[{'message':{'content':json.dumps({'question':'What powers photosynthesis?','answer':'Sunlight.','quote':'Plants use sunlight for photosynthesis.'})}}]}).encode()
                self.send_response(200);self.end_headers();self.wfile.write(body)
        server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with patch.dict(os.environ,{'PROOFPAGE_MODEL_URL':f'http://127.0.0.1:{server.server_port}/v1','PROOFPAGE_MODEL_NAME':'test-fixture'}):
                c=models.assist(self.store,self.rev,'sft')
            self.assertEqual(c['status'],'draft');self.assertEqual(received[0][0],'/v1/chat/completions')
            self.assertIn('untrusted',received[0][1]['messages'][0]['content'])
        finally:server.shutdown();server.server_close();thread.join()

    def test_crawl_scope_feed_and_restart(self):
        self.assertFalse(crawl.in_scope('https://example.org/docs/','https://example.org/docs/%2e%2e/private'))
        self.assertFalse(crawl.in_scope('https://example.org/docs/','https://other.org/docs/a'))
        self.assertEqual(crawl.discover('<rss><channel><item><link>https://example.org/docs/a</link></item></channel></rss>','https://example.org/docs/'),['https://example.org/docs/a'])
        with patch('proofpage.core.validate_url'):s=self.store.source('Web','web','https://example.org/docs/')
        job=crawl.create_job(self.store,s['id'],3,1)
        html='<title>Documentation</title><p>'+('Useful source content. '*40)+'</p><a href="a">A</a><a href="b">B</a><a href="https://other.org/">Other</a>'
        with patch('proofpage.core.fetch',side_effect=[(404,{},'',''),(200,{'content-type':'text/html'},html,s['location'])]):
            result=crawl.step_job(self.store,job['id'])
        self.assertEqual(len(result['pages']),3)
        self.assertEqual(agent.ensure_fresh(self.store,s['id'])['state'],'fresh')
        restarted=Store(self.temp.name)
        with patch('proofpage.core.fetch') as fetch:
            crawl.step_job(restarted,job['id']);fetch.assert_not_called()
        crawl.cancel_job(restarted,job['id'])
        self.assertEqual(crawl.step_job(restarted,job['id'])['state'],'cancelled')

    def test_render_failure_not_success(self):
        with patch('proofpage.core.validate_url'):s=self.store.source('Web','web','https://example.org/')
        with patch('proofpage.core.fetch',side_effect=[(404,{},'',''),(200,{'content-type':'text/html'},'<p>'+('Article. '*80)+'</p>',s['location'])]),patch('proofpage.render.render_html',side_effect=ValueError('Chromium unavailable')):
            result=self.store.collect(s['id'],render=True)
        self.assertEqual(result['state'],'failed');self.assertEqual(result['added'],0)
