"""Build a dependency-light, portable static PNG site from captured public content.

Default builds are private review builds (noindex). Production requires --production.
No publication, form submission, remote scripts or service configuration occurs here.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from html import escape as e
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist'
ORIGIN = 'https://www.pngesports.com'
PAGES = json.loads((ROOT / 'content/source-pages.json').read_text())
# New company-authored articles stay separate from the immutable migration source.
for authored in sorted((ROOT/'content/posts').glob('*.json')):
    record=json.loads(authored.read_text())
    if record['path'] in {p['path'] for p in PAGES}:
        raise ValueError('Authored article would overwrite a captured route: '+record['path'])
    PAGES.append(record)
BY_PATH = {p['path']: p for p in PAGES}
MEDIA = json.loads((ROOT / 'content/media-manifest.json').read_text())
THUMBNAIL_ASSETS = json.loads((ROOT / 'content/thumbnail-assets.json').read_text())
THUMBNAIL_OVERRIDES = json.loads((ROOT / 'content/thumbnail-overrides.json').read_text())
MEMBER_UPDATES = json.loads((ROOT / 'content/member-updates.json').read_text())
LINK_CORRECTIONS = json.loads((ROOT / 'content/link-corrections.json').read_text())['links']
ARTICLES = [p for p in PAGES if p['type'] == 'article']
MEMBERS = [BY_PATH[path] for path in dict.fromkeys(urlsplit(a['href']).path for a in BY_PATH['/member']['links'] if '/blog/' in a['href'])]
MEMBER_PATHS = {p['path'] for p in MEMBERS}
CURRENT_MEMBERS = [p for p in MEMBERS if MEMBER_UPDATES.get(p['path'], {}).get('membership_state') != 'departed']
NEWS = sorted((p for p in ARTICLES if p['path'] not in MEMBER_PATHS), key=lambda p: p['published_at'], reverse=True)
TITLE_FIXES = {'/blog/adc014909c5': '美月姫 脱退のお知らせ', '/blog/f2a43fc69c2': 'CoD部門 NevvtonX選手 脱退のお知らせ'}
ROSTER_COPY = [
    ('Call of Duty / Battlefield', 'YouTubeとTwitchを中心に、FPSを配信。'),
    ('YouTube / ゲーム動画', 'マリオカートやYouTube Shortsでも活動中。'),
    ('Twitch / VALORANT', 'リスナーとの交流を大切にする、長時間配信が人気。'),
    ('ゲーム / コミュニティ', '幅広いゲームを楽しむ、ストリートファイター6のマスター。'),
    ('FPS / ゲーム配信', 'R6S大会の優勝経験を持ち、APEX大会の主催も。'),
    ('雑談 / コラボ', 'ゲームも雑談も、視聴者との近い距離感が魅力。'),
    ('配信 / エンターテインメント', '配信を見る側から、楽しさを届ける側へ。'),
    ('イベント / 配信', 'イベントを支える経験を、配信の楽しさにつなげる。'),
]
SOCIALS = [('X', 'https://x.com/PNGesports'), ('YouTube', 'https://www.youtube.com/@osakapng'), ('SUZURI', 'https://suzuri.jp/Osaka_PNG')]
CORRECTIONS = []
ROUTES = {}


def title(p):
    return TITLE_FIXES.get(p['path'], p['title'])


def dated(p):
    return datetime.fromisoformat(p['published_at']).astimezone(ZoneInfo('Asia/Tokyo')).strftime('%Y.%m.%d')


def link(target, current):
    u = urlsplit(target)
    if u.scheme in {'http', 'https'} and u.hostname not in {'www.pngesports.com', 'pngesports.com'}:
        return target
    if u.scheme and u.scheme not in {'http', 'https'}:
        return target if u.scheme in {'mailto', 'tel'} else '#'
    path = u.path or current
    if not path.startswith('/'):
        path = urljoin(current.rstrip('/') + '/', path)
    # Preserve query/fragment, including legacy categoryId links.
    relative = os.path.relpath(path.lstrip('/') or '.', current.lstrip('/') or '.')
    if not Path(path).suffix:
        relative = ('./' if relative == '.' else relative + '/')
    return urlunsplit(('', '', relative, u.query, u.fragment))


def asset(path, current):
    return link('/' + path, current)


def media(url, current):
    url = url if url in MEDIA else urljoin(ORIGIN, url)
    row = MEDIA.get(url)
    if not row or row['status'] != 'ok':
        raise ValueError('Unmirrored content image: ' + url)
    return asset(row['local'], current)


def cover_asset(path, source_cover):
    """Editorial images replace only reviewed missing covers, never source bodies."""
    override = THUMBNAIL_OVERRIDES.get(path)
    if override:
        if source_cover != override['source_cover']:
            raise ValueError('Source cover changed; review the thumbnail override: ' + path)
        return THUMBNAIL_ASSETS[override['asset']]['local']
    if not source_cover:
        return 'assets/hero-logo.png'
    return MEDIA[source_cover]['local']


def anchor(url, text, current, cls=''):
    return f'<a class="{cls}" href="{e(link(url, current), quote=True)}">{e(text)}</a>'


def reviewed_link_correction(url, path):
    correction = LINK_CORRECTIONS.get(url)
    return correction if correction and path in correction['occurrences'] else None


def clean_body(p):
    soup = BeautifulSoup(p['body_html'], 'html.parser')
    for bad in soup.select('script,style,noscript,form,input,button'):
        bad.decompose()
    for tag in list(soup.find_all(True)):
        if tag.name == 'a':
            original = urljoin(p['url'], tag.get('href', ''))
            correction = reviewed_link_correction(original, p['path'])
            if correction and correction['action'] == 'unlink':
                tag.name = 'span'
                tag.attrs = {'class': 'historical-link', 'data-original-href': original,
                             'title': '掲載当時のリンク（現在の移転先未確認）'}
                continue
            target = correction['target'] if correction else original
            tag.attrs = {'href': link(target, p['path'])}
            if urlsplit(target).scheme in {'http', 'https'} and urlsplit(target).hostname not in {'www.pngesports.com','pngesports.com'}:
                tag['rel'] = 'noopener noreferrer'
        elif tag.name == 'img':
            src = tag.get('data-src') or tag.get('src')
            alt = tag.get('alt', '')
            if not alt or alt in {'Section image', 'Image'}:
                alt = title(p) + ' 掲載画像'
            dimensions = {a: tag[a] for a in ('width', 'height') if str(tag.get(a, '')).isdigit()}
            tag.attrs = {'src': media(src, p['path']), 'alt': alt, 'loading': 'lazy', 'decoding': 'async', **dimensions}
        elif tag.name in {'h1','h2','h3','h4','h5','h6','p','strong','em','b','i','u','br','ul','ol','li','blockquote','hr','table','tr','td','th','thead','tbody','figure','figcaption','sup','sub','s'}:
            tag.attrs = {}
            if tag.name == 'h1':
                tag.name = 'h2'
        else:
            tag.unwrap()
    # Source Strikingly headings sometimes wrap p elements. Normalize valid HTML.
    for h in soup.select('h2,h3,h4,h5,h6'):
        for ptag in h.select('p'):
            ptag.unwrap()
    return str(soup)


def section_head(kicker, heading, current, target=None, label='すべて見る'):
    more = anchor(target, label + ' →', current, 'text-link') if target else ''
    return f'<div class="section-head"><div><p class="eyebrow">{kicker}</p><h2>{heading}</h2></div>{more}</div>'


def talent_cards(current):
    cards = []
    for p, (tag, description) in zip(MEMBERS, ROSTER_COPY):
        # Use the original public portrait, not an inferred talent category.
        portrait = p['images'][0]['url']
        update = MEMBER_UPDATES.get(p['path'],{})
        if update.get('membership_state') == 'departed':
            continue
        description = update.get('summary',description)
        socials = ' '.join(anchor(a['href'], a['text'], current) for a in update.get('additional_links',[])+p['links'])
        badge = '<span class="member-status">'+e(update['status'])+'</span>' if update.get('status') else ''
        cards.append(f'<article class="talent-card"><a class="portrait" href="{e(link(p["path"], current))}"><img src="{e(media(portrait, current))}" alt="{e(title(p))}" width="600" height="650" loading="lazy"></a><div class="talent-info"><p class="tagline">{e(tag)}</p><h3>{anchor(p["path"], title(p), current)}</h3>{badge}<p>{e(description)}</p><div class="social-links" aria-label="{e(title(p))}の配信・SNS">{socials}</div>{anchor(p["path"], 'プロフィール →', current, 'text-link')}</div></article>')
    return '<div class="talent-grid">' + ''.join(cards) + '</div>'


def news_card(p, current, featured=False):
    desc = p['source_text']
    short = desc[:110].strip() + ('…' if len(desc) > 110 else '')
    generated = p['path'] in THUMBNAIL_OVERRIDES
    local_cover = cover_asset(p['path'], p['cover'])
    dimensions = THUMBNAIL_ASSETS[THUMBNAIL_OVERRIDES[p['path']]['asset']] if generated else {'width':720,'height':400}
    cover = f'<img src="{e(asset(local_cover, current))}" alt="" width="{dimensions["width"]}" height="{dimensions["height"]}" loading="lazy" decoding="async">'
    cls = 'news-card news-card--generated' if generated else 'news-card'
    data = e((title(p) + ' ' + desc).lower(), quote=True)
    return f'<article class="{cls}" data-news data-year="{dated(p)[:4]}" data-search="{data}"><a href="{e(link(p["path"], current))}" class="news-cover" tabindex="-1" aria-hidden="true">{cover}</a><div class="news-copy"><p class="meta"><time datetime="{dated(p).replace(".","-")}">{dated(p)}</time><span>NEWS</span></p><h3>{anchor(p["path"], title(p), current)}</h3><p class="excerpt">{e(short)}</p></div></article>'


def related(current, all_stories=False):
    records = json.loads((ROOT/'content/related-sources.json').read_text())
    selected = json.loads((ROOT/'content/stories.json').read_text())
    items = []
    for story in selected:
        url = 'https://www.package-inc.com/blog/' + story['slug']
        source = next(p for p in records if p['url'] == url)
        items.append((dated(source), story['title'], story['summary'], url))
    items.sort(reverse=True)
    if not all_stories: items = items[:3]
    return '<div class="related-grid">' + ''.join(f'<article><p class="meta">{date} · PACkage公式</p><h3>{anchor(url, name + " ↗", current)}</h3><p>{e(copy)}</p></article>' for date,name,copy,url in items) + '</div>'


def page_intro(kicker, heading, description):
    return f'<section class="page-intro container"><p class="eyebrow">{kicker}</p><h1>{heading}</h1><p>{description}</p></section>'


def home():
    c = '/'
    return f'''<section class="arena-hero" aria-labelledby="hero-title"><div class="arena-grid"><div class="arena-copy"><p class="arena-kicker"><span>OSAKA IS OUR HOME.</span><span>GAME IS OUR LANGUAGE.</span></p><h1 id="hero-title">大阪から、<br><span>遊びでつながる。</span></h1><p class="arena-lead">本気の一戦も、いつもの配信も。<br>おもろい瞬間を、いっしょに。</p><div class="actions">{anchor('/member','メンバー・配信を見る ↗',c,'button primary')}{anchor('/newsevents','ニュースを読む →',c,'button outline')}</div><p class="arena-signature">楽しいを共有する。<span>OsakaPNG</span></p></div><div class="arena-visual"><picture><source type="image/webp" srcset="{asset('assets/takopen-osaka-soft-hero.webp',c)}"><img class="arena-city" src="{asset('assets/takopen-osaka-soft-hero.png',c)}" alt="ぬいぐるみ風のタコペンが、小さな地図を持って大阪の街をさんぽするイラスト" width="1536" height="1024" fetchpriority="high"></picture></div></div><div class="play-strip" aria-label="OsakaPNGの活動"><span>OSAKA PNG</span><span>GAME</span><span>STREAMING</span><span>COMMUNITY</span><a href="#news">LATEST NEWS ↘</a></div></section>
<section id="news" class="section container">{section_head('NEWS & EVENTS','OsakaPNGの最新情報',c,'/newsevents','過去のニュースも読む')}<div class="news-grid">{''.join(news_card(p,c) for p in NEWS[:3])}</div></section>
<section id="talents" class="section soft"><div class="container">{section_head('MEMBER','あなたの「好き」に出会おう。',c,'/member','メンバー一覧')}<p class="section-lead">ゲーム、雑談、コラボ。個性豊かなメンバーの配信へ。</p>{talent_cards(c)}</div></section>
<section id="about" class="section container about-grid"><div><p class="eyebrow">ABOUT OSAKAPNG</p><h2>楽しいを、<br>もっと近くに。</h2><img class="about-mark" src="{asset('assets/brand-mark.png',c)}" alt="" width="100" height="100" loading="lazy"></div><div class="prose"><p>OsakaPNGは、大阪を拠点に活動するタレントチーム。eスポーツ、ゲーム、配信、音楽など、さまざまな「楽しい」を共有します。</p><p>2023年、PNG esportsからOsakaPNGへ。オンラインとリアルの両方で、地元のコミュニティとつながりながら活動しています。</p><p>たこ焼きとペンギンを組み合わせた「タコヤキペンギン」が目印です。</p>{anchor('/about','OsakaPNGの歩みを見る →',c,'text-link')}</div></section>
<section id="goods" class="section dark"><div class="container">{section_head('GOODS & FOLLOW','配信の外でも、一緒に。',c)}<div class="enjoy-grid"><article><span class="large-number">01</span><h3>オリジナルグッズ</h3><p>OsakaPNGのグッズをSUZURIでチェック。</p>{anchor('https://suzuri.jp/Osaka_PNG','SUZURIで見る ↗',c,'button light')}</article><article><span class="large-number">02</span><h3>LINEスタンプ</h3><p>タコヤキペンギンの8種類のスタンプ。</p>{anchor('https://store.line.me/stickershop/product/23122447/ja','LINE STOREで見る ↗',c,'button light')}</article><article><span class="large-number">03</span><h3>公式チャンネル</h3><p>配信やイベントの情報を、公式SNSから。</p><div class="social-links">{''.join(anchor(url,name+' ↗',c) for name,url in SOCIALS[:2])}</div></article></div></div></section>
<section class="section container">{section_head('MORE STORIES','PACkageから届く活動情報',c,'/stories','活動情報をすべて見る')}<p class="section-lead">運営会社の公式サイトに掲載された、OsakaPNGにまつわるお知らせ。日付は当時の掲載日です。</p>{related(c)}</section>
<section class="section soft"><div class="container">{section_head('SPONSORS','OsakaPNGを応援するパートナー',c)}<div class="sponsor-row">{''.join(f'<a href="{url}"><img src="{asset("assets/"+file,c)}" alt="{name}" width="260" height="110" loading="lazy"></a>' for name,file,url in [('AOC','sponsor-aoc.png','https://jp.aoc.com'),('ふもっふのおみせ','sponsor-fumo.png','https://fumo-shop.com'),('GMOペパボ','sponsor-pepabo.png','https://pepabo.com')])}</div></div></section>
<section id="contact" class="section container contact-strip"><div><p class="eyebrow">CONTACT</p><h2>OsakaPNGへのお問い合わせ</h2><p>出演、コラボ、取材、スポンサーのご相談はこちら。</p></div>{anchor('/contact','お問い合わせへ →',c,'button primary')}</section>'''


def news_index(c):
    years = sorted({dated(p)[:4] for p in NEWS}, reverse=True)
    controls = '<form class="archive-controls" role="search"><label>キーワード<input id="news-search" type="search" placeholder="メンバー名・イベント名など" autocomplete="off"></label><label>掲載年<select id="news-year"><option value="">すべての年</option>' + ''.join(f'<option>{y}</option>' for y in years) + '</select></label><button type="reset" class="button outline">条件をリセット</button></form>'
    return page_intro('NEWS & EVENTS','ニュース・イベント','加入のお知らせから、過去の大会・イベントまで。OsakaPNGとPNG esportsの活動の記録。') + f'<section class="container archive">{controls}<p class="results" role="status" aria-live="polite"><span id="news-count">{len(NEWS)}</span>件の記事</p><p class="archive-note">記事中の所属・募集・開催情報は掲載当時のものです。現在の所属は{anchor("/member","メンバー一覧",c)}をご覧ください。</p><div class="news-grid archive-grid">' + ''.join(news_card(p,c) for p in NEWS) + '</div><p id="empty-results" hidden>該当する記事がありません。キーワードや掲載年を変えてお試しください。</p></section>'


def article_page(p):
    c = p['path']; is_member = c in MEMBER_PATHS
    update = MEMBER_UPDATES.get(c,{})
    departed = update.get('membership_state') == 'departed'
    category = 'FORMER MEMBER' if departed else ('MEMBER' if is_member else 'NEWS & EVENTS')
    back = '/member' if is_member else '/newsevents'
    copy = clean_body(p)
    prefix = f'<nav class="breadcrumb container" aria-label="パンくず">{anchor("/","HOME",c)}<span>/</span>{anchor(back,category,c)}</nav>'
    date = '' if is_member else f'<time datetime="{dated(p).replace(".","-")}">{dated(p)}</time>'
    note = '' if is_member else '<p class="archive-note">この記事は掲載当時の情報です。募集・イベントの開催状況や所属情報は、現在と異なる場合があります。</p>'
    update = MEMBER_UPDATES.get(c,{})
    if update:
        extra_links = ' '.join(anchor(a['href'],a['text'],c) for a in update.get('additional_links',[]))
        source_link = anchor(update['source_urls'][0],'本人の公開プロフィール ↗',c,'text-link') if update.get('source_urls') and not departed else ''
        status = '<strong class="member-status">'+e(update['status'])+'</strong>' if update.get('status') else ''
        note = '<aside class="profile-update">'+status+'<p>'+e(update['notice'])+'</p><div class="social-links">'+extra_links+'</div>'+source_link+'</aside>'
    if any(row['action'] == 'unlink' and c in row['occurrences'] for row in LINK_CORRECTIONS.values()):
        note += '<p class="archive-note" data-link-maintenance>掲載当時の外部リンクのうち、現在の移転先を確認できないものは文字のみで掲載しています。</p>'
    neighbors = ''
    if not is_member:
        i = NEWS.index(p)
        neighbors = '<nav class="article-neighbors" aria-label="前後の記事">' + (anchor(NEWS[i+1]['path'], '← ' + title(NEWS[i+1]),c) if i+1 < len(NEWS) else '<span></span>') + (anchor(NEWS[i-1]['path'],title(NEWS[i-1])+' →',c) if i else '') + '</nav>'
    return prefix + f'<article class="article-shell {"profile" if is_member else ""}"><header><p class="eyebrow">{category} {date}</p><h1>{e(title(p))}</h1>{note}</header><div class="article-body" data-source-body>{copy}</div>{neighbors}<div class="article-return">{anchor(back,"メンバー一覧へ" if is_member else "ニュース一覧へ",c,"button outline")}</div></article>'


def about(c):
    return page_intro('ABOUT','楽しいを共有する。','大阪から、ゲーム・eスポーツ・配信・音楽を通じて、人と人がつながる場所へ。') + f'<section class="section container about-grid"><img class="history-logo" src="{asset("assets/hero-logo.png",c)}" alt="OsakaPNG" width="500" height="500"><div class="prose"><h2>OsakaPNGについて</h2><p>株式会社PACkageが運営する、大阪を拠点としたタレントチームです。eスポーツの競技活動から広がり、VTuberやYouTuberなど、さまざまなタレントの活動を届けています。</p><p>オンラインでの配信と、リアル会場でのイベント。両方を通じて、地元のコミュニティと一緒に楽しさを育てていきます。</p><p>マスコットの「タコヤキペンギン」は、大阪のたこ焼きと、PNGの由来であるペンギンを組み合わせたデザインです。</p>{anchor("/blog/e-pngesports-osakapng","2023年のリブランディング発表を読む →",c,"text-link")}</div></section><section class="section soft"><div class="container">{section_head("OUR STORY","これまでと、これから。",c)}<ol class="timeline"><li><strong>2018</strong><div><h3>PNG esportsとしての活動</h3><p>PACkageの設立とともに、大阪を拠点に活動を展開。</p>{anchor("/newsevents?year=2018","2018年の記事を見る →",c)}</div></li><li><strong>2023</strong><div><h3>OsakaPNGへリブランディング</h3><p>地元大阪を名前に冠し、ゲームや音楽など、幅広い「楽しい」を共有するチームへ。</p></div></li><li><strong>NOW</strong><div><h3>配信から、リアルのイベントへ</h3><p>個性豊かなメンバーと一緒に、新しい出会いや楽しさを届けます。</p>{anchor("/member","現在のメンバーを見る →",c)}</div></li></ol></div></section><section class="section container">{section_head("RELATED STORIES","もっと知るOsakaPNG",c,"/stories","活動情報をすべて見る")}{related(c)}</section><section id="operator" class="section container operator"><div class="operator-brand"><img src="{asset("assets/package-logo.png",c)}" alt="PACkage — Players Audience Creators" width="500" height="132" loading="lazy"></div><div><p class="eyebrow">OPERATED BY</p><h2>運営会社</h2><p>株式会社PACkage</p>{anchor("https://www.package-inc.com/","会社の公式サイト ↗",c)}</div></section>'


def contact(c):
    return page_intro('CONTACT','お問い合わせ','出演・コラボ・イベント・取材・スポンサーなどのご相談を承ります。') + f'''<section class="container contact-layout"><div class="prose"><h2>OsakaPNG 運営窓口</h2><p>株式会社PACkage</p><p><a href="mailto:info@package-inc.com">info@package-inc.com</a></p><p>下の項目を入力すると、ご利用のメールアプリで宛先・件名・本文を準備できます。内容を確認して、メールアプリから送信してください。</p><p>メールアプリを使わない場合は、「本文をコピー」して、普段お使いのメールサービスから上記の宛先へお送りください。</p></div><form id="contact-form"><label>ご相談の種類<select name="topic" required><option value="">選択してください</option><option>出演・イベント</option><option>配信・動画コラボ</option><option>取材・メディア掲載</option><option>スポンサー・提携</option><option>その他</option></select></label><label>お名前<input name="name" autocomplete="name" required maxlength="100"></label><label>メールアドレス<input type="email" name="email" autocomplete="email" required maxlength="254"></label><label>お問い合わせ内容<textarea name="message" rows="8" required maxlength="5000"></textarea></label><div class="actions"><button class="button primary" type="submit">メールアプリで送信する</button><button class="button outline" id="copy-message" type="button">本文をコピー</button></div><p class="form-note" role="status" aria-live="polite">このページから直接メールは送信されません。入力内容はこのサイトには保存されません。</p><noscript><p>入力補助にはJavaScriptを使用します。直接 info@package-inc.com へお問い合わせください。</p></noscript></form></section>'''


def policy(c):
    return page_intro('SITE INFORMATION','このサイトのCookieについて','ウェブサイトでの情報の取り扱いについて。') + '<section class="container prose policy"><h2>このサイトで使用する機能</h2><p>このサイトは静的なページで構成されており、アクセス解析、広告配信、SNSの埋め込み、会員ログインのためのCookieを設定していません。</p><h2>お問い合わせ</h2><p>お問い合わせページの入力内容は、メールアプリへの受け渡し、または本文のコピーにのみ利用します。このサイトのサーバーには送信・保存しません。</p><h2>外部サービス</h2><p>SNS、動画配信、ショップなどのリンク先は外部サービスです。移動後の情報の取り扱いは、それぞれのサービスのポリシーをご確認ください。</p><h2>運営</h2><p>株式会社PACkage<br><a href="mailto:info@package-inc.com">info@package-inc.com</a></p></section>'


def render(path, heading, body, description='', cover='', production=False):
    canonical = ORIGIN + (path if path != '/' else '/')
    css = asset('styles.css', path); js = asset('script.js', path)
    nav = ''.join(anchor(url,name,path) for url,name in [('/member','MEMBER'),('/newsevents','NEWS'),('/about','ABOUT'),('/#goods','GOODS'),('/contact','CONTACT')])
    footer = ''.join(anchor(url,name,path) for name,url in SOCIALS)
    og = ORIGIN + '/' + cover_asset(path, cover)
    breadcrumb = {'@context':'https://schema.org','@type':'Organization','name':'OsakaPNG','url':ORIGIN,'sameAs':[u for _,u in SOCIALS[:2]],'parentOrganization':{'@type':'Organization','name':'株式会社PACkage','url':'https://www.package-inc.com/'}}
    p = BY_PATH.get(path)
    structured = breadcrumb
    if p and p['type'] == 'article' and path not in MEMBER_PATHS:
        structured = {'@context':'https://schema.org','@type':'NewsArticle','headline':heading,'datePublished':p['published_at'],'image':og,'mainEntityOfPage':canonical,'publisher':breadcrumb}
    robots = 'index,follow' if production and path != '/404' else 'noindex,nofollow'
    template = (ROOT / 'index.html').read_text()
    values = {'TITLE':e(heading + ' | OsakaPNG'), 'DESCRIPTION':e(description or '大阪から「楽しいを共有する」。OsakaPNGのメンバー、配信、ニュース、イベント、グッズ情報。',quote=True),'CANONICAL':e(canonical),'OG_IMAGE':e(og),'ROBOTS':robots,'CSS':css,'JS':js,'HOME':link('/',path),'BRAND':asset('assets/brand-mark.png',path),'NAV':nav,'BODY':body,'FOOTER':footer,'CONTACT':link('/contact',path),'POLICY':link('/pages/cookie-policy',path),'STRUCTURED':json.dumps(structured,ensure_ascii=False).replace('<','\\u003c')}
    values['DESIGN_CSS'] = asset('osaka-theme.css', path)
    values['PAGE_CLASS'] = 'home-page' if path == '/' else 'inner-page'
    for key,value in values.items():
        template = template.replace('{{'+key+'}}',value)
    location = OUT / path.lstrip('/') / 'index.html'
    location.parent.mkdir(parents=True,exist_ok=True)
    location.write_text(template)
    ROUTES[path] = {'file':str(location.relative_to(OUT)),'title':heading,'source':p['url'] if p else None}


def main():
    global OUT
    args = argparse.ArgumentParser()
    args.add_argument('--production', action='store_true')
    args.add_argument('--output', type=Path, default=OUT)
    args.add_argument('--base-path', default='', help='Hosting subdirectory, used by the fallback 404 page')
    opt = args.parse_args()
    OUT = opt.output.resolve()
    base_path = '/' + opt.base_path.strip('/') if opt.base_path.strip('/') else ''
    if base_path and not re.fullmatch(r'/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*', base_path):
        args.error('--base-path must be a URL directory path')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / '.nojekyll').write_text('')
    shutil.copytree(ROOT/'assets',OUT/'assets',dirs_exist_ok=True)
    for file in ('styles.css','osaka-theme.css','script.js'):
        shutil.copyfile(ROOT/file,OUT/file)
    def write(path,heading,body,**kw): render(path,heading,body,production=opt.production,**kw)
    write('/','大阪から、楽しいを共有する。',home())
    for path in ['/member','/blog/categories/member-1155238']:
        write(path,'所属メンバー',page_intro('MEMBER','あなたの「好き」に出会おう。','ゲーム、雑談、コラボ。気になるメンバーのプロフィールから、配信やSNSへ。')+'<section class="container section">'+talent_cards(path)+'</section>')
    for path in ['/newsevents','/_blog','/blog/categories/news-1175894','/blog/categories']:
        write(path,'ニュース・イベント',news_index(path))
    for p in ARTICLES:
        description = MEMBER_UPDATES.get(p['path'],{}).get('summary',p['description'])
        write(p['path'],title(p),article_page(p),description=description,cover=p['cover'])
    write('/about','OsakaPNGについて',about('/about'))
    write('/contact','お問い合わせ',contact('/contact'))
    write('/stories','PACkage公式の活動情報',page_intro('MORE STORIES','OsakaPNGにまつわる活動情報','運営会社PACkageの公式サイトから。記事の出演者・所属・開催概要は、それぞれの掲載当時の情報です。')+'<section class="container section">'+related('/stories',True)+'</section>')
    write('/pages/cookie-policy','Cookieについて',policy('/pages/cookie-policy'))
    write('/404','ページが見つかりません',page_intro('404','ページが見つかりません','URLをご確認いただくか、メンバー一覧・ニュースからお探しください。')+'<section class="container section"><a class="button primary" href="/">トップページへ</a></section>')
    notfound=BeautifulSoup((OUT/'404/index.html').read_text(),'html.parser')
    for tag in notfound.select('a[href],link[href],script[src],img[src]'):
        attr='href' if tag.has_attr('href') else 'src'
        value=tag[attr]
        if not urlsplit(value).scheme and not urlsplit(value).netloc:
            u=urlsplit(urljoin(ORIGIN+'/404/',value))
            tag[attr]=urlunsplit(('', '', base_path + u.path, u.query, u.fragment))
    (OUT/'404.html').write_text(str(notfound))
    urls = ''.join('<url><loc>'+e(ORIGIN+path)+'</loc></url>' for path in ROUTES if path!='/404')
    (OUT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+urls+'</urlset>')
    (OUT/'robots.txt').write_text('User-agent: *\n'+('Allow: /\nSitemap: '+ORIGIN+'/sitemap.xml\n' if opt.production else 'Disallow: /\n'))
    (ROOT/'content/route-manifest.json').write_text(json.dumps(ROUTES,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'content/editorial-decisions.json').write_text(json.dumps({'title_corrections':TITLE_FIXES,'body_policy':'All 101 original article/profile body texts and images retained. Reviewed link corrections are recorded in content/link-corrections.json; original destinations remain in source-pages.json. Use publication dates and separate page notes for temporal context. Thumbnail wording reads as an announcement at the original publication date; no retrospective labels inside images.','profile_copy':'Current roster excludes departed members. Owner confirmed 隣ノあおこ departure on 2026-09-13; original profile body retained with a departure notice. Other summaries use captured public profiles.','cookie_policy':'Platform-specific Strikingly policy replaced with implementation-specific text; original retained in source-pages.json.','contact':'Static mail composer and copy fallback; never show an unverified delivery-success message.','related_news':'Eight official company articles linked with original publication dates, selected from eleven reviewed articles. No unrelated neighboring posts imported.','not_proven':'All disappeared content from pre-existing esportspng.com and unpublished/internal/SNS-only information remains unverified.'},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'routes':len(ROUTES),'articles':len(ARTICLES),'news':len(NEWS),'current_members':len(CURRENT_MEMBERS),'preserved_profiles':len(MEMBERS),'production':opt.production}))


if __name__ == '__main__':
    main()
