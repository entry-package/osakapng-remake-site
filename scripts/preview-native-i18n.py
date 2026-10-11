#!/usr/bin/env python3
"""Serve translated homepages over original local assets, on loopback only."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote,urlsplit
from bs4 import BeautifulSoup

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,overlay,original,**kwargs):
        self.overlay=Path(overlay).resolve();self.original=Path(original).resolve()
        super().__init__(*args,**kwargs)
    def translate_path(self,path):
        parts=Path(unquote(urlsplit(path).path).lstrip('/'))
        if '..' in parts.parts or any(x.startswith('.') for x in parts.parts):
            return str(self.overlay/'__missing__')
        for root in (self.overlay,self.original):
            candidate=root/parts
            if candidate.is_dir():candidate=candidate/'index.html'
            if candidate.is_file():return str(candidate)
        return str(self.overlay/'__missing__')
    def end_headers(self):
        self.send_header('X-Robots-Tag','noindex, nofollow')
        self.send_header('Cache-Control','no-store')
        super().end_headers()
    def list_directory(self,path):self.send_error(404)
    def do_POST(self):self.send_error(405,'Read-only local preview')
    def do_GET(self):
        path=Path(self.translate_path(self.path))
        if path.suffix=='.html' and path.is_file() and self.original in path.parents:
            soup=BeautifulSoup(path.read_text(),'html.parser')
            for node in soup.select('[data-site-languages],link[href="/i18n/languages.css"],script[src="/i18n/languages.js"],link[hreflang]'):node.decompose()
            # Secondary pages remain Japanese. Do not link to the superseded overviews.
            body=str(soup).encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        else:super().do_GET()
    def log_message(self,*args):pass

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--overlay',required=True);p.add_argument('--original',required=True);p.add_argument('--port',type=int,required=True);a=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),partial(Handler,overlay=a.overlay,original=a.original))
    print(f'Preview: http://127.0.0.1:{a.port}/en/',flush=True);server.serve_forever()
