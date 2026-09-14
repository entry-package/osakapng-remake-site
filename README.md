# OsakaPNG 自社管理サイト（切替前の確認版）

Strikinglyの公開ページ109件から、記事・プロフィール101件を元のURLで再構築した静的サイトです。本文・画像を保全し、記事内リンクの修正は別表で管理しています。現在の公開プロフィールから不足情報を補っています。公開・DNS変更・Strikingly解約は実施していません。最終GO前の確認版です。

## 構成

- `index.html`：共通HTMLテンプレート。
- `styles.css` / `osaka-theme.css` / `script.js`：基本表示、大阪とゲームを軸にしたテーマ、メニュー、記事検索、問い合わせメールの作成補助。
- `scripts/build.py`：静的ページの生成。出力は `dist/`。通常は全ページ noindex。
- `content/source-pages.json`：2026-09-10時点の公開原文。加工前の本文・リンク・画像・ハッシュを保存。社内文書は含めない。
- `content/member-updates.json`：公開プロフィールおよび運営者の直接訂正による現在情報の追補。原文を消さず、別枠で表示する。脱退済みの人物は現メンバーカードから除外する。
- `content/design-assets.json`：2026-09-13追加の大阪・ゲームイラストの生成条件とチェックサム。
- `content/stories.json` / `related-sources.json`：PACkage公式の記事11件の調査と、PNGに直接関連する8件の掲載案内。
- `content/posts/*.json`：新規ニュースの原稿。取得原文とは分けて管理する。
- `content/media-manifest.json`：画像148参照とローカル保存先・SHA-256。実画像147参照を取得、空のプラットフォーム用カバー1参照は既存ロゴへ置換。
- `content/thumbnail-overrides.json` / `thumbnail-assets.json`：サムネイル未設定22記事に追加した10種類の編集用画像。生成条件・チェックサムと記事対応を保存。既存のカバー79件と取得本文は変更せず、一覧・OGP・構造化データに反映する。画像内の文言は掲載時点の告知として自然な表現を使う。掲載時期は日付とページ側の注記で伝える。
- `content/route-manifest.json`：旧URLから出力ファイルへの対応表。
- `content/editorial-decisions.json`：表題補正・Cookie説明更新などの編集判断。
- `content/link-corrections.json`：運営者の依頼による旧問い合わせ1 URLの置換と、過去の監査で404だった外部46 URL・73箇所のリンク解除。対象URL・記事・箇所数・根拠を固定し、元の本文と参照先は取得原文に保存する。別人のアカウントや終了済み募集の代替フォームを推測で割り当てない。
- `content/verification.json` / `browser-verification.json` / `external-link-verification.json`：検証結果。
- `.audit/`：公開HTMLの取得キャッシュ、独立ブラウザーの一時プロファイル、確認画像。Git・配布対象外。

## 開発

Python 3.11以上と `beautifulsoup4` を使用します。JSの本番ライブラリー、CDN、認証、ビルド時の外部サービスは不要です。

```sh
python3 scripts/build.py
python3 scripts/preview.py
```

ローカル確認先: http://127.0.0.1:8766/

プレビューサーバーはループバック限定・キャッシュ保存なしです。以前のサーバーで開いたページが古い場合は一度再読み込みしてください。本番用サーバーではありません。

## 2026-09-13 デザイン確認版

2026-09-14更新：トップは「ぬいぐるみ風のタコペンが、小さな地図を持って大阪をさんぽする」ビジュアルです。元ロゴだけをキャラクター参照に使い、淡い色のミニチュアの街と柔らかな質感で制作しました。大きな画像内ラベルを外し、トップの見出し・ボタン・スマホでの画像比率も合わせて調整。生成条件は `content/takopen-soft-hero-20260914.json`、今回の検証範囲は `content/takopen-soft-verification-20260914.json` を参照。旧画像は保存しています。

Solary（https://www.solary.fr/）の強い見出しと明確なチームサイト構成を参考に、黒・紫・黄を基調にしました。トップ右側の円形ロゴ演出は、大阪の街並み・たこ焼き・ゲームコントローラーのオリジナルイラストへ変更。運営会社欄はPACkageの白い既存ロゴを濃色の面に載せています。Solaryの画像・ロゴ・ソースコードは使用していません。

