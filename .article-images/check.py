#!/usr/bin/env python3
"""Read-only article cover release check. Never publishes or generates images."""
import argparse
import hashlib
import json
import struct
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.images = []
        self.links = []
        self.stack = []
        self.cards = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta':
            key = a.get('property', a.get('name', ''))
            self.meta.setdefault(key, []).append(a.get('content', ''))
        card_classes={'news-card','story-card','article-card','news-item','related-card'}
        if set(a.get('class','').split()) & card_classes:
            card={'links':[],'images':[]}
            self.cards.append(card)
            a['_card']=card
        if tag == 'a':
            self.links.append(a.get('href', ''))
            for _,parent in self.stack:
                if '_card' in parent:parent['_card']['links'].append(a.get('href',''))
            if '_card' in a:a['_card']['links'].append(a.get('href',''))
        if tag in ('a','main','article','div','li'):
            self.stack.append((tag,a))
        if tag == 'img':
            self.images.append((a, list(self.stack)))
            for _,parent in self.stack:
                if '_card' in parent:parent['_card']['images'].append(a)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

def asset(root, url, origin):
    full = urlsplit(urljoin(origin + '/', url))
    if (full.scheme, full.netloc) != ('https', urlsplit(origin).netloc):
        raise ValueError('image/page must be hosted on this HTTPS site')
    if full.query or full.fragment:
        raise ValueError('use stable versioned asset paths without query/fragment')
    path = unquote(full.path)
    if any(part == '..' for part in path.split('/')):
        raise ValueError('parent path is forbidden')
    target = (root / path.lstrip('/')).resolve()
    if root != target and root not in target.parents:
        raise ValueError('path escapes release directory')
    if path.endswith('/'):
        target /= 'index.html'
    target = target.resolve()
    if root != target and root not in target.parents:
        raise ValueError('path escapes release directory')
    return target, full.geturl()

def header_dimensions(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw) >= 24:
        return struct.unpack('>II', raw[16:24])
    if raw[:2] == b'\xff\xd8':
        pos = 2
        while pos < len(raw):
            if raw[pos] != 255:
                pos += 1
                continue
            while pos < len(raw) and raw[pos] == 255:
                pos += 1
            if pos >= len(raw):
                break
            marker = raw[pos]
            pos += 1
            if marker in (0xd8, 0xd9) or 0xd0 <= marker <= 0xd7:
                continue
            length = int.from_bytes(raw[pos:pos+2], 'big')
            if length < 2:
                break
            if marker in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf):
                height, width = struct.unpack('>HH', raw[pos+3:pos+7])
                return width, height
            pos += length
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        kind = raw[12:16]
        if kind == b'VP8X':
            return 1+int.from_bytes(raw[24:27], 'little'), 1+int.from_bytes(raw[27:30], 'little')
        if kind == b'VP8 ' and raw[23:26] == b'\x9d\x01\x2a':
            w, h = struct.unpack('<HH', raw[26:30])
            return w & 0x3fff, h & 0x3fff
        if kind == b'VP8L' and raw[20:21] == b'\x2f':
            bits = int.from_bytes(raw[21:25], 'little')
            return (bits & 0x3fff)+1, ((bits >> 14) & 0x3fff)+1
    raise ValueError('cannot read PNG/JPEG/WebP dimensions')

def dimensions(raw):
    from io import BytesIO
    try:
        from PIL import Image
        with Image.open(BytesIO(raw)) as image:
            if image.format not in ('PNG', 'JPEG', 'WEBP', 'MPO'):
                raise ValueError('cover must be PNG/JPEG/WebP')
            size = image.size
            image.verify()
        with Image.open(BytesIO(raw)) as image:
            image.load()
        if size != header_dimensions(raw):
            raise ValueError('raster/header dimensions differ')
        return size
    except ImportError as exc:
        raise ValueError('Pillow is required to decode cover images') from exc
    except (OSError, SyntaxError) as exc:
        raise ValueError('cover raster cannot be decoded') from exc

