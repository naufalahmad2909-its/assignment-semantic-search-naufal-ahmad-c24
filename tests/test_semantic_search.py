"""Pengujian offline atas data, FAISS, retrieval dan kontrak jawaban."""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import faiss
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / 'src'))
import semantic_search as app


class SemanticSearchTests(unittest.TestCase):
    def setUp(self):
        self.df,self.info=app.load_knowledge_base()
        self.index=app.load_index(self.df)
        self.queries=json.loads((app.DOC / 'test_queries.json').read_text(encoding='utf-8'))

    def test_units_preserve_question_and_answer_and_raw_hash(self):
        self.assertEqual(len(self.df),59)
        self.assertEqual(len(self.info['categories']),8)
        self.assertTrue(all(row.content == 'Q: '+row.question+'\nA: '+row.answer for row in self.df.itertuples()))
        profile=json.loads((app.DOC / 'knowledge_base_profile.json').read_text(encoding='utf-8'))
        self.assertEqual(profile['raw_sha256'],app.sha(app.DATA.read_bytes()))

    def test_embedding_shape_finite_values_and_index_count(self):
        matrix,meta=app.create_embeddings(self.df)
        self.assertEqual(matrix.shape,(59,768))
        self.assertEqual(matrix.dtype,np.dtype('float32'))
        self.assertTrue(np.isfinite(matrix).all())
        self.assertEqual(len(meta['api_records']),59)
        self.assertTrue(all(r['source']=='real_gemini_embeddings_api' for r in meta['api_records']))
        self.assertEqual((self.index.ntotal,self.index.d),(59,768))
        self.assertEqual(self.index.metric_type,faiss.METRIC_INNER_PRODUCT)
        indexed=self.index.reconstruct_n(0,self.index.ntotal)
        np.testing.assert_allclose(np.linalg.norm(indexed,axis=1),1,atol=1e-5)

    def test_faiss_matches_direct_cosine_computation(self):
        query=self.queries[0]['query']
        result=app.semantic_search(query,self.df,self.index)
        docs=app.normalized(np.load(app.ART / 'document_embeddings.npy',allow_pickle=False))
        q=app.normalized(app.get_query_embedding(query).reshape(1,-1))
        scores=(docs @ q.T).ravel()
        order=np.argsort(-scores)[:3]
        self.assertEqual([r['faq_id'] for r in result],self.df.iloc[order].faq_id.tolist())
        np.testing.assert_allclose([r['cosine_similarity'] for r in result],scores[order],atol=1e-6)

    def test_rebuilt_index_matches_saved_index(self):
        vectors,_=app.create_embeddings(self.df)
        query=app.normalized(app.get_query_embedding(self.queries[0]['query']).reshape(1,-1))
        expected_scores,expected_ids=self.index.search(query,3)
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests',prefix='.tmp-') as directory:
            with patch.object(app,'ART',Path(directory)):
                rebuilt=app.build_index(self.df,vectors)
                loaded=app.load_index(self.df)
                scores,ids=loaded.search(query,3)
                self.assertEqual(rebuilt.ntotal,59)
                np.testing.assert_array_equal(ids,expected_ids)
                np.testing.assert_allclose(scores,expected_scores,atol=1e-6)

    def test_bad_query_and_top_k_are_rejected(self):
        with self.assertRaises(ValueError):
            app.semantic_search('',self.df,self.index)
        for k in [0,60]:
            with self.assertRaises(ValueError):
                app.semantic_search(self.queries[0]['query'],self.df,self.index,top_k=k)

    def test_demo_replays_without_api_key_and_matches_saved_results(self):
        saved=json.loads((app.DOC / 'query_results.json').read_text(encoding='utf-8'))
        with patch.dict(os.environ,{},clear=True):
            for item,expected in zip(self.queries,saved):
                result=app.generate_answer(item['query'],self.df,self.index)
                self.assertEqual(result['answer'],expected['answer'])
                self.assertEqual(result['source_faq_ids'],expected['source_faq_ids'])
                self.assertEqual(len(result['retrieved']),3)
                self.assertTrue(result['response_id'])

    def test_answer_cannot_cite_faq_outside_context(self):
        results=app.semantic_search(self.queries[0]['query'],self.df,self.index)
        with self.assertRaisesRegex(ValueError,'tidak ada pada context'):
            app.validate_answer({'answer':'Jawaban','status':'answered','source_faq_ids':[999]},results)
        with self.assertRaises(ValueError):
            app.validate_answer({'answer':'','status':'answered','source_faq_ids':[17]},results)

    def test_index_integrity_mismatch_is_detected(self):
        manifest=json.loads((app.ART / 'index_manifest.json').read_text(encoding='utf-8'))
        manifest['index_sha256']='incorrect'
        with tempfile.TemporaryDirectory(dir=ROOT / 'tests',prefix='.tmp-') as directory:
            temp=Path(directory)
            (temp/'index_manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            (temp/'faq.index').write_bytes((app.ART/'faq.index').read_bytes())
            with patch.object(app,'ART',temp):
                with self.assertRaisesRegex(ValueError,'Hash index'):
                    app.load_index(self.df)


if __name__=='__main__':
    unittest.main()
