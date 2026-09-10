"""Mirror the images referenced by the captured public PNG content."""
import concurrent.futures as futures
import hashlib
import json
import mimetypes
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from capture import ROOT, get

def run():
    pages = json.loads((ROOT / 'content/source-pages.json').read_text())
    urls = {i['url'] for p in pages for i in p['images']}
    urls.update(p['cover'] for p in pages if p['cover'])
    # Hero and other CSS-backed images are not represented by img tags.
    for file in (ROOT / '.audit/source').glob('*.html'):
        soup = BeautifulSoup(file.read_text(), 'html.parser')
        scope = soup.select_one('#s-content') or soup
        for tag in scope.select('[data-background], [data-bg], [data-src]'):
            for attr in ('data-background', 'data-bg', 'data-src'):
                val = tag.get(attr, '')
                if val.startswith(('https://', '//')) and 'strikinglycdn.com/' in val:
                    urls.add(urljoin('https://www.pngesports.com', val))
    dest = ROOT / 'assets/archive'
    dest.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / 'content/media-manifest.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    def download(url):
        if url == '/images/icons/transparent.png':
            raw = (ROOT / 'assets/brand-mark.png').read_bytes()
            return url, {'status': 'ok', 'local': 'assets/brand-mark.png', 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'mime': 'image/png', 'disposition': 'Empty Strikingly cover placeholder replaced with existing PNG brand mark; not an editorial content image.'}
        old = previous.get(url)
        if old and old.get('status') == 'ok' and (ROOT / old['local']).exists():
            return url, old
        try:
            raw, final, mime = get(url)
            if not mime.startswith('image/'):
                raise ValueError('Expected image, received ' + mime)
            ext = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/gif': '.gif', 'image/webp': '.webp', 'image/svg+xml': '.svg'}.get(mime)
            if not ext:
                raise ValueError('Unsupported image type ' + mime)
            digest = hashlib.sha256(raw).hexdigest()
            relative = 'assets/archive/' + digest[:24] + ext
            (ROOT / relative).write_bytes(raw)
            return url, {'status': 'ok', 'local': relative, 'sha256': digest, 'bytes': len(raw), 'mime': mime}
        except Exception as error:
            return url, {'status': 'error', 'error': type(error).__name__ + ': ' + str(error)[:180]}
    with futures.ThreadPoolExecutor(max_workers=4) as pool:
        result = dict(pool.map(download, sorted(urls)))
    manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    failures = {u: v for u, v in result.items() if v['status'] != 'ok'}
    print(json.dumps({'references': len(result), 'unique_files': len({v.get('local') for v in result.values() if v['status'] == 'ok'}), 'bytes': sum(v.get('bytes', 0) for v in result.values()), 'failures': failures}, ensure_ascii=False))
    if failures:
        raise SystemExit(1)

if __name__ == '__main__':
    run()
