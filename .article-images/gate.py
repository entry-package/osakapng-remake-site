#!/usr/bin/env python3
"""Fail-closed build/deployment gate for new or changed article images."""
import argparse
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote
import check as cover_check

VOID = set('area base br col embed hr img input link meta param source track wbr'.split())
IMAGE_META = {'og:image', 'og:image:alt', 'og:image:width', 'og:image:height',
              'twitter:card', 'twitter:image', 'twitter:image:alt'}
SHELLS = {'article-shell', 'article-content', 'report-body'}
IGNORE = {'article-neighbors', 'article-return', 'breadcrumbs', 'article-brand-link', 'back-link', 'article-event-links'}

class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []
    def nodes(self, tag=None):
        for child in self.children:
            if isinstance(child, Node):
                if tag is None or child.tag == tag:
                    yield child
                yield from child.nodes(tag)

class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(text)
        self.meta = {}
        for n in self.root.nodes('meta'):
            self.meta.setdefault(n.attrs.get('property', n.attrs.get('name', '')), []).append(n.attrs.get('content', ''))
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs)
        self.stack[-1].children.append(n)
        if tag not in VOID:
            self.stack.append(n)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break
    def handle_data(self, data):
        self.stack[-1].children.append(data)

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def canonical(path, base, origin):
    u = urlsplit(urljoin(base, path))
    if (u.scheme, u.netloc) != ('https', urlsplit(origin).netloc):
        return None
    p = unquote(u.path)
    if '..' in p.split('/'):
        raise ValueError('path traversal')
    if not p.endswith('/') and not Path(p).suffix:
        p += '/'
    return p

def semantic(node):
    if isinstance(node, str):
        return re.sub(r'\s+', ' ', node).strip()
    classes = set(node.attrs.get('class', '').split())
    if classes & IGNORE or node.tag in ('script', 'style'):
        return None
    attrs = {k:v for k,v in node.attrs.items() if not k.startswith('data-astro-')}
    children = [semantic(c) for c in node.children]
    return [node.tag, attrs, [c for c in children if c is not None and c != '']]

def route_for(file, root):
    rel = file.relative_to(root).as_posix()
    return '/' + (rel[:-10] if rel.endswith('index.html') else rel)

def scan(root, config):
    root = Path(root).resolve()
    origin = config['origin'].rstrip('/')
    docs, articles = {}, {}
    excluded = set(config.get('exclude_paths', []))
    excluded_prefixes = config.get('exclude_prefixes', [])
    prefixes = config.get('article_prefixes', [])
    explicit = set(config.get('article_paths', []))
    for file in sorted(root.rglob('*.html')):
        rel = file.relative_to(root)
        if any(part.startswith('.') for part in rel.parts):
            continue
        if file.is_symlink():
            raise ValueError('symlinked HTML is not permitted')
        route = route_for(file, root)
        page = Document(file.read_text(encoding='utf-8'))
        docs[route] = page
        if route in excluded or any(route.startswith(x) for x in excluded_prefixes):
            continue
        redirect = any(n.attrs.get('http-equiv', '').lower() == 'refresh' for n in page.root.nodes('meta'))
        if redirect:
            continue
        shells = [n for n in page.root.nodes() if set(n.attrs.get('class','').split()) & SHELLS]
        is_article = route in explicit or any(route.startswith(p) for p in prefixes) or page.meta.get('og:type') == ['article'] or bool(shells)
        if not is_article:
            continue
        sections = shells or list(page.root.nodes('main'))
        if not sections:
            raise ValueError(route + ': article has no main content')
        # A nested article-content is already included in its outer article-shell.
        if shells:
            sections = shells[:1]
        srcs = set()
        for section in sections:
            for img in section.nodes('img'):
                if img.attrs.get('src'):
                    srcs.add(urljoin(origin+route, img.attrs['src']))
                for candidate in img.attrs.get('srcset','').split(','):
                    if candidate.strip():
                        srcs.add(urljoin(origin+route, candidate.split()[0]))
        srcs.update(page.meta.get('og:image', []))
        deps = {}
        for src in sorted(srcs):
            try:
                p, full = cover_check.asset(root, src, origin)
                deps[full] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'missing'
            except ValueError:
                # Existing remote archive references stay stable; new/updated covers must be local.
                deps[src] = 'external'
        articles[route] = {
            'body': digest([semantic(n) for n in sections]),
            'heading': digest([semantic(n) for n in page.root.nodes('h1')]),
            'image_meta': {k:page.meta.get(k,[]) for k in sorted(IMAGE_META)},
            'assets': deps,
            'cards': {}
        }
    # Discover article links from news listings even when an author forgot article metadata.
    for listing in config.get('listing_paths', []):
        page = docs.get(listing)
        if not page:
            raise ValueError('required listing missing: '+listing)
        for anchor in page.root.nodes('a'):
            route = canonical(anchor.attrs.get('href',''), origin+listing, origin)
            if not route or route not in docs or route in excluded:
                continue
            if any(route.startswith(p) for p in excluded_prefixes):
                continue
            if route not in articles and route not in config.get('non_article_paths', []):
                raise ValueError('unclassified page linked from news listing: '+route+'; register as article or reviewed non-article')
    for listing, page in docs.items():
        for anchor in page.root.nodes('a'):
            target = canonical(anchor.attrs.get('href',''), origin+listing, origin)
            if target not in articles or target == listing:
                continue
            # Navigation and return links without images are not listing cards.
            imgs = list(anchor.nodes('img'))
            if not imgs:
                continue
            cards = []
            for n in imgs:
                src = urljoin(origin+listing, n.attrs.get('src',''))
                try:
                    p, full = cover_check.asset(root, src, origin)
                    sha = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'missing'
                except ValueError:
                    sha = 'external'
                cards.append({'src':src, 'sha256':sha})
            articles[target]['cards'].setdefault(listing, []).extend(cards)
    return docs, articles