def check(root, manifest):
    root = Path(root).resolve()
    errors, verified = [], []
    origin = manifest.get('origin', '').rstrip('/')
    u = urlsplit(origin)
    if u.scheme != 'https' or not u.netloc or u.path or u.query or u.fragment or u.username:
        return {'ok': False, 'errors': ['origin must be an HTTPS origin'], 'articles': []}
    rows = manifest.get('articles', [])
    if not isinstance(rows, list) or not rows:
        return {'ok': False, 'errors': ['articles must not be empty'], 'articles': []}
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append('article must be an object')
            continue
        label = str(row.get('path', '(missing path)'))
        def fail(message):
            errors.append(label + ': ' + message)
        try:
            for key in ('path', 'title', 'image', 'alt', 'width', 'height', 'sha256', 'source', 'listings'):
                if not row.get(key):
                    raise ValueError('required field missing: ' + key)
            if not isinstance(row['listings'], list) or not row['listings']:
                raise ValueError('listings must be a nonempty list')
            if not isinstance(row['source'], dict):
                raise ValueError('source must be an object')
            pagepath, pageurl = asset(root, row['path'], origin)
            if pageurl in seen:
                raise ValueError('duplicate article path')
            seen.add(pageurl)
            imagepath, imageurl = asset(root, row['image'], origin)
            raw = imagepath.read_bytes()
            size = dimensions(raw)
            if size != (row['width'], row['height']):
                fail('declared dimensions differ from image bytes')
            if size[0] < 600 or size[1] < 315:
                fail('cover must be at least 600x315; prepare 1200x630 or larger')
            if hashlib.sha256(raw).hexdigest() != row['sha256']:
                fail('image SHA-256 differs from reviewed image')
            if len(raw) > 5_000_000:
                fail('image exceeds 5 MB')
            source = row['source']
            if source.get('kind') not in ('photo', 'official', 'generated', 'designed') or not source.get('reference'):
                fail('source kind and source/generation record reference are required')
            page = Page(pagepath.read_text(encoding='utf-8'))
            expected = {'og:image': imageurl, 'og:image:alt': row['alt'],
                        'og:image:width': str(row['width']), 'og:image:height': str(row['height']),
                        'twitter:card': 'summary_large_image', 'twitter:image': imageurl,
                        'twitter:image:alt': row['alt']}
            for key, value in expected.items():
                if page.meta.get(key) != [value]:
                    fail('missing, duplicate or mismatched ' + key)
            covers = [(a, stack) for a, stack in page.images if 'data-article-cover' in a]
            if len(covers) != 1:
                fail('exactly one img[data-article-cover] is required')
            else:
                a, stack = covers[0]
                if not any(tag in ('main', 'article') for tag, _ in stack):
                    fail('article cover must be inside main/article')
                if urljoin(pageurl, a.get('src', '')) != imageurl:
                    fail('article cover and share image differ')
                if a.get('alt') != row['alt']:
                    fail('article cover alt differs')
                if a.get('width') != str(row['width']) or a.get('height') != str(row['height']):
                    fail('article cover intrinsic dimensions differ')
                if a.get('loading') == 'lazy':
                    fail('top cover must not be lazy loaded')
            for listing in row['listings']:
                listpath, listurl = asset(root, listing, origin)
                index = Page(listpath.read_text(encoding='utf-8'))
                matches = [a for a, stack in index.images
                           if urljoin(listurl, a.get('src', '')) == imageurl
                           and any(tag == 'a' and urljoin(listurl, attrs.get('href', '')) == pageurl
                                   for tag, attrs in stack)]
                for card in index.cards:
                    if any(urljoin(listurl,href)==pageurl for href in card['links']):
                        matches.extend(a for a in card['images'] if urljoin(listurl,a.get('src',''))==imageurl)
                if not matches:
                    fail('article card image missing in ' + listing)
            verified.append({'path': row['path'], 'image': row['image'], 'bytes': len(raw), 'dimensions': size})
        except (OSError, ValueError, TypeError, KeyError, struct.error) as exc:
            fail(str(exc))
    return {'ok': not errors, 'errors': errors, 'articles': verified}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--manifest', required=True, type=Path)
    a = p.parse_args()
    try:
        report = check(a.root, json.loads(a.manifest.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError) as exc:
        report = {'ok': False, 'errors': [str(exc)], 'articles': []}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['ok'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
