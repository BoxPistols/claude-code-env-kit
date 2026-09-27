# claude-code-env-kit

チームでClaude Codeの環境を点検し、改善を持ち寄るための道具一式です。各自の個人設定とは切り分けて配ります。

| 中身 | 場所 | 内容 |
| --- | --- | --- |
| 監査のSkill | `/env-kit:env-audit` | 毎セッションの読み込み量、hookの重さ、参照切れ、使われていない設定、古い書き方、権限を表で報告する。設定は書き換えない |
| 雛形 | `templates/` | settings.json、CLAUDE.md、paths指定のルール、署名禁止のhook |
| 手引き | `docs/guide.md` | 初回の整理、Opus 5.5への対応、定期点検の手順 |

## 入れ方

```
claude plugin marketplace add BoxPistols/claude-code-env-kit
claude plugin install env-kit@claude-code-env-kit
```

組織のアカウントへ移したりforkしたりした場合は、`BoxPistols/claude-code-env-kit`をそのリポジトリの`owner/repo`に読み替えます。cloneしたディレクトリのパスも指定できます。更新は`claude plugin update env-kit@claude-code-env-kit`です。

チームのリポジトリで全員が使えるようにするには、`templates/settings.project.example.json`の`extraKnownMarketplaces`と`enabledPlugins`を、そのリポジトリの`.claude/settings.json`へ足してcommitします。`extraKnownMarketplaces`は、各メンバーがそのフォルダを信頼した後にマーケットプレイスを登録します（公式のsettingsのページ）。プラグインが入っていないメンバーは、`claude plugin install env-kit@claude-code-env-kit`で入れます。

## 使い方

月に1回、または動作が重いと感じたときに、Claude Codeで次を実行します。

```
/env-kit:env-audit
```

「要確認」の行を見て、直すかどうかを決めます。直し方は`docs/guide.md`にあります。

## コネクタの読み込みを切る

claude.aiのコネクタのツール名一覧は、使わないセッションでも毎回読み込まれます。実測で入力トークンの約3割を占めた例があります。`tools/connector-scope.py`は、コードのリポジトリ（gitのルートにpackage.jsonやpyproject.tomlなどがある）の`.claude/settings.local.json`に`"disableClaudeAiConnectors": true`を書きます。

```
python3 tools/connector-scope.py ~/dev            # 対象を表示するだけ
python3 tools/connector-scope.py ~/dev --apply    # 書き込む
```

コネクタを使うリポジトリは、`.claude/settings.json`か`.claude/settings.local.json`に`"disableClaudeAiConnectors": false`を書いておくと対象から外れます。Slackやドキュメントの作業は、リポジトリの外で起動すれば今までどおりコネクタを使えます。

## 個人の設定とチームの設定の分け方

| 置き場所 | 共有の範囲 | 入れるもの | 変え方 |
| --- | --- | --- | --- |
| `~/.claude/` | 本人のみ | 好みの設定、個人で使うhookやSkill | 各自で自由に変える |
| 各リポジトリの`.claude/`（commitする） | そのリポジトリを使う全員 | `enabledPlugins`、deny、paths指定のルール、リポジトリ固有のSkill | そのリポジトリへのPR |
| このリポジトリ | 組織の全員 | 監査の道具、雛形、手引き | このリポジトリへのPR（`CONTRIBUTING.md`） |
| Managed Settings | 組織の全員。個人では外せない | 全社で守るdeny、必要なら`disableBypassPermissionsMode` | 管理者 |

個人の好み（通知、テーマ、記憶の仕組みなど）はこのリポジトリに入れません。複数の人に効く改善だけを持ち込みます。

## 改善を持ち込む

手順は[CONTRIBUTING.md](CONTRIBUTING.md)にあります。

すぐに着手できる改善の候補は、ラベル「改善の候補」のissueにまとめています。新しい候補を見つけたら、完了の条件を添えてissueを立ててください。

## ライセンス

MIT
