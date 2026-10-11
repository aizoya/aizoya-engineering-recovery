import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harness import new_mission,add_session,add_attempt,recovery_context,render,end_session,AtlasStore,record_plan,metrics
from verifier import validate_source,verify

def failure():
    return {'candidate_hash':'a'*64,'verifier_hash':'b'*64,'passed':False,'checks':[{'name':'exact_cents','passed':False,'expected':29,'observed':28}], 'failure':None,'elapsed_ms':1}

    

class HarnessChecks(unittest.TestCase):
    def test_failure_evidence_changes_next_session_plan(self):
        doc=add_session(new_mission('test'),'session1')
        doc,_=add_attempt(doc,'session1',failure())
        restored=copy.deepcopy(doc)
        restored=add_session(restored,'session2')
        self.assertEqual(restored['sessions'][-1]['context']['retrieved_evidence'][0]['failed_checks'],['exact_cents'])
        self.assertNotEqual(restored['sessions'][0]['context']['plan'],restored['sessions'][1]['context']['plan'])
        self.assertEqual(restored['lessons'][0]['source_attempt'],restored['attempts'][0]['id'])

    def test_replayed_attempt_is_noop(self):
        doc=add_session(new_mission('test'),'session1')
        once,_=add_attempt(doc,'session1',failure())
        twice,changed=add_attempt(once,'session1',failure())
        self.assertFalse(changed);self.assertEqual(once,twice)

    def test_replayed_session_is_noop(self):
        doc=add_session(new_mission('test'),'session1')
        self.assertEqual(doc,add_session(doc,'session1'))

    def test_changed_verifier_requires_new_attempt(self):
        doc=add_session(new_mission('test'),'session1')
        doc,_=add_attempt(doc,'session1',failure())
        new=failure();new['verifier_hash']='c'*64
        doc,changed=add_attempt(doc,'session1',new)
        self.assertTrue(changed);self.assertEqual(len(doc['attempts']),2)

    def test_memory_disabled_context_does_not_recall(self):
        doc=add_session(new_mission('test'),'session1')
        doc,_=add_attempt(doc,'session1',failure())
        context=recovery_context(doc,False)
        self.assertEqual(context['retrieved_evidence'],[]);self.assertEqual(context['lessons'],[])

    def test_session_binding(self):
        with self.assertRaises(ValueError):add_attempt(new_mission('test'),'unknown',failure())

    def test_private_attributes_and_imports_rejected(self):
        for code in ['import os','import json\nx=json.__dict__','x=open("secret")']:
            with self.assertRaises(ValueError):validate_source(code)

    def test_real_invalid_execution_is_not_success(self):
        # Unit-test fixture, not a hackathon agent attempt.
        result=verify('def import_transactions(text):\n    return None\n')
        self.assertFalse(result['passed']);self.assertTrue(result['checks'])

    def test_secret_environment_not_inherited(self):
        import os,subprocess
        from unittest.mock import patch
        captured=[]
        real_run=subprocess.run
        def inspect_run(*args,**kwargs):
            captured.append(kwargs['env'])
            return real_run(*args,**kwargs)
        with patch.dict(os.environ,{'MONGODB_URI':'CANARY_NOT_A_REAL_SECRET'}),patch('verifier.subprocess.run',side_effect=inspect_run):
            verify('def import_transactions(text):\n    return None\n')
        self.assertTrue(captured)
        self.assertTrue(all('MONGODB_URI' not in env and 'CANARY_NOT_A_REAL_SECRET' not in env.values() for env in captured))

    def test_closed_session_rejects_new_attempt(self):
        doc=end_session(add_session(new_mission('test'),'session1'),'session1')
        self.assertEqual(doc,end_session(doc,'session1'))
        with self.assertRaises(ValueError):add_attempt(doc,'session1',failure())

    def test_recovery_contains_actual_failure_values(self):
        doc=add_session(new_mission('test'),'session1')
        doc,_=add_attempt(doc,'session1',failure())
        context=recovery_context(doc)
        self.assertEqual(context['retrieved_evidence'][0]['check_evidence'][0]['observed'],28)
        self.assertIn('physical LF',context['contract'])

    def test_stale_revision_does_not_report_success(self):
        from unittest.mock import Mock
        store=AtlasStore.__new__(AtlasStore);store.collection=Mock()
        store.collection.replace_one.return_value.modified_count=0
        doc=new_mission('test')
        with self.assertRaises(ValueError):store.save(doc,add_session(doc,'session1'))
        store.collection.find_one.assert_not_called()

    def test_uncertain_write_readback_does_not_report_success(self):
        from unittest.mock import Mock
        store=AtlasStore.__new__(AtlasStore);store.collection=Mock()
        store.collection.replace_one.return_value.modified_count=1
        doc=new_mission('test');store.collection.find_one.return_value=doc
        with self.assertRaises(ValueError):store.save(doc,add_session(doc,'session1'))

    def test_ui_escapes_script_termination(self):
        doc=new_mission('test');doc['goal']='</script><img src=x onerror=alert(1)>'
        self.assertNotIn(doc['goal'],render(doc))

    def test_decision_provenance_and_replay(self):
        doc=add_session(new_mission('test'),'session1')
        doc,_=add_attempt(doc,'session1',failure())
        doc=add_session(end_session(doc,'session1'),'session2')
        updated=record_plan(doc,'session2','Inspect rounding against exact cents evidence.')
        self.assertEqual(updated,record_plan(updated,'session2','Inspect rounding against exact cents evidence.'))
        self.assertEqual(updated['sessions'][-1]['decisions'][0]['source_attempts'],[doc['attempts'][0]['id']])
        with self.assertRaises(ValueError):record_plan(doc,'session1','closed')

    def test_metrics_do_not_claim_unobserved_model_recovery(self):
        doc=add_session(new_mission('test'),'session1')
        doc,_=add_attempt(doc,'session1',failure())
        changed=failure();changed['candidate_hash']='d'*64
        doc,_=add_attempt(doc,'session1',changed)
        summary=metrics(doc)
        self.assertEqual(summary['repeated_failed_checks'],1)
        self.assertEqual(summary['harness_tool_calls'],2)
        self.assertIsNone(summary['model_tool_calls'])
        self.assertEqual(summary['model_session_freshness'],'not instrumented')

if __name__=='__main__':unittest.main()
