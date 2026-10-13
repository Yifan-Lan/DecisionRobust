"""Regression checks for metric semantics and the manual admission gate."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import validate_submission as v


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.data=self.root/'website/data';(self.data/'samples').mkdir(parents=True)
        self.folder=self.root/'submissions/entries/test-model';self.folder.mkdir(parents=True)
        self.release={'version':'1.2.0','data_revision':'a','results_revision':'b'}
        self.config='text_injection_curated'
        records=[
            {'id':1,'gt':'a','task':{'mode':'choice','question_ids':['q']},'q':{'type':'choice','criteria':{'a':'Alpha','b':'Beta','c':'Gamma'}}},
            {'id':2,'gt':'a','task':{'mode':'noul','question_ids':['qa','qb'],'labels':['a','b']},'q':{'type':'noul'}},
            {'id':3,'gt':0,'task':{'mode':'score','question_ids':['q']},'q':{'type':'score','criteria':['low','medium','high']}}]
        self.rows=[]
        for rec in records:
            q=rec.pop('q');qs={name:copy.deepcopy(q) for name in rec['task']['question_ids']};qs['unscored']={'type':'noul','instructions':'No GT; retain this question'}
            rec['clean']={'state':'clean','questions':qs};rec['adv']={'state':'adv','questions':qs}
            self.write(self.data/'samples'/f'{rec["id"]}.json',rec)
            outputs={1:({'q':{'choice':'a'}},{'q':{'choice':'b'}}),2:({'qa':{'noul':.4},'qb':{'noul':.2}},{'qa':{'noul':.1},'qb':{'noul':.9}}),3:({'q':{'score':0}},{'q':{'score':1.7,'probabilities':{'0':0,'1':.3,'2':.7}}})}[rec['id']]
            self.rows.append({'config':self.config,'id':rec['id'],**{s:{'request_sha256':v.canonical_hash(rec[s]),'status':'ok','answers':a} for s,a in zip(['clean','adv'],outputs)}})
        self.write(self.data/'index.json',[{'config':self.config,'id':i} for i in [1,2,3]])
        self.write(self.data/'leaderboard.json',{'release':self.release,'suites':{self.config:['Injection','']},'injection_targets':{f'{self.config}:{i}':{'target':t} for i,t in [(1,'b'),(2,'b'),(3,2)]}})
        self.manifest={'schema_version':1,'release':self.release,'model':{'id':'test-model','name':'Test model','revision':'frozen','url':'https://example.com/model','adapter':'native','inference_settings':'deterministic','training_data_disclosure':'not used'},'evaluation_code_url':'https://example.com/code/commit','submitter':'test','configs':[self.config],'complete_requests_preserved':True}
        self.write(self.folder/'manifest.json',self.manifest);self.save_rows()

    def write(self,path,obj):path.write_text(json.dumps(obj)+'\n')
    def save_rows(self):
        (self.folder/'predictions.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in self.rows))
    def check(self):return v.validate_submission(self.folder,self.data)

    def test_all_types_and_score_weighting(self):
        r=self.check()['metrics'][0];self.assertEqual((r['denominator'],r['successes']), (3,3))
        self.rows[2]['adv']['answers']['q']['score']=2;self.save_rows()
        with self.assertRaisesRegex(ValueError,'weighted'):self.check()

    def test_wrong_label_is_not_always_target_hit(self):
        self.rows[0]['adv']['answers']['q']['choice']='c';self.save_rows()
        r=self.check()['metrics'][0];self.assertEqual((r['flip_successes'],r['target_successes']),(3,2))

    def test_clean_wrong_and_errors_do_not_enter_denominator(self):
        self.rows[0]['clean']['answers']['q']['choice']='b'
        self.rows[1]['adv'].update(status='error',reason='timeout');self.save_rows()
        r=self.check()['metrics'][0];self.assertEqual((r['valid_pairs'],r['excluded_pairs'],r['denominator'],r['successes']),(2,1,1,1))

    def test_missing_duplicate_and_wrong_release_rejected(self):
        old=copy.deepcopy(self.rows)
        self.rows.pop();self.save_rows()
        with self.assertRaisesRegex(ValueError,'Missing'):self.check()
        self.rows=old+[old[0]];self.save_rows()
        with self.assertRaisesRegex(ValueError,'duplicate'):self.check()
        self.rows=old;self.save_rows();self.manifest['release']['data_revision']='other';self.write(self.folder/'manifest.json',self.manifest)
        with self.assertRaisesRegex(ValueError,'revision mismatch'):self.check()

    def test_bad_probabilities_pending_and_request_mismatch(self):
        original=copy.deepcopy(self.rows)
        for mutate,pattern in [
            (lambda:self.rows[1]['adv']['answers']['qa'].update(noul=1.2),'Noul'),
            (lambda:self.rows[0]['clean'].update(status='pending'),'status'),
            (lambda:self.rows[0]['clean'].update(request_sha256='incorrect'),'hash mismatch')]:
            self.rows=copy.deepcopy(original);mutate();self.save_rows()
            with self.assertRaisesRegex(ValueError,pattern):self.check()

    def test_strict_json(self):
        for raw in ['{"x":1,"x":2}','{"x":NaN}']:
            with self.assertRaises(ValueError):v.parse_json(raw)

    def test_pending_ignored_and_exact_hash_approval_required(self):
        results={self.config:[]};details={};self.write(self.root/'submissions/approved.json',{'submissions':[]})
        with patch.object(v,'ROOT',self.root):
            v.merge_approved(results,details,self.data);self.assertEqual(results[self.config],[])
            review={'submission':'test-model','reviewer':'Yifan-Lan','reviewed_at':'2026-10-13','verification':'receipt_review','review_url':'https://github.com/Yifan-Lan/DecisionRobust/issues/1','files_sha256':self.check()['files_sha256']}
            self.write(self.root/'submissions/approved.json',{'submissions':[review]})
            v.merge_approved(results,details,self.data);self.assertEqual(len(results[self.config]),1)
            self.assertEqual(details['test-model']['review']['verification'],'receipt_review')
            self.rows[0]['adv']['answers']['q']['choice']='a';self.save_rows()
            with self.assertRaisesRegex(ValueError,'changed'):v.merge_approved({self.config:[]},{},self.data)


if __name__=='__main__':unittest.main()
