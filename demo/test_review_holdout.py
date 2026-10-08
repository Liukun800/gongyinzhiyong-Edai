import hashlib
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent/'experiments'


class HoldoutIntegrityTests(unittest.TestCase):
    def test_frozen_hashes_and_pending_review_status(self):
        base=ROOT/'review_holdout_v1'
        manifest=json.loads((base/'manifest.json').read_text(encoding='utf-8'))
        for filename,digest in manifest['files'].items():
            self.assertEqual(hashlib.sha256((base/filename).read_bytes()).hexdigest(),digest)
        self.assertFalse(manifest['expert_reviewed'])

    def test_no_exact_input_duplicates_or_label_fields_in_inputs(self):
        cases=json.loads((ROOT/'review_holdout_v1/cases.json').read_text(encoding='utf-8'))
        training=json.loads((ROOT/'domain_dev_v2/combined_cases.json').read_text(encoding='utf-8'))
        def canonical(c):return json.dumps(c['documents'],ensure_ascii=False,sort_keys=True)
        self.assertFalse(set(map(canonical,cases)) & set(map(canonical,training)))
        self.assertEqual(len(set(map(canonical,cases))),len(cases))
        for c in cases:self.assertEqual(set(c),{'id','revision','task_id','documents'})

    def test_reference_ids_match_and_families_not_development_ids(self):
        base=ROOT/'review_holdout_v1'
        cases={c['id']:c for c in json.loads((base/'cases.json').read_text(encoding='utf-8'))}
        labels=json.loads((base/'labels.sealed.json').read_text(encoding='utf-8'))
        self.assertEqual(set(cases),{r['id'] for r in labels})
        for r in labels:
            available={d['id']+':'+p['id'] for d in cases[r['id']]['documents'] for p in d['paragraphs']}
            self.assertTrue(set(r['evidence']) <= available)
            self.assertIsNone(r['reviewer'])


if __name__=='__main__':unittest.main()
