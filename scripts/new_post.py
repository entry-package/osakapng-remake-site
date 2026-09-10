"""Create a local news draft. This command never publishes."""
import argparse
import json
import re
from datetime import datetime
from html import escape
from pathlib import Path
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--slug',required=True);p.add_argument('--title',required=True);p.add_argument('--date',required=True,help='YYYY-MM-DD');p.add_argument('--body-file',required=True,help='UTF-8 HTML body');a=p.parse_args()
if not re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*',a.slug):p.error('Use lowercase ASCII words separated by hyphens for slug')
datetime.strptime(a.date,'%Y-%m-%d')
path='/blog/'+a.slug
source=json.loads((ROOT/'content/source-pages.json').read_text())
dest=ROOT/'content/posts'/(a.slug+'.json')
if dest.exists() or any(x['path']==path for x in source):p.error('Route already exists; edit its authored file explicitly')
body=Path(a.body_file).read_text();soup=BeautifulSoup(body,'html.parser')
if soup.select('script,iframe,form,input,style'):p.error('Use semantic content HTML only, without embeds or scripts')
if soup.select('img'):p.error('Register company-approved images in media-manifest before adding image HTML to the draft')
text=soup.get_text(' ',strip=True)
if not text:p.error('Article body is empty')
record={'url':'https://www.pngesports.com'+path,'path':path,'status':'authored','type':'article','title':a.title,'description':text[:150],'published_at':a.date+'T12:00:00+09:00','categories':[{'name':'NEWS'}],'tags':[],'hide_date':False,'cover':'','source_text':text,'body_html':body,'images':[],'links':[{'href':x['href'],'text':x.get_text(' ',strip=True)} for x in soup.select('a[href]')],'embeds':[]}
dest.parent.mkdir(exist_ok=True);dest.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(str(dest))
