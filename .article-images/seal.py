#!/usr/bin/env python3
"""Export only public image metadata; keep source-record locations in source storage."""
import hashlib,json,sys
from pathlib import Path

def seal(source, output):
    data=json.loads(Path(source).read_text())
    rows=[]
    for row in data['articles']:
        public={key:row[key] for key in ('path','title','image','alt','width','height','sha256')}
        public['listings']=row.get('listings',[])
        source_info=row['source']
        reference=source_info.get('reference')
        if not isinstance(reference,str) or not reference:
            raise ValueError('source reference is required')
        public['source']={'kind':source_info['kind'],'reference':'sha256:'+hashlib.sha256(reference.encode()).hexdigest()}
        rows.append(public)
    Path(output).write_text(json.dumps({'origin':data['origin'],'articles':rows},ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('usage: seal.py internal-manifest public-manifest')
    seal(*sys.argv[1:])
