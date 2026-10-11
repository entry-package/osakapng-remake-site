#!/usr/bin/env python3
"""Build same-design homepage translations using local, reviewed catalogs.

No translator API, network access, account, subscription or runtime translation.
Source hashes and complete catalog coverage are required before output is written.
This experimental command does not alter the existing production build.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup, Comment

ATTRS = ('alt', 'title', 'aria-label', 'placeholder', 'content')
JAPANESE = re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')

CSS = '''
.native-language{position:fixed;z-index:110;right:18px;bottom:calc(18px + var(--native-consent-height,0px));display:flex;align-items:center;gap:4px;padding:5px;border:1px solid #cbd1dc;border-radius:999px;background:#fff;color:#182239;box-shadow:0 5px 24px #12213922;font:600 13px/1.3 system-ui,sans-serif}
.native-language a{display:flex;align-items:center;justify-content:center;min-width:62px;min-height:38px;padding:0 12px;text-decoration:none!important;color:#182239;border-radius:999px;white-space:nowrap}
.native-language a[aria-current=page]{background:#172c4e;color:#fff}
.native-language a:focus-visible{outline:3px solid #1678f3;outline-offset:3px}
.native-language .native-preview{font-size:10px;padding:0 9px;color:#5c6474;letter-spacing:.04em}
html[lang=en] body{overflow-wrap:break-word;word-break:normal}
html[lang=en] h1,html[lang=en] h2,html[lang=en] h3{letter-spacing:-.025em}
html[lang=en] .summit-hero-copy h1{font-size:clamp(42px,6.5vw,96px);line-height:1.07}
html[lang=en] .summit-hero-copy>p:not(.hero-kicker){line-height:1.65}
html[lang=en] .hero-title{line-height:1.08}
html[lang=en] .hero-lead{line-height:1.8}
html[lang=en] .arena-copy h1 span,html[lang=en] .hero-message span{white-space:normal}
html[lang=en] .arena-copy h1{font-size:clamp(36px,4vw,60px)}
html[lang=en] .fact .num{font-size:clamp(26px,2.5vw,38px)}
html[lang=en] .fact .unit{font-size:13px}
html[lang=en] .featured-stats dd{overflow-wrap:anywhere}
html[lang=en] .header nav{gap:clamp(12px,1.6vw,28px)}
@media(max-width:600px){.native-language{right:12px;bottom:calc(12px + var(--native-consent-height,0px))}.native-language .native-preview,.native-language a[aria-current=page]{display:none}.native-language a{min-width:56px;padding:0 10px}html[lang=en] .summit-hero-copy h1{font-size:clamp(36px,9.8vw,58px)}html[lang=en] .hero h1{font-size:clamp(33px,9.5vw,46px)}}
'''

JS = '''
(()=>{
 const links=document.querySelectorAll('.native-language a');
 const update=()=>links.forEach(a=>{a.hash=location.hash;});
 const menu=document.querySelector('.menu-toggle[aria-label]');
 if(document.documentElement.lang==='en'&&menu){const syncMenu=()=>menu.setAttribute('aria-label',menu.getAttribute('aria-expanded')==='true'?'Close menu':'Open menu');new MutationObserver(syncMenu).observe(menu,{attributes:true,attributeFilter:['aria-expanded']});syncMenu();}
 update();addEventListener('hashchange',update);
 const consent=document.querySelector('#analytics-choice');
 if(consent){const sync=()=>{const r=consent.getBoundingClientRect();document.documentElement.style.setProperty('--native-consent-height',consent.hidden||getComputedStyle(consent).display==='none'?'0px':`${r.height+12}px`);};new ResizeObserver(sync).observe(consent);new MutationObserver(sync).observe(consent,{attributes:true});sync();}
})();
'''

def translated_texts(soup):
    for node in soup.find_all(string=True):
        if isinstance(node, Comment) or node.parent.name in ('script','style','noscript'):
            continue
        value = str(node).strip()
        if JAPANESE.search(value):
            yield node, None, value
    for node in soup.find_all(True):
        for attr in ATTRS:
            value = node.get(attr, '')
            if isinstance(value, str) and JAPANESE.search(value):
                yield node, attr, value

def preserve_urls(soup, origin, lang):
    for node in soup.find_all(True):
        if node.get('srcset'):
            entries=[]
            for entry in node['srcset'].split(','):
                bits=entry.strip().split()
                if not bits:continue
                url=urlsplit(urljoin(origin+'/',bits[0]))
                if url.netloc==urlsplit(origin).netloc:
                    bits[0]=url.path+('?' + url.query if url.query else '')
                entries.append(' '.join(bits))
            node['srcset']=', '.join(entries)
        for attr in ('href','src','poster','action'):
            value=node.get(attr)
            if not value or value.startswith(('#','data:','mailto:','tel:','javascript:')):
                continue
            url=urlsplit(urljoin(origin+'/',value))
            if url.netloc==urlsplit(origin).netloc:
                path=url.path or '/'
                if path in ('/','/index.html'):
                    path='/en/' if lang=='en' else '/'
                node[attr]=path+('?' + url.query if url.query else '')+('#'+url.fragment if url.fragment else '')
                if lang=='en' and node.name=='a' and path not in ('/en/',):
                    node['hreflang']='ja'
                    node['title']='Japanese page'

def structure(soup):
    main=soup.find('main')
    return [(n.name,n.get('id'),n.get('class')) for n in main.find_all(True)]

def render(raw, catalog, origin, lang):
    soup=BeautifulSoup(raw,'html.parser')
    original_structure=structure(soup)
    if lang=='en':
        missing={v for _,_,v in translated_texts(soup) if v not in catalog}
        if missing:raise ValueError(f'Missing {len(missing)} translations: {sorted(missing)[:5]}')
        for node,attr,value in list(translated_texts(soup)):
            translation=catalog[value]
            if not isinstance(translation,str) or not translation.strip():
                raise ValueError('Empty translation: '+value)
            if attr:node[attr]=translation
            else:
                raw_text=str(node)
                left=raw_text[:len(raw_text)-len(raw_text.lstrip())]
                right=raw_text[len(raw_text.rstrip()):]
                node.replace_with(left+translation+right)
    soup.html['lang']=lang
    # The personal name is part of the original visual identity; its existing
    # English reading directly below remains visible and avoids duplicate names.
    if lang=='en' and soup.select_one('.hero-name'):
        name=soup.select_one('.hero-name')
        name.string=BeautifulSoup(raw,'html.parser').select_one('.hero-name').get_text()
        name['lang']='ja'
    preserve_urls(soup,origin,lang)
    # This is a private localhost proof, not an indexed or deployable release.
    for node in soup.select('link[rel=canonical],link[hreflang],meta[name=robots]'):
        node.decompose()
    robots=soup.new_tag('meta',attrs={'name':'robots','content':'noindex,nofollow'})
    soup.head.append(robots)
    css=soup.new_tag('link',attrs={'rel':'stylesheet','href':'/native-i18n.css'})
    soup.head.append(css)
    nav=soup.new_tag('nav',attrs={'class':'native-language','aria-label':'Language / 言語'})
    label=soup.new_tag('span',attrs={'class':'native-preview'})
    label.string='PREVIEW';nav.append(label)
    for code,text,href in [('ja','日本語','/'),('en','English','/en/')]:
        a=soup.new_tag('a',attrs={'href':href,'lang':code,'hreflang':code})
        if code==lang:a['aria-current']='page'
        a.string=text;nav.append(a)
    soup.body.append(nav)
    script=soup.new_tag('script',attrs={'src':'/native-i18n.js','defer':''})
    soup.body.append(script)
    assert structure(soup)==original_structure,'Original main DOM structure changed'
    return str(soup)

def main():
    p=argparse.ArgumentParser();p.add_argument('--catalog-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--origin',required=True);a=p.parse_args()
    raw=(a.catalog_dir/'source-home.html').read_text()
    receipt=json.loads((a.catalog_dir/'source-receipt.json').read_text())
    assert hashlib.sha256(raw.encode()).hexdigest()==receipt['clean_source_sha256'],'Snapshot changed: re-extract and review the catalog'
    catalog=json.loads((a.catalog_dir/'en.json').read_text())
    pages={code:render(raw,catalog,a.origin,code) for code in ('ja','en')}
    a.output.mkdir(parents=True,exist_ok=True)
    for code,value in pages.items():
        target=a.output/('en/index.html' if code=='en' else 'index.html');target.parent.mkdir(parents=True,exist_ok=True);target.write_text(value)
    (a.output/'native-i18n.css').write_text(CSS)
    (a.output/'native-i18n.js').write_text(JS)
    report={'site':receipt['site'],'translated_strings':len(catalog),'main_dom_preserved':True,'source_sha256':receipt['source_sha256'],'external_translation_calls':0,'subscription_added':False,'scope':'Complete homepage text and metadata, English only; secondary pages remain Japanese','output':str(a.output)}
    (a.output.parent/'build-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