運営者の直接訂正により隣ノあおこを脱退済みとして、現メンバー表示を7件に変更しました。プロフィール8件と歴史的な記事本文は保存し、旧プロフィールの先頭に脱退済みの注記を追加しています。脱退日は未提供のため記載していません。

今回のブラウザー確認はChromeの画面とDOMで実施し、結果は `content/design-verification-20260913.json` に保存します。`content/browser-verification.json` は2026-09-10の旧デザインの検証記録です。

取得原文を更新する場合は、差分を先に確認してください。サイトの現行表示が社内の活動状況より古い場合があります。`capture.py` は既存キャッシュを再利用します。別日の再取得は旧 `.audit/source/` を日付付きで退避してから行い、旧 `source-pages.json` と比較してください。原文と追補を混ぜない設計です。

```sh
python3 scripts/capture.py
python3 scripts/media.py
python3 scripts/build.py
python3 scripts/verify.py
node --check script.js
```

`browser_check.py` はMacのChromeのheadless CLIを使用し、ユーザーのログイン済みプロファイルを使わずにローカルサイトだけを確認します。先に上記HTTPサーバーを起動します。6種類の画面幅、文字拡大、検索・リセット、モバイルメニュー、問い合わせの入力検証・本文作成を確認します。メールは送信しません。

追加サムネイルは内蔵image_genで生成したイラストです。実在人物・製品の写真として扱いません。同じ種別の記事には共通デザインを割り当て、固有名詞・日付は原記事の見出しで区別します。WebPは画素寸法を維持して配信用に圧縮したものです。元PNGは `.audit/thumbnail-originals/` に保管し、配布物には軽量なWebPを含めます。修正前の画像は `_archive/thumbnail-v1/` に保管し、サイトには配布しません。原サイトでカバーが追加・変更された場合はビルドを停止し、追補の再確認を求めます。

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
- 隣ノあおこの脱退は2026-09-13の運営者の直接訂正で反映済み。他の所属・スポンサー情報は別途正本との確認が必要。
- スポンサー掲載条件、計測の継承、受信確認。既存スポンサー表示は維持。
- 旧Strikingly問い合わせは `/contact/` へ置換済み。監査で404だった46 URLは記事の文言を残してクリック先を外し、該当記事に注記を付けた。これはアカウント削除の断定ではない。ネットワーク・アクセス制限による未検証URLはリンク解除の対象外。外部リンク監査は既存の確認結果を再利用するため、全件の最新疎通を証明するものではない。

`--production` は noindex を外すローカル生成オプションです。公開承認・デプロイを意味しません。確認版ZIPをそのまま本番配置すると noindex のままなので、最終GO後のリリース作業で再生成し、公開先で確認する必要があります。`404.html` はホストの404応答ページに使用できます。通常ルートはディレクトリーのindex.htmlで元のパスを維持します。

## 2026-09-14 公開ビルド

GitHub Pagesは既存の `main` ブランチ直下を公開します。開発ソースのテンプレートをそのまま `main` にマージせず、検証済み生成物だけを別の公開ブランチへコピーし、PRから反映します。

```sh
python3 scripts/build.py --production --output /path/to/release/site --base-path /osakapng-remake-site
python3 scripts/verify.py --production --output /path/to/release/site --base-path /osakapng-remake-site --report /path/to/release/verification.json
```

独自ドメインのルート直下に切り替える際は `--base-path` を省略して再生成します。通常ページの内部リンクは相対パスで、`--base-path` は未知のURLに表示する `404.html` の参照先に適用します。`.nojekyll` で旧 `/_blog/` も配信対象にします。通常ページは `index,follow`、404は `noindex,nofollow` とし、robots.txt・sitemap.xml・canonicalも検証します。監査ファイルや取得原文、ローカル環境は配布物に含めません。

2026-09-14のChrome確認で、柔らかなタコペンのトップをPCとモバイルで目視確認しました。モバイルDOMの幅とscrollWidthはともに375pxで横はみ出しなし、画像のnaturalWidthは1536pxです。公開先の読戻しと独自ドメインの切替状態はリリース記録を別途参照してください。
