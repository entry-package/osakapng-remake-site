#!/usr/bin/env python3
"""Loopback-only preview with no indexing; directory listing is disabled."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

class PreviewHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('X-Robots-Tag','noindex, nofollow')
        self.send_header('Cache-Control','no-store')
        super().end_headers()
    def list_directory(self,path):
        self.send_error(404)
    def log_message(self,*args):pass

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--port',required=True,type=int);a=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),partial(PreviewHandler,directory=a.directory))
    print(f'Local preview: http://127.0.0.1:{a.port}/',flush=True)
    server.serve_forever()
