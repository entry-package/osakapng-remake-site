#!/usr/bin/env python3
"""Check shipped HTML, language navigation, assets, anchors and original content."""
import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
LOCALES={'en':'en','zh-hans':'zh-Hans','zh-hant':'zh-Hant','ko':'ko'}

def verify(output, original_prefix=None, original_ref=None):
    data=json.loads((ROOT/'content/i18n/overviews.json').read_text())
    errors=[];checks=0
    def check(ok,message):
        nonlocal checks
        checks+=1
        if not ok:errors.append(message)
    def parse(file): return BeautifulSoup(file.read_text(),'html.parser')
    expected={**{v:data['origin']+'/'+k+'/' for k,v in LOCALES.items()},'ja':data['origin']+'/','x-default':data['origin']+'/'}
    for slug,lang in LOCALES.items():
        file=output/slug/'index.html';d=parse(file)
        check(d.html.get('lang')==lang,f'{slug}: document language')
        check(len(d.select('h1'))==1,f'{slug}: h1 count')
        check(d.title is not None and len(d.title.text)>8,f'{slug}: title')
        check(d.select_one('link[rel=canonical]')['href']==data['origin']+'/'+slug+'/',f'{slug}: canonical')
        check({n['hreflang']:n['href'] for n in d.select('head link[hreflang]')}==expected,f'{slug}: reciprocal alternates')
        check(len(d.select('[data-site-languages] a'))==5,f'{slug}: 5 language links')
        check(len(d.select('form'))==1 and not d.form.get('action'),f'{slug}: email draft only')
        check(all(n.get('hreflang')=='ja' for n in d.select('.original-links a')),f'{slug}: original link languages')
        check(len(d.select('.related-links a'))==2,f'{slug}: related sites')
        check(all(urlsplit(n['href']).path==f'/{slug}/' for n in d.select('.related-links a')),f'{slug}: related site locale')
        check(not d.select('script[src^="http"],iframe'),f'{slug}: no external translation runtime')
        ids=[x['id'] for x in d.select('[id]')]
        check(len(ids)==len(set(ids)),f'{slug}: duplicate IDs')
        for label in d.select('label[for]'):check(d.find(id=label['for']) is not None,f'{slug}: label target')
        for node in d.select('a[href],link[href],img[src],script[src]'):
            url=node.get('href',node.get('src',''));p=urlsplit(url)
            if p.scheme or p.netloc:continue
            path=unquote(p.path)
            target=(output/path.lstrip('/')) if path else file
            if target.is_dir():target=target/'index.html'
            check(target.is_file(),f'{slug}: missing {url}')
            if p.fragment and target.is_file() and target.suffix=='.html':
                check(parse(target).find(id=unquote(p.fragment)) is not None,f'{slug}: missing anchor {url}')
        for obj in d.select('script[type="application/ld+json"]'):
            check(json.loads(obj.string)['inLanguage']==lang,f'{slug}: structured data language')
    home=parse(output/'index.html')
    check({n['hreflang']:n['href'] for n in home.select('head link[hreflang]')}==expected,'Japanese home: reciprocal alternates')
    sitemap=(output/'sitemap.xml').read_text()
    for url in expected.values():check(f'<loc>{url}</loc>' in sitemap,f'sitemap: {url}')
    japanese=0
    for file in output.rglob('*.html'):
        rel=file.relative_to(output)
        if rel.parts[0] in LOCALES or any(x.startswith('.') for x in rel.parts):continue
        raw=file.read_text()
        if '<body' not in raw or re.search(r'http-equiv=["\']refresh',raw,re.I):continue
        d=BeautifulSoup(raw,'html.parser')
        check(len(d.select('[data-site-languages]'))==1,f'{rel}: one language menu')
        japanese+=1
        if original_ref:
            source=(Path(original_prefix or '')/rel).as_posix()
            proc=subprocess.run(['git','show',f'{original_ref}:{source}'],cwd=ROOT,capture_output=True,text=True)
            if proc.returncode:continue
            old=BeautifulSoup(proc.stdout,'html.parser')
            check(str(d.select_one('main'))==str(old.select_one('main')),f'{rel}: Japanese main content changed')
            check([str(x) for x in d.select('form')]==[str(x) for x in old.select('form')],f'{rel}: Japanese forms changed')
    result={'passed':not errors,'checks':checks,'localized_pages':4,'japanese_pages_with_language_menu':japanese,'errors':errors}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--original-ref');p.add_argument('--original-prefix');p.add_argument('--report',type=Path)
    args=p.parse_args();result=verify(args.output.resolve(),args.original_prefix,args.original_ref)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    raise SystemExit(0 if result['passed'] else 1)
