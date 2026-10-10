#!/usr/bin/env python3
"""Render reviewed international overviews; no runtime translation or external calls.

The four translations are parallel to the Japanese overview, not translated
archive articles. Links to untranslated material are explicitly labelled.
"""
import argparse
import hashlib
import html
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
LANGS = [('ja', '日本語'), ('en', 'English'), ('zh-Hans', '简体中文'), ('zh-Hant', '繁體中文'), ('ko', '한국어')]
SLUGS = {'ja': '', 'en': 'en', 'zh-Hans': 'zh-hans', 'zh-Hant': 'zh-hant', 'ko': 'ko'}
UI = {
 'en': ['Skip to content', 'Language / Site overview', 'About', 'Explore', 'Contact', 'Read in Japanese', 'Japanese articles and detailed source material are available from the links below.', 'Email us', 'Name', 'Email', 'Message', 'Prepare email', 'Your email app will open with a draft. Review it and send it there. This site does not send or store your message.', 'Open the Japanese contact form', 'Back to top', 'Detailed profile in Japanese', 'Related sites', 'Language versions', 'Japanese original', 'Email draft prepared. If your email app did not open, email the address shown above.', 'Please complete the required fields.'],
 'zh-Hans': ['跳至正文', '语言／网站介绍', '关于', '了解更多', '联系我们', '阅读日语原文', '以下链接提供日语新闻、详细介绍及原始资料。', '发送邮件', '姓名', '电子邮箱', '咨询内容', '生成邮件草稿', '将打开您的邮件应用并生成草稿。请在邮件应用中确认后发送。本网站不会发送或保存您的咨询内容。', '打开日语咨询表单', '返回顶部', '日语详细介绍', '相关网站', '语言版本', '日语原文', '邮件草稿已准备好。如果邮件应用没有打开，请向上方地址发送邮件。', '请填写所有必填项。'],
 'zh-Hant': ['跳至正文', '語言／網站介紹', '關於', '了解更多', '聯絡我們', '閱讀日文原文', '以下連結提供日文新聞、詳細介紹及原始資料。', '傳送電子郵件', '姓名', '電子郵件', '洽詢內容', '建立郵件草稿', '將開啟您的郵件應用程式並建立草稿。請在郵件應用程式中確認後寄出。本網站不會傳送或儲存您的洽詢內容。', '開啟日文洽詢表單', '回到頂端', '日文詳細介紹', '相關網站', '語言版本', '日文原文', '郵件草稿已準備好。如果郵件應用程式沒有開啟，請寄信至上方地址。', '請填寫所有必填欄位。'],
 'ko': ['본문 바로가기', '언어 / 사이트 안내', '소개', '더 알아보기', '문의', '일본어 원문 보기', '아래 링크에서 일본어 뉴스와 자세한 소개, 출처 자료를 확인할 수 있습니다.', '이메일 문의', '이름', '이메일', '문의 내용', '이메일 초안 만들기', '이메일 앱에 초안이 열립니다. 내용을 확인한 뒤 앱에서 보내 주세요. 이 사이트는 문의 내용을 전송하거나 저장하지 않습니다.', '일본어 문의 양식 열기', '맨 위로', '일본어 상세 소개', '관련 사이트', '언어별 안내', '일본어 원문', '이메일 초안을 준비했습니다. 이메일 앱이 열리지 않았다면 위 주소로 문의해 주세요.', '필수 항목을 모두 입력해 주세요.'],
}

def esc(value):
    return html.escape(str(value), quote=True)

def language_nav(current='ja'):
    label = '言語別サイト案内 / Language' if current == 'ja' else UI[current][1]
    links = ''.join(f'<a href="/{SLUGS[code] + "/" if SLUGS[code] else ""}" lang="{code}" hreflang="{code}"{chr(32) + "aria-current=\"page\"" if code == current else ""}>{name}</a>' for code, name in LANGS)
    return f'<nav class="site-languages" aria-label="{esc(label)}" data-site-languages><span>{esc(label)}</span><div>{links}</div></nav>'

def alternates(origin):
    return ''.join(f'<link rel="alternate" hreflang="{code}" href="{origin}/{SLUGS[code] + "/" if SLUGS[code] else ""}">' for code, _ in LANGS) + f'<link rel="alternate" hreflang="x-default" href="{origin}/">'

