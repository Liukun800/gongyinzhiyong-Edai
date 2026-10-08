from collections import Counter
import json
import unittest

from engine import ANSWERS
from experiments.prepare_domain_adaptation import build_bundle
from shadow_engine import model_state, task_documents
from vendor.agentjev.contract import prepare


class DomainDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=build_bundle()

    def test_three_labels_share_each_anchor(self):
        cases,labels,*_=self.bundle
        self.assertEqual(len(cases),30)
        by_id={c['id']:c for c in cases}
        for family in {a['family'] for a in labels}:
            group=[a for a in labels if a['family']==family]
            self.assertEqual(Counter(a['answer'] for a in group),Counter(ANSWERS[group[0]['task_id']]))
            anchors=[by_id[a['id']]['documents'][0] for a in group]
            self.assertTrue(all(anchor==anchors[0] for anchor in anchors))

    def test_all_parent_descendants_remain_in_same_fold(self):
        _,_,cases,labels,_,_,folds=self.bundle
        lookup={a['id']:a for a in labels}
        for a in labels:
            for parent in a['parent_ids']:
                if parent in lookup:
                    self.assertEqual(a['lineage_group'],lookup[parent]['lineage_group'])
        for fold in folds:
            train=set(fold['train_ids']);validation=set(fold['validation_ids'])
            self.assertFalse(train&validation)
            self.assertFalse({lookup[k]['lineage_group'] for k in train}&{lookup[k]['lineage_group'] for k in validation})
            self.assertEqual({lookup[k]['answer'] for k in train},set(ANSWERS[fold['task_id']]))

    def test_target_separated_from_semantic_input(self):
        _,_,cases,labels,records,_,_=self.bundle
        self.assertEqual(len(records),54)
        by_id={c['id']:c for c in cases}
        by_label={a['id']:a for a in labels}
        for r in records:
            c=by_id[r['record_id']]
            self.assertEqual(set(r['request']),{'state','questions'})
            self.assertEqual(r['request']['state'],model_state(task_documents(c,c['task_id'])))
            self.assertEqual(r['request']['questions'][0]['options'][r['target']['candidate_index']],by_label[c['id']]['answer'])
            prepare(r['request'])

    def test_evidence_and_no_duplicate_input(self):
        _,_,cases,labels,_,_,_=self.bundle
        seen=set(); lookup={a['id']:a for a in labels}
        for c in cases:
            key=(c['task_id'],json.dumps(model_state(task_documents(c,c['task_id'])),ensure_ascii=False,sort_keys=True))
            self.assertNotIn(key,seen)
            seen.add(key)
            for e in lookup[c['id']]['evidence']:
                self.assertTrue(any(d['id']==e['document_id'] and any(p['id']==e['paragraph_id'] and p['text']==e['quote'] for p in d['paragraphs']) for d in c['documents']))


if __name__=='__main__':unittest.main(verbosity=2)
