# OsakaPNG 自社管理サイト（切替前の確認版）

Strikinglyの公開ページ109件から、記事・プロフィール101件を元のURLで再構築した静的サイトです。本文・記事内リンク・画像を保全し、現在の公開プロフィールから不足情報を補っています。公開・DNS変更・Strikingly解約は実施していません。最終GO前の確認版です。

## 構成

- `index.html`：共通HTMLテンプレート。
- `styles.css` / `script.js`：表示、メニュー、記事検索、問い合わせメールの作成補助。
- `scripts/build.py`：静的ページの生成。出力は `dist/`。通常は全ページ noindex。
- `content/source-pages.json`：2026-09-10時点の公開原文。加工前の本文・リンク・画像・ハッシュを保存。社内文書は含めない。
- `content/member-updates.json`：本人の公開プロフィールに基づく現在情報の追補。原文を消さず、別枠で表示する。
- `content/stories.json` / `related-sources.json`：PACkage公式の記事11件の調査と、PNGに直接関連する8件の掲載案内。
- `content/posts/*.json`：新規ニュースの原稿。取得原文とは分けて管理する。
- `content/media-manifest.json`：画像148参照とローカル保存先・SHA-256。実画像147参照を取得、空のプラットフォーム用カバー1参照は既存ロゴへ置換。
- `content/route-manifest.json`：旧URLから出力ファイルへの対応表。
- `content/editorial-decisions.json`：表題補正・Cookie説明更新などの編集判断。
- `content/verification.json` / `browser-verification.json` / `external-link-verification.json`：検証結果。
- `.audit/`：公開HTMLの取得キャッシュ、独立ブラウザーの一時プロファイル、確認画像。Git・配布対象外。

## 開発

Python 3.11以上と `beautifulsoup4` を使用します。JSの本番ライブラリー、CDN、認証、ビルド時の外部サービスは不要です。

```sh
python3 scripts/build.py
python3 -m http.server 8766 --bind 127.0.0.1 --directory dist
```

ローカル確認先: http://127.0.0.1:8766/

取得原文を更新する場合は、差分を先に確認してください。サイトの現行表示が社内の活動状況より古い場合があります。`capture.py` は既存キャッシュを再利用します。別日の再取得は旧 `.audit/source/` を日付付きで退避してから行い、旧 `source-pages.json` と比較してください。原文と追補を混ぜない設計です。

```sh
python3 scripts/capture.py
python3 scripts/media.py
python3 scripts/build.py
python3 scripts/verify.py
node --check script.js
```

`browser_check.py` はMacのChromeのheadless CLIを使用し、ユーザーのログイン済みプロファイルを使わずにローカルサイトだけを確認します。先に上記HTTPサーバーを起動します。6種類の画面幅、文字拡大、検索・リセット、モバイルメニュー、問い合わせの入力検証・本文作成を確認します。メールは送信しません。

## ニュース更新

`new_post.py` でUTF-8 HTMLの本文からローカル原稿を作れます。既存記事と同じURLの上書きは拒否します。

```sh
python3 scripts/new_post.py --slug example-news --title '記事タイトル' --date 2026-09-10 --body-file /path/to/body.html
python3 scripts/build.py
python3 scripts/verify.py
```

本文には見出し・段落・リスト・リンクを使用します。画像は権利と内容を確認してローカル保存し、マニフェストに登録します。記事はローカルで確認し、Gitの小さい差分としてレビューできます。取得元の101件は更新原稿で上書きしません。投稿の削除はせず、必要に応じて訂正記事や非表示の明示的な管理で対応します。

## 問い合わせ

本人の公開窓口 `info@package-inc.com` 宛てのメールを作る方式です。メールアプリ起動と、Webメール向け本文コピーに対応します。このサイトからサーバー送信はせず、入力内容も保存しません。送信成功を装う表示はありません。実配送は今回未検証です。Web上で送信を完結させるサーバーフォームは未接続であり、その方式を採る場合は移行先ホスティングの確定後に別途実装・配送確認が必要です。

## 切替の保留事項

- 本番ホスティング、DNS・HTTPS・www/apex・メール用DNSの確認。最終GOまでは変更しない。
- Strikinglyの下書き・非公開記事と、取得できなかった旧 `esportspng.com` の消失内容。今回の「欠落ゼロ」は取得済み101本文に限る。
- 現行サイト掲載者の現在の所属・掲載区分。公開情報で確定できない変更は推測で反映しない。
- 隣ノあおこは本人Twitchで「2025.11〜活動休止」を確認して追補。「卒業」は一次情報で確定できず採用していない。
- スポンサー掲載条件、計測の継承、受信確認。既存スポンサー表示は維持。
- 旧外部URLの404応答やネットワーク制限は別表に残す。本文の歴史的なリンクは勝手に他人のアカウントへ置換しない。

`--production` は noindex を外すローカル生成オプションです。公開承認・デプロイを意味しません。確認版ZIPをそのまま本番配置すると noindex のままなので、最終GO後のリリース作業で再生成し、公開先で確認する必要があります。`404.html` はホストの404応答ページに使用できます。通常ルートはディレクトリーのindex.htmlで元のパスを維持します。