def render(data, locale, index, production=False):
    def t(value):
        return value[index] if isinstance(value, list) else value
    u = UI[locale]
    canonical = data['origin'] + '/' + SLUGS[locale] + '/'
    sections = []
    for section in data['sections']:
        cards = []
        for card in section.get('cards', []):
            image = f'<img src="{esc(card["image"])}" alt="" width="600" height="400" loading="lazy" decoding="async">' if card.get('image') else ''
            link = ''
            if card.get('href'):
                href = card['href'].replace('{locale}', SLUGS[locale])
                label = t(card.get('link', u[5]))
                link = f'<a class="text-link" href="{esc(href)}"{chr(32) + "hreflang=\"ja\"" if card.get("japanese", True) else ""}>{esc(label)} <span aria-hidden="true">↗</span></a>'
            cards.append(f'<article class="intl-card">{image}<div><h3>{esc(t(card["title"]))}</h3><p>{esc(t(card["text"]))}</p>{link}</div></article>')
        body = ''.join(f'<p>{esc(t(p))}</p>' for p in section.get('paragraphs', []))
        note = f'<p class="intl-note">{esc(t(section["note"]))}</p>' if section.get('note') else ''
        sections.append(f'<section class="intl-section" id="{esc(section["id"])}"><div class="section-title"><span>{esc(section.get("eyebrow", ""))}</span><h2>{esc(t(section["title"]))}</h2></div>{body}<div class="intl-grid">{"".join(cards)}</div>{note}</section>')
    archive = ''.join(f'<a href="{esc(item["href"])}" hreflang="ja">{esc(t(item["title"]))} <span aria-hidden="true">↗</span></a>' for item in data['originals'])
    related = ''.join(f'<a href="{esc(item["origin"])}/{SLUGS[locale]}/">{esc(item["name"])} <span aria-hidden="true">↗</span></a>' for item in data['related'])
    subject = t(data['subject'])
    email = data['email']
    mailto = 'mailto:' + email + '?subject=' + quote(subject)
    og_locale = {'en':'en_US', 'zh-Hans':'zh_CN', 'zh-Hant':'zh_TW', 'ko':'ko_KR'}[locale]
    return f'''<!doctype html>
<html lang="{locale}" prefix="og: https://ogp.me/ns#"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(t(data['title']))}</title><meta name="description" content="{esc(t(data['description']))}">
<link rel="canonical" href="{canonical}">{alternates(data['origin'])}
<meta property="og:type" content="website"><meta property="og:title" content="{esc(t(data['title']))}"><meta property="og:description" content="{esc(t(data['description']))}"><meta property="og:url" content="{canonical}"><meta property="og:locale" content="{og_locale}"><meta property="og:site_name" content="{esc(data['name'])}"><meta property="og:image" content="{data['origin']}{data['hero']}"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{esc(data['icon'])}"><link rel="stylesheet" href="/i18n/overview.css">
<meta name="color-scheme" content="light"><meta name="robots" content="{'index,follow' if production else 'noindex,nofollow'}">
<script type="application/ld+json">{json.dumps({'@context':'https://schema.org','@type':'WebPage','name':t(data['title']),'url':canonical,'inLanguage':locale,'isPartOf':{'@type':'WebSite','url':data['origin']+'/' ,'name':data['name']}},ensure_ascii=False).replace('<',chr(92)+'u003c')}</script>
</head><body class="intl-page theme-{data['theme']}" id="top">
<a class="intl-skip" href="#main">{esc(u[0])}</a>{language_nav(locale)}
<header class="intl-header"><a class="intl-brand" href="/{SLUGS[locale]}/">{esc(data['name'])}<span>{esc(t(data['brandline']))}</span></a><nav aria-label="{esc(u[3])}"><a href="#about">{esc(u[2])}</a><a href="#{esc(data['sections'][1]['id'])}">{esc(t(data['nav_explore']))}</a><a class="contact-link" href="#contact">{esc(u[4])} ↗</a></nav></header>
<main id="main"><section class="intl-hero"><div class="hero-image"><img src="{esc(data['hero'])}" alt="{esc(t(data['hero_alt']))}" width="1500" height="800" fetchpriority="high" decoding="async"></div><div class="hero-content"><p class="eyebrow">{esc(data['eyebrow'])}</p><h1>{esc(t(data['headline']))}</h1><p class="lead">{esc(t(data['lead']))}</p><a class="intl-button" href="#contact">{esc(t(data['cta']))} <span aria-hidden="true">↗</span></a></div></section>
{''.join(sections)}
<section class="intl-section originals" id="originals"><div class="section-title"><span>JAPANESE ORIGINALS</span><h2>{esc(t(data['archive_title']))}</h2></div><p>{esc(u[6])}</p><div class="original-links">{archive}</div></section>
<section class="intl-section intl-contact" id="contact"><div><span class="eyebrow">CONTACT</span><h2>{esc(t(data['contact_title']))}</h2><p>{esc(t(data['contact_text']))}</p><a class="email" href="{esc(mailto)}">{esc(email)}</a><p><a class="text-link" href="{esc(data['japanese_contact'])}" hreflang="ja">{esc(u[13])} ↗</a></p><p class="intl-note">{esc(t(data['contact_note']))}</p></div>
<form class="intl-mail" data-subject="{esc(subject)}" data-email="{esc(email)}"><label for="contact-name">{esc(u[8])} <span aria-hidden="true">*</span></label><input id="contact-name" name="name" autocomplete="name" maxlength="100" required><label for="contact-email">{esc(u[9])} <span aria-hidden="true">*</span></label><input id="contact-email" name="email" type="email" autocomplete="email" maxlength="254" required><label for="contact-message">{esc(u[10])} <span aria-hidden="true">*</span></label><textarea id="contact-message" name="message" rows="5" maxlength="1500" required></textarea><button class="intl-button" type="submit">{esc(u[11])} ↗</button><p class="intl-note">{esc(u[12])}</p><p role="status" aria-live="polite" data-mail-status data-ready="{esc(u[19])}"></p><noscript><p>{esc(u[7])}: <a href="{esc(mailto)}">{esc(email)}</a></p></noscript></form></section>
</main><footer class="intl-footer"><div><strong>{esc(data['name'])}</strong><p>{esc(u[16])}</p><div class="related-links">{related}</div></div><a href="#top">{esc(u[14])} ↑</a></footer>
<script src="/i18n/overview.js" defer></script></body></html>'''

