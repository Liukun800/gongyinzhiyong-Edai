import copy
import unittest

from experiments.run_development import load_data, feature_text, grouped_baseline


class ExperimentIntegrityTests(unittest.TestCase):
    def test_label_evidence_and_manifest_integrity(self):
        cases,labels,manifest=load_data()
        self.assertEqual(len(cases),24)
        self.assertEqual(len(labels),24)
        self.assertEqual(manifest['version'],'dev-v1')

    def test_label_and_case_identifiers_cannot_become_features(self):
        cases,_,_=load_data()
        original=cases[0]
        edited=copy.deepcopy(original)
        edited.update(id='SECRET-LABEL-ID',answer='秘密标签',family='秘密模板族')
        edited['documents'][0].update(expected='秘密答案',title='标签不能来自标题')
        self.assertEqual(feature_text(original),feature_text(edited))

    def test_family_validation_has_no_training_overlap(self):
        cases,labels,_=load_data()
        rows,folds=grouped_baseline(cases,labels)
        self.assertEqual(len(rows),24)
        self.assertEqual(len({r['case_id'] for r in rows}),24)
        for fold in folds:
            self.assertFalse(set(fold['train_ids'])&set(fold['validation_ids']))
            self.assertTrue(all(labels[key]['family']!=fold['validation_family'] for key in fold['train_ids']))


if __name__=='__main__':unittest.main(verbosity=2)
