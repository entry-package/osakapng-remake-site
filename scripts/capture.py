"""Read PNG's public web pages; preserve a bounded, auditable migration corpus.

No credentials, administrator endpoints, external API calls or publishing.
Raw public responses stay in ignored .audit; only selected public content is exported.
"""
import concurrent.futures as futures
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.audit/source'
CONTENT = ROOT / 'content'
ORIGIN = 'https://www.pngesports.com'
HOSTS = {'www.pngesports.com', 'pngesports.com'}
CACHE.mkdir(parents=True, exist_ok=True)
CONTENT.mkdir(exist_ok=True)


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'PACkage-content-migration/1.0', 'Accept': 'text/html,application/xml,image/*;q=0.9,*/*;q=0.8'})
    with urllib.request.urlopen(req, timeout=40) as response:
        data = response.read(25_000_001)
        if len(data) > 25_000_000:
            raise ValueError('Response exceeds 25MB limit')
        return data, response.url, response.headers.get_content_type()


def canonical(url, base=ORIGIN):
    u = urllib.parse.urlsplit(urllib.parse.urljoin(base, url))
    if u.scheme not in {'http', 'https'} or u.hostname not in HOSTS:
        return None
    path = u.path.rstrip('/') or '/'
    return ORIGIN + path


def extract_json(html, variable):
    match = re.search(r'\$S\.' + re.escape(variable) + r'\s*=\s*', html)
    if not match:
        return {}
    try:
        return json.JSONDecoder().raw_decode(html[match.end():])[0]
    except (ValueError, TypeError):
        return {}


def capture(url):
    path = urllib.parse.urlsplit(url).path
    file = CACHE / (digest(url)[:20] + '.html')
    try:
        if file.exists():
            raw = file.read_bytes()
            final = url
        else:
            raw, final, mime = get(url)
            if mime != 'text/html':
                return {'url': url, 'status': 'non_html', 'mime': mime}, []
            file.write_bytes(raw)
        html = raw.decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        data = extract_json(html, 'blogPostData')
        meta = data.get('blogPostMeta', {})
        is_article = path.startswith('/blog/') and not path.startswith('/blog/categories')
        body = soup.select_one('.s-blog-content > .s-blog-body') if is_article else soup.select_one('#s-content')
        if body is None:
            body = soup.body
        for tag in body.select('script,style,noscript'):
            tag.decompose()
        title_el = soup.find('meta', property='og:title')
        title = title_el.get('content', '') if title_el else soup.title.get_text(' ', strip=True)
        description_el = soup.find('meta', attrs={'name': 'description'})
        cover_el = soup.find('meta', property='og:image')
        links = [{'href': urllib.parse.urljoin(url, a.get('href', '')), 'text': a.get_text(' ', strip=True)} for a in body.find_all('a', href=True)]
        images = []
        for img in body.find_all('img'):
            src = img.get('data-src') or img.get('src')
            if src and not src.startswith('data:'):
                images.append({'url': urllib.parse.urljoin(url, src), 'alt': img.get('alt', ''), 'width': img.get('width'), 'height': img.get('height')})
        record = {
            'url': url, 'path': path, 'final_url': final, 'status': 'ok',
            'type': 'article' if is_article else ('category' if path.startswith('/blog/categories') else 'page'),
            'title': title, 'description': description_el.get('content', '') if description_el else '',
            'published_at': meta.get('publishedAt'), 'categories': meta.get('categories', []),
            'tags': meta.get('tags', []), 'hide_date': data.get('settings', {}).get('hideBlogDate', False),
            'cover': cover_el.get('content', '') if cover_el else '',
            'source_text': body.get_text(' ', strip=True), 'body_html': str(body),
            'images': images, 'links': links, 'source_sha256': digest(raw),
            'body_text_sha256': digest(body.get_text(' ', strip=True)),
            'embeds': [str(x) for x in body.select('iframe,video,audio,[class*="s-video"],[class*="s-html"]')],
        }
        discovered = []
        for a in soup.find_all('a', href=True):
            dest = canonical(a['href'], url)
            if dest and (urllib.parse.urlsplit(dest).path.startswith(('/blog/', '/pages/')) or urllib.parse.urlsplit(dest).path in {'/', '/member', '/newsevents', '/_blog'}):
                discovered.append(dest)
        return record, discovered
    except Exception as error:
        return {'url': url, 'path': path, 'status': 'error', 'error': type(error).__name__ + ': ' + str(error)[:200]}, []


def main():
    sitemap, _, _ = get(ORIGIN + '/sitemap.xml')
    (CACHE / 'sitemap.xml').write_bytes(sitemap)
    urls = [x.text for x in ET.fromstring(sitemap).findall('{*}url/{*}loc')]
    pending = set(canonical(u) for u in urls)
    records = {}
    round_no = 0
    while pending:
        round_no += 1
        batch = sorted(pending - records.keys())
        pending = set()
        if len(records) + len(batch) > 220:
            raise RuntimeError('Discovery limit reached; inspect before expanding')
        with futures.ThreadPoolExecutor(max_workers=4) as pool:
            for record, links in pool.map(capture, batch):
                records[record['url']] = record
                pending.update(x for x in links if x not in records)
        (CONTENT / 'source-pages.json').write_text(json.dumps(list(records.values()), ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({'round': round_no, 'pages': len(records), 'new': len(pending), 'failures': sum(r['status'] != 'ok' for r in records.values())}), flush=True)
    report = {'observed_at': datetime.now(timezone.utc).isoformat(), 'sitemap_count': len(urls), 'sitemap_urls': urls, 'discovered_count': len(records), 'errors': [r for r in records.values() if r['status'] != 'ok']}
    (CONTENT / 'capture-summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'sitemap_urls'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