def build(output, inject=False, production=False):
    data = json.loads((ROOT/'content/i18n/overviews.json').read_text())
    static = ROOT/'content/i18n/static'
    output.mkdir(parents=True, exist_ok=True)
    (output/'i18n').mkdir(exist_ok=True)
    for source in static.iterdir():
        if source.is_file():
            shutil.copy2(source, output/'i18n'/source.name)
    for i, (locale, _) in enumerate(LANGS[1:]):
        target = output/SLUGS[locale]/'index.html'
        target.parent.mkdir(exist_ok=True)
        target.write_text(render(data,locale,i,production))
    injected = 0
    if inject:
        for target in output.rglob('*.html'):
            if target.relative_to(output).parts[0] in SLUGS.values() or any(p.startswith('.') for p in target.relative_to(output).parts):
                continue
            value = target.read_text()
            if '<body' not in value or re.search(r'http-equiv=["\']refresh',value,re.I):
                continue
            if 'data-site-languages' not in value:
                value = re.sub(r'(<body\b[^>]*>)', lambda m:m[0]+language_nav(),value,count=1)
                value = value.replace('</head>','<link rel="stylesheet" href="/i18n/languages.css"></head>',1)
                injected += 1
            if target == output/'index.html' and 'hreflang="x-default"' not in value:
                value = value.replace('</head>',alternates(data['origin'])+'</head>',1)
            target.write_text(value)
    sitemap = output/'sitemap.xml'
    if sitemap.exists():
        value = sitemap.read_text()
        for locale,_ in LANGS[1:]:
            url = data['origin']+'/'+SLUGS[locale]+'/'
            if f'<loc>{url}</loc>' not in value:
                value = value.replace('</urlset>',f'<url><loc>{url}</loc></url></urlset>')
        sitemap.write_text(value)
    print(json.dumps({'locales':4,'japanese_pages_with_selector_added':injected,'output':str(output)}))

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--inject',action='store_true')
    parser.add_argument('--production',action='store_true',default=os.environ.get('PACKAGE_RELEASE')=='true')
    args=parser.parse_args()
    build(args.output.resolve(),args.inject,args.production)
