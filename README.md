# claude-code-env-kit

Claude Codeを使うチームが、各自の環境の重さ・守りの抜け・参照切れを同じ表で点検し、直し方をPRで持ち寄るためのプラグインと雛形です。各自の個人設定とは切り分けて配ります。

[![ci](https://github.com/BoxPistols/claude-code-env-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/BoxPistols/claude-code-env-kit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> A Claude Code plugin and templates for teams to audit their Claude Code setups.
> `/env-kit:env-audit` reports per-session context size, slow hooks, broken references, enabled-but-missing plugins and missing deny rules as a read-only table.
> Fixes are shared through PRs with before/after audit output; CI runs the tests on Ubuntu, macOS and Windows.

## 実行例

`/env-kit:env-audit`をある個人の環境で実行した実際の出力です（ホームディレクトリのパスは`~`に置き換えています）。設定は書き換えず、表だけを出します。

```text
# Claude Code環境の監査（~/dev/portfolio/claude-code-env-kit）

| 状態 | 区分 | 項目 | 詳細 |
| --- | --- | --- | --- |
| 要確認 | hook | ユーザー UserPromptSubmit | 応答やツールのたびに同期でネットワーク処理を行う: bash "~/.claude/skills/memory-sync/hooks/start.sh" |
| 要確認 | 権限 | deny | denyが0件。.envや鍵の読み取りを止める設定が無い。denyは確認を増やさない |
| 情報 | hook | ユーザー PreToolUse | すべてのツール呼び出しで同期実行される: if [ -z "${HOME-}" ]; then case "${OSTYPE-}" in msys*/cygwin*/win32*) printf '{} |
| 情報 | hook | ユーザー PostToolUse | すべてのツール呼び出しで同期実行される: if [ -z "${HOME-}" ]; then case "${OSTYPE-}" in msys*/cygwin*/win32*) printf '{} |
| 情報 | hook | ユーザー イベントごとの本数 | Elicitation=1, ElicitationResult=1, PermissionRequest=1, PostCompact=1, PostToolUse=1, PostToolUseFailure=1, PreToolUse=1, SessionEnd=1, SessionStart=1, Stop=2, StopFailure=1, SubagentStart=1, SubagentStop=1, TeammateIdle=1, UserPromptSubmit=2 |
| 情報 | 読み込み量 | claude.aiのコネクタ | claude.aiに接続したコネクタのツール名一覧が毎セッション読み込まれる。コネクタを使わないリポジトリでは、.claude/settings.local.jsonに"disableClaudeAiConnectors": trueを書くと読み込まれない。ユーザー設定でtrueにするとプロジェクト側で戻せない |
| 情報 | 権限 | bypassモード | 公式はコンテナやVMでの利用を推奨している。速度を優先して選んでいるなら、denyと署名などのhookで最低限を守る |
| OK | 読み込み量 | ~/.claude/CLAUDE.md | 115行 / 4913バイト |
| OK | 書き方 | 「考えて」系の指示 | 5ファイルで0件 |

要確認は2件。自動では直さない。直すかどうかは表を見て決める。
```

`tools/connector-scope.py`の確認だけの実行（`--apply`なし）です。サンプルとして作った4つのリポジトリ（コード3つ、`package.json`などの無いメモ1つ）に対して実行しました。

```text
$ python3 tools/connector-scope.py ~/dev
切る      api-server
触らない  chat-bot（settings.jsonでfalse）
切る      web-app

切る対象は2件
--apply で書き込む
```

## 見どころ

- 読むだけの監査：CLAUDE.mdの行数とバイト数、応答ごとに同期で走るhookのネットワーク処理、存在しないパスへの参照、有効なのに入っていないプラグイン、denyの抜けを1つの表にする。標準ライブラリだけのPython（[`plugins/env-kit/skills/env-audit/claude-env-audit.py`](plugins/env-kit/skills/env-audit/claude-env-audit.py)）
- 設定の置き場所を4層に分ける：個人（`~/.claude/`）、リポジトリ（`.claude/`）、このリポジトリ、Managed Settingsで、誰が何を変えるかを決める（[下の表](#個人の設定とチームの設定の分け方)）
- 3つのOSでのCI：Ubuntu・macOS・WindowsでJSONの構文と監査のテストを流す（[`.github/workflows/ci.yml`](.github/workflows/ci.yml)、[`tests/test_env_kit.py`](tests/test_env_kit.py)）

## チームでの導入の流れ

1. 各自が`/env-kit:env-audit`を実行し、「要確認」の行を確かめる（[`docs/guide.md`](docs/guide.md)の「初回のクリーニング」）
2. 複数の人に効く直し方は、直す前と後の監査の出力を貼ってPRにする。共有する設定はリポジトリの`.claude/`へ、監査や雛形の改善はこのリポジトリへ出す（[CONTRIBUTING.md](CONTRIBUTING.md)）
3. 月に1回、または動作が重いと感じたときに監査をやり直す（[`docs/guide.md`](docs/guide.md)の「定期点検」）

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

claude.aiのコネクタのツール名一覧は、使わないセッションでも毎回読み込まれます。ある個人の環境では、コネクタを切ると入力トークンが48,777から33,593に減りました（約31%減。測定条件は[`docs/guide.md`の「実測例」](docs/guide.md#実測例)）。`tools/connector-scope.py`は、コードのリポジトリ（gitのルートにpackage.jsonやpyproject.tomlなどがある）の`.claude/settings.local.json`に`"disableClaudeAiConnectors": true`を書きます。

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