def freeze(root, config):
    _, articles = scan(root, config)
    if not articles:
        raise ValueError('baseline cannot be empty')
    return {'schema_version':1, 'config_sha256':digest(config),
            'articles':{route:{'content':digest({k:v for k,v in row.items() if k!='cards'}),'cards':row['cards']} for route,row in sorted(articles.items())}}

def verify(root, config, baseline, manifest):
    errors = []
    if baseline.get('schema_version') != 1 or baseline.get('config_sha256') != digest(config):
        return {'ok':False, 'errors':['policy/baseline mismatch'], 'checked':[]}
    if manifest.get('origin') != config['origin']:
        return {'ok':False, 'errors':['manifest origin differs from site policy'], 'checked':[]}
    docs, found = scan(root, config)
    rows = manifest.get('articles')
    if not isinstance(rows,list):
        return {'ok':False,'errors':['manifest articles must be a list'],'checked':[]}
    indexed = {}
    for row in rows:
        route = canonical(row.get('path',''), config['origin']+'/', config['origin'])
        if not route or route in indexed:
            errors.append('invalid or duplicate manifest path')
            continue
        indexed[route] = row
    changed = []
    for route,data in found.items():
        before=baseline['articles'].get(route)
        content=digest({k:v for k,v in data.items() if k!='cards'})
        if not before or before['content']!=content:
            changed.append(route)
            continue
        allowed={digest(card) for cards in before['cards'].values() for card in cards}
        if any(digest(card) not in allowed for cards in data['cards'].values() for card in cards):
            changed.append(route)
            continue
        for listing in config.get('required_listing_paths',[]):
            if data['cards'].get(listing)!=before['cards'].get(listing):
                changed.append(route)
                break
    required = sorted(set(changed) | set(indexed))
    for route in required:
        if route not in found:
            errors.append(route+': manifest entry has no discovered article')
        if route not in indexed:
            errors.append(route+': new/updated article requires reviewed cover manifest; select or create an image')
    checked = []
    for route in required:
        if route not in indexed or route not in found:
            continue
        row = dict(indexed[route])
        # Discover every actual image card and always require the site's news listing.
        # A removed card cannot disappear from validation by omission from the manifest.
        row['listings']=sorted(set(found[route]['cards']) | set(config.get('required_listing_paths',[])) | set(row.get('listings',[])))
        result = cover_check.check(root, {'origin':config['origin'],'articles':[row]})
        errors.extend(result['errors'])
        checked.extend(result['articles'])
    return {'ok':not errors,'errors':errors,'discovered':len(found),
            'unchanged_legacy':len(found)-len(changed),'required':required,'checked':checked}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True,type=Path)
    p.add_argument('--policy-dir',type=Path,default=Path(__file__).resolve().parent)
    a=p.parse_args()
    try:
        policy=a.policy_dir
        config=json.loads((policy/'config.json').read_text())
        baseline=json.loads((policy/'baseline.json').read_text())
        manifest=json.loads((a.root/'article-images.json').read_text())
        result=verify(a.root,config,baseline,manifest)
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:
        result={'ok':False,'errors':[str(exc)],'checked':[]}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['ok'] else 1
if __name__=='__main__':
    sys.exit(main())
