"""Independent content-conservation and static-release checks."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist'
pages = json.loads((ROOT/'content/source-pages.json').read_text())
article_lookup = {p['path']:p for p in pages}
for file in (ROOT/'content/posts').glob('*.json'):
    p=json.loads(file.read_text()); article_lookup[p['path']]=p
media = json.loads((ROOT/'content/media-manifest.json').read_text())
thumbnail_assets = json.loads((ROOT/'content/thumbnail-assets.json').read_text())
thumbnail_overrides = json.loads((ROOT/'content/thumbnail-overrides.json').read_text())
routes = json.loads((ROOT/'content/route-manifest.json').read_text())
member_updates = json.loads((ROOT/'content/member-updates.json').read_text())
failures = []
checks = []
def check(ok, kind, detail):
    row = {'check':kind,'detail':detail,'pass':bool(ok)}
    checks.append(row)
    if not ok: failures.append(row)

def normalize(text): return re.sub(r'\s+', '', text)
def normalized_href(href, origin):
    u = urlsplit(urljoin(origin, href))
    host = 'preview.invalid' if u.netloc in {'www.pngesports.com','pngesports.com'} else u.netloc
    return u._replace(path=u.path.rstrip('/') or '/', netloc=host).geturl()

for p in pages:
    check(p['path'] in routes, 'source_route', p['path'])
    if p['type'] != 'article': continue
    file = OUT/routes[p['path']]['file']
    soup = BeautifulSoup(file.read_text(), 'html.parser')
    body = soup.select_one('[data-source-body]')
    check(body and normalize(body.get_text(' ',strip=True)) == normalize(p['source_text']), 'article_text', p['path'])
    oldlinks = Counter(normalized_href(x['href'],p['url']) for x in p['links'])
    newlinks = Counter(normalized_href(x['href'],'https://preview.invalid'+p['path']+'/') for x in body.select('a[href]'))
    check(oldlinks == newlinks, 'article_links', {'path':p['path'],'missing':list((oldlinks-newlinks).elements()),'extra':list((newlinks-oldlinks).elements())})
    oldimages = Counter(media[x['url']]['local'] for x in p['images'])
    newimages = Counter(unquote(urlsplit(urljoin('https://preview.invalid'+p['path']+'/',x['src'])).path).lstrip('/') for x in body.select('img[src]'))
    check(oldimages == newimages, 'article_images',p['path'])

for url,entry in media.items():
    file = ROOT/entry.get('local','missing')
    check(entry['status']=='ok' and file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest()==entry.get('sha256'), 'media_checksum',url)

missing_covers = {p['path'] for p in pages if p['type']=='article' and (not p['cover'] or p['cover'].endswith('/images/icons/transparent.png'))}
check(set(thumbnail_overrides)==missing_covers, 'all_missing_thumbnails_covered', {'missing':sorted(missing_covers-set(thumbnail_overrides)),'unexpected':sorted(set(thumbnail_overrides)-missing_covers)})
for key,entry in thumbnail_assets.items():
    file = ROOT/entry['local']
    check(file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest()==entry['sha256'], 'thumbnail_checksum',key)
    check((OUT/entry['local']).read_bytes()==file.read_bytes(), 'thumbnail_distributed',key)
for p in (p for p in pages if p['type']=='article'):
    override = thumbnail_overrides.get(p['path'])
    expected = thumbnail_assets[override['asset']]['local'] if override else media[p['cover']]['local']
    soup = BeautifulSoup((OUT/routes[p['path']]['file']).read_text(),'html.parser')
    image_url = 'https://www.pngesports.com/'+expected
    check(soup.select_one('meta[property="og:image"]')['content']==image_url, 'article_cover_matches',p['path'])
    check(soup.select_one('meta[name="twitter:image"]')['content']==image_url, 'twitter_cover_matches',p['path'])
    structured=json.loads(soup.select_one('script[type="application/ld+json"]').string)
    if structured['@type']=='NewsArticle':
        check(structured['image']==image_url,'structured_cover_matches',p['path'])
    if override:
        check(override['source_cover']==p['cover'],'only_missing_cover_overridden',p['path'])
for route in ['/newsevents','/_blog','/blog/categories/news-1175894','/blog/categories']:
    soup=BeautifulSoup((OUT/routes[route]['file']).read_text(),'html.parser')
    seen=set()
    for card in soup.select('[data-news]'):
        path=urlsplit(urljoin('https://preview.invalid'+route+'/',card.select_one('h3 a')['href'])).path.rstrip('/')
        p=article_lookup[path]
        override=thumbnail_overrides.get(path)
        expected=thumbnail_assets[override['asset']]['local'] if override else (media[p['cover']]['local'] if p['cover'] else 'assets/hero-logo.png')
        actual=urlsplit(urljoin('https://preview.invalid'+route+'/',card.select_one('.news-cover img')['src'])).path.lstrip('/')
        check(actual==expected,'news_card_cover_matches',{'listing':route,'article':path})
        if override: seen.add(path)
    check(seen==missing_covers,'all_editorial_covers_listed',route)

for path,entry in routes.items():
    file = OUT/entry['file']; html = file.read_text(); soup=BeautifulSoup(html,'html.parser')
    check(len(soup.find_all('h1'))==1, 'single_h1',path)
    check(soup.title and len(soup.title.get_text())>5,'page_title',path)
    check(soup.find('meta',attrs={'name':'robots'}).get('content')=='noindex,nofollow','preview_not_indexed',path)
    check(not re.search(r'\{\{[A-Z_]+\}\}',html),'no_template_tokens',path)
    check(not soup.select('script[src^="http"],iframe'),'no_platform_script_or_embed',path)
    ids = [x['id'] for x in soup.select('[id]')]
    check(len(ids)==len(set(ids)), 'unique_ids',path)
    for tag in soup.select('a[href],img[src],script[src],link[href]'):
        value=tag.get('href') or tag.get('src'); u=urlsplit(value)
        if u.scheme or u.netloc:continue
        dest = urlsplit(urljoin('https://preview.invalid'+path.rstrip('/')+'/',value))
        target=OUT/unquote(dest.path).lstrip('/')
        if target.is_dir(): target=target/'index.html'
        check(target.is_file(),'local_target',{'page':path,'url':value})
        if dest.fragment and target.suffix=='.html' and target.exists():
            check(BeautifulSoup(target.read_text(),'html.parser').find(id=unquote(dest.fragment)) is not None,'fragment_target',{'page':path,'url':value})
    for img in soup.select('img'):
        check(img.has_attr('alt'),'image_alt',path)
    for structured in soup.select('script[type="application/ld+json"]'):
        try:json.loads(structured.string);valid=True
        except Exception:valid=False
        check(valid,'structured_data',path)

departed = {path for path, update in member_updates.items() if update.get('membership_state') == 'departed'}
for route in ['/', '/member', '/blog/categories/member-1155238']:
    soup = BeautifulSoup((OUT/routes[route]['file']).read_text(),'html.parser')
    listed = {urlsplit(urljoin('https://preview.invalid'+route+'/',a['href'])).path.rstrip('/') for a in soup.select('.talent-card h3 a')}
    check(not (listed & departed), 'departed_members_not_in_current_roster', route)
    source_members = {urlsplit(a['href']).path for a in next(p for p in pages if p['path']=='/member')['links'] if '/blog/' in a['href']}
    check(listed == source_members - departed, 'current_roster_preserved', route)
for path in departed:
    soup = BeautifulSoup((OUT/routes[path]['file']).read_text(),'html.parser')
    check('脱退済み' in soup.select_one('.profile-update').get_text(), 'departure_notice_above_archived_profile', path)
    check('脱退済み' in soup.find('meta',attrs={'name':'description'})['content'], 'departure_in_profile_description', path)

summary={'source_pages':len(pages),'articles_verified':sum(p['type']=='article' for p in pages),'source_image_references':sum(len(p['images']) for p in pages if p['type']=='article'),'routes':len(routes),'editorial_thumbnails':len(thumbnail_overrides),'thumbnail_designs':len(thumbnail_assets),'checks':len(checks),'failures':failures,'result':'PASS' if not failures else 'FAIL'}
(ROOT/'content/verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
raise SystemExit(bool(failures))
