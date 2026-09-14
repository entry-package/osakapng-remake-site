"""Read-only availability check of published URLs; never retries auth failures."""
import concurrent.futures
import json
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
urls={}
previous_path=ROOT/'content/external-link-verification.json'
previous=json.loads(previous_path.read_text()).get('links',{}) if previous_path.exists() else {}
for f in (ROOT/'dist').rglob('*.html'):
    for a in BeautifulSoup(f.read_text(),'html.parser').select('a[href]'):
        u=a['href']; parts=urlsplit(u)
        if parts.scheme not in {'http','https'}:continue
        urls.setdefault(u,set()).add(str(f.relative_to(ROOT/'dist')))
def inspect(url):
    if url in previous:
        return url,{**previous[url],'pages':sorted(urls[url])}
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'PACkage-public-link-check/1.0'},method='GET')
        with urllib.request.urlopen(req,timeout=12) as response:
            response.read(512)
            return url,{'status':response.status,'result':'responded','final_host':urlsplit(response.url).hostname,'pages':sorted(urls[url])}
    except urllib.error.HTTPError as error:
        return url,{'status':error.code,'result':'missing' if error.code in {404,410} else 'unverified_response','pages':sorted(urls[url])}
    except Exception as error:
        return url,{'status':None,'result':'unverified_network','error_type':type(error).__name__,'pages':sorted(urls[url])}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    result=dict(pool.map(inspect,sorted(urls)))
counts={label:sum(v['result']==label for v in result.values()) for label in ('responded','missing','unverified_response','unverified_network')}
(ROOT/'content/external-link-verification.json').write_text(json.dumps({'policy':'Active links only; previous availability results are reused when present. Public unauthenticated GET only for new URLs. No login, challenge bypass, retries or external sends. 403/429 are unverified, not evidence of deletion. Reviewed historical-link corrections are recorded in content/link-corrections.json.','count':len(result),'counts':counts,'reused_result_count':sum(url in previous for url in result),'requested_now_count':sum(url not in previous for url in result),'links':result},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'count':len(result),'counts':counts},ensure_ascii=False))
