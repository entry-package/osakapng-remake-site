"""Read a deployed static release over HTTPS and compare it with reviewed files."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--url', required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
base = args.url.rstrip('/') + '/'
if urlsplit(base).scheme != 'https':
    parser.error('Use the public HTTPS URL')
root = args.output.resolve()


def fetch(path, expected, status=200):
    url = urljoin(base, path)
    try:
        try:
            response = urlopen(Request(url, headers={'User-Agent': 'OsakaPNG-release-verification/1.0', 'Cache-Control': 'no-cache'}), timeout=25)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            final_url = response.geturl()
            code = response.code
        digest = hashlib.sha256(data).hexdigest()
        return {'path': path, 'status': code, 'final_url': final_url, 'sha256': digest,
                'pass': code == status and data == expected and final_url.startswith(base)}
    except Exception as error:
        return {'path': path, 'pass': False, 'error': type(error).__name__ + ': ' + str(error)}


jobs = []
fallback = (root / '404.html').read_bytes()
for file in sorted(root.rglob('*')):
    if not file.is_file() or file.name.startswith('.'):
        continue
    path = str(file.relative_to(root))
    request_path = path[:-len('index.html')] if file.name == 'index.html' else path
    jobs.append((request_path, file.read_bytes(), 200))
# Old links without a trailing slash must reach the same pages too.
for file in sorted(root.rglob('index.html')):
    path = str(file.parent.relative_to(root))
    if path != '.':
        # GitHub Pages resolves /404 to 404.html before /404/index.html.
        jobs.append((path, fallback if path == '404' else file.read_bytes(), 200))
for path in ['release-check-missing-20260914/', 'content/source-pages.json', 'scripts/build.py']:
    jobs.append((path, fallback, 404))
with ThreadPoolExecutor(max_workers=6) as pool:
    results = list(pool.map(lambda job: fetch(*job), jobs))
summary = {'checked_at': datetime.now(timezone.utc).isoformat(), 'base_url': base,
           'checks': len(results), 'passed': sum(row['pass'] for row in results),
           'failures': [row for row in results if not row['pass']], 'results': results}
args.report.parent.mkdir(parents=True, exist_ok=True)
args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({key: value for key, value in summary.items() if key != 'results'}, ensure_ascii=False, indent=2))
raise SystemExit(bool(summary['failures']))
