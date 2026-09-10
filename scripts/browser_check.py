"""Isolated local Chromium QA; never opens an authenticated user profile.

Uses Chrome's documented headless CLI. The harness is local, disposable and is
removed from the distributable after verification. No external messages are sent.
"""
import json
import subprocess
import time
from pathlib import Path
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'.audit'; DIST=ROOT/'dist'
CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
ORIGIN='http://127.0.0.1:8766'
AUDIT.mkdir(exist_ok=True)

HARNESS='''<!doctype html><meta charset="utf-8"><title>Local verification</title><pre id="result">RUNNING</pre><iframe id="frame" style="border:0;width:1440px;height:1000px"></iframe><script>
const report=[]; const f=document.querySelector('iframe');
const assert=(ok,name,detail)=>report.push({pass:!!ok,name,detail});
const load=async(path,width)=>{f.style.width=width+'px';await new Promise((yes,no)=>{f.onload=yes;f.onerror=no;f.src=path});await f.contentDocument.fonts.ready;await new Promise(r=>setTimeout(r,70));return f.contentDocument};
const widths=[320,375,390,768,1024,1440];
const routes=['/','/member/','/newsevents/','/about/','/contact/','/stories/','/blog/7e2b75b2ff9/','/blog/d8211521a58/','/blog/3328bc126c9/','/blog/e-pngesports-osakapng/'];
(async()=>{
for(const route of routes)for(const width of widths){
 const d=await load(route,width),w=f.contentWindow;
 assert(d.documentElement.scrollWidth<=d.documentElement.clientWidth+1,'no_horizontal_overflow',{route,width,scroll:d.documentElement.scrollWidth,client:d.documentElement.clientWidth});
 assert(d.querySelector('h1')?.getBoundingClientRect().width>0,'heading_visible',{route,width});
 const broken=[...d.images].filter(i=>i.complete && i.naturalWidth===0).map(i=>i.getAttribute('src'));
 assert(!broken.length,'no_broken_loaded_images',{route,width,broken});
 if(route==='/newsevents/'){
  const images=[...d.querySelectorAll('.news-card--generated .news-cover img')];
  images.forEach(i=>i.loading='eager');
  // Image decode promises can outlive headless virtual-time capture. Verify the
  // actual loaded resources after the eager requests have settled instead.
  await new Promise(r=>setTimeout(r,300));
  assert(images.length===22&&images.every(i=>i.complete&&i.naturalWidth===Number(i.getAttribute('width'))),'all_editorial_images_loaded',{width,count:images.length});
  const clipped=images.filter(i=>{const r=i.getBoundingClientRect(),c=i.parentElement.getBoundingClientRect();return w.getComputedStyle(i).objectFit!=='contain'||Math.abs(r.width/r.height-i.naturalWidth/i.naturalHeight)>.01||r.bottom>c.bottom+1||r.right>c.right+1});
  assert(!clipped.length,'editorial_titles_not_cropped',{width,clipped:clipped.map(i=>i.src)});
 }
}
for(const route of ['/','/member/','/newsevents/','/contact/'])for(const width of [375,768,1440]){
 const d=await load(route,width);d.documentElement.style.fontSize='200%';
 assert(d.documentElement.scrollWidth<=d.documentElement.clientWidth+1,'text_200_percent',{route,width,scroll:d.documentElement.scrollWidth,client:d.documentElement.clientWidth});
}
let d=await load('/newsevents/',390),w=f.contentWindow,search=d.querySelector('#news-search'),year=d.querySelector('#news-year');
const fire=()=>search.dispatchEvent(new w.Event('input',{bubbles:true}));
search.value='桜木';fire();let shown=[...d.querySelectorAll('[data-news]')].filter(c=>!c.hidden);assert(shown.length>0&&shown.every(c=>c.dataset.search.includes('桜木')),'news_text_filter',shown.length);
search.value='zzzzNOT_A_REAL_NEWS_999';fire();assert(d.querySelector('#news-count').textContent==='0'&&!d.querySelector('#empty-results').hidden,'news_empty_state');
search.value='';year.value='2018';year.dispatchEvent(new w.Event('change',{bubbles:true}));shown=[...d.querySelectorAll('[data-news]')].filter(c=>!c.hidden);assert(shown.length>0&&shown.every(c=>c.dataset.year==='2018'),'news_year_filter',shown.length);
search.form.reset();await new Promise(r=>setTimeout(r,30));assert(d.querySelector('#news-count').textContent==='93','news_reset');
d=await load('/newsevents/?year=2018',390);assert(d.querySelector('#news-year').value==='2018','year_url_restored');
d=await load('/member/',390);let toggle=d.querySelector('.menu-toggle');toggle.click();assert(toggle.getAttribute('aria-expanded')==='true'&&d.querySelector('#site-nav').classList.contains('open'),'mobile_menu_open');d.dispatchEvent(new f.contentWindow.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));assert(toggle.getAttribute('aria-expanded')==='false','mobile_menu_escape');
d=await load('/contact/',390);assert(!d.querySelector('form').checkValidity(),'contact_required_fields');d.querySelector('[name=topic]').value='その他';d.querySelector('[name=name]').value='表示確認';d.querySelector('[name=email]').value='invalid';d.querySelector('[name=message]').value='ローカル動作確認・未送信';assert(!d.querySelector('form').checkValidity(),'contact_reject_invalid_email');d.querySelector('[name=email]').value='test@example.invalid';assert(d.querySelector('form').checkValidity(),'contact_valid_input');
const copied=[];Object.defineProperty(f.contentWindow.navigator,'clipboard',{value:{writeText:async value=>copied.push(value)},configurable:true});d.querySelector('#copy-message').click();await new Promise(r=>setTimeout(r,30));assert(copied.length===1&&copied[0].includes('ローカル動作確認・未送信')&&copied[0].includes('info@package-inc.com'),'contact_copy_prepared_text');assert(d.querySelector('.form-note').textContent.includes('コピーしました'),'contact_copy_status');
document.querySelector('#result').textContent=JSON.stringify({complete:true,checks:report.length,failures:report.filter(r=>!r.pass),report});
})().catch(error=>{document.querySelector('#result').textContent=JSON.stringify({complete:false,error:String(error),report})});
</script>'''

