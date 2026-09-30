"""Rebuild only fixed input/output aggregates from pinned vid_pipeline batches.
No source_cache, RAG_finance, Gold, API or semantic decision is accessed.
"""
import json
from audit_structure import ROOT,rows,save,sha

def main():
    dependency=json.loads((ROOT/'DEPENDENCIES.json').read_text())
    repo=ROOT.parents[2]
    for kind in ['inputs','outputs']:
        records=[]
        for item in dependency['fixed_batch_files']:
            if item['kind']!=kind:continue
            path=repo/item['repository_path']
            assert path.is_file(), 'Obtain pinned file first: '+str(path)
            assert sha(path.read_bytes())==item['sha256'], 'Pinned source changed: '+str(path)
            records.extend(rows(path))
        content=''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in records).encode()
        assert sha(content)==dependency['aggregates'][kind+'.jsonl']['sha256']
        save(ROOT/(kind+'.jsonl'),records,True)
    print('Fixed aggregates restored and hashes matched; no review state modified.')

if __name__=='__main__':main()