def chrome(name,args,completion):
    stdout=AUDIT/(name+'.out'); stderr=AUDIT/(name+'.err')
    base=[CHROME,'--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-component-update','--user-data-dir='+str(AUDIT/('browser-'+name))]
    with stdout.open('w') as out,stderr.open('w') as err:
        proc=subprocess.Popen(base+args,stdout=out,stderr=err)
        deadline=time.monotonic()+55
        try:
            while time.monotonic()<deadline:
                if completion(stdout): break
                if proc.poll() is not None: break
                time.sleep(.4)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=4)
                except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=4)
    return stdout

def main():
    harness=DIST/'qa-local-only.html';harness.write_text(HARNESS)
    output=chrome('checks',['--virtual-time-budget=25000','--dump-dom',ORIGIN+'/qa-local-only.html'],lambda f:'&quot;complete&quot;' in f.read_text() or '"complete":true' in f.read_text())
    dom=BeautifulSoup(output.read_text(),'html.parser');result=dom.select_one('#result')
    try:report=json.loads(result.get_text())
    except Exception:report={'complete':False,'error':'No completed browser report'}
    (ROOT/'content/browser-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    # Archive the temporary test page outside the deliverable.
    harness.replace(AUDIT/'qa-local-only.html')
    print(json.dumps({k:v for k,v in report.items() if k!='report'},ensure_ascii=False),flush=True)
    for name,path,width,height in [('home-desktop','/',1440,1050),('home-mobile','/',390,1000),('members-mobile','/member/',390,1200),('profile-mobile','/blog/7e2b75b2ff9/',390,1200),('archive-mobile','/newsevents/',390,1100),('thumbnails-desktop','/newsevents/?year=2018',1440,1350),('thumbnails-mobile','/newsevents/?year=2018',390,1600)]:
        file=AUDIT/(name+'.png')
        # A new filename makes completion independent of a previous run.
        stamp=str(time.time_ns());fresh=AUDIT/(name+'-'+stamp+'.png')
        target = ORIGIN+path
        frame = DIST/'qa-screenshot-local.html'
        if width < 500:
            frame.write_text('<!doctype html><meta charset="utf-8"><style>body{margin:0;background:#ddd}iframe{border:0;display:block;width:'+str(width)+'px;height:'+str(height)+'px}</style><iframe src="'+path+'"></iframe>')
            target = ORIGIN+'/qa-screenshot-local.html'
        chrome(name,['--window-size='+str(max(500,width))+','+str(height),'--screenshot='+str(fresh),'--timeout=10000',target],lambda _:fresh.exists())
        if frame.exists(): frame.replace(AUDIT/'qa-screenshot-local.html')
        if fresh.exists():fresh.replace(file);print('Screenshot '+name,flush=True)
    raise SystemExit(not report.get('complete') or bool(report.get('failures')))

if __name__=='__main__':main()
