# Claude Code最新化・クリーニング手引き

Claude Codeの設定は、使ううちに指示やhookやプラグインが足され、毎回の待ち時間とトークン消費が増えていきます。この手引きは、公式ドキュメントと実測に基づいて、それを最小限の手順で整理し、月に1回点検するためのものです。

## 対象と考え方

整理の対象は次の3種類のコストです。

| コスト | 発生する場所 | 主な原因 |
| --- | --- | --- |
| 毎セッションの読み込み量 | CLAUDE.md、paths指定のないrules、プラグインのスキル一覧と開始時の注入、claude.aiのコネクタのツール名一覧 | 手順書や知見をCLAUDE.mdに書き足す。一部のリポジトリでしか使わないプラグインやコネクタを全体で有効にする |
| 応答ごとの待ち時間 | UserPromptSubmit、PreToolUse、PostToolUseのhook | 同期実行のhookの中でネットワーク処理を行う。すべてのツール呼び出しで外部プロセスを起動する |
| 守りの抜け | permissions、hook | 機密ファイルのdenyが無い。文書にはあるが実体のないhookがある |

整理の原則は3つです。

1. 毎セッション読み込むものは、常に効かせる規則だけにする。手順はSkillに、ファイルの種類で決まる規則はpaths指定のrulesに分ける
2. 応答やツールのたびに走るhookでは待たせない。同期の処理はセッションの開始と終了に移し、通知のように結果を待たないものは`async: true`にする
3. 守りは確認プロンプトを増やさない形で入れる。denyは該当する操作だけを止め、それ以外の作業を遅くしない

## 初回のクリーニング

### 測る

1. `/env-kit:env-audit`を実行し、「要確認」の行を確かめる
2. UserPromptSubmit・PreToolUse・PostToolUseのhookは、コマンドを手で実行して時間を測る。同じイベントのhookは並列に動くので、待ち時間は最も遅いhookの時間になる

### 減らす

1. CLAUDE.mdを200行未満にする（公式の目安）。手順や長い説明はSkillか必要なときに読むファイルへ移し、CLAUDE.mdには「どういうときにどこを読むか」の1行だけを残す。雛形は`templates/CLAUDE.md`
2. UIや特定の言語の規則は`.claude/rules/`へ移し、先頭に`paths`を書く。雛形は`templates/rules/ui.md`
3. プラグインは使うリポジトリだけで有効にする。ユーザー設定では`false`にし、リポジトリの`.claude/settings.json`の`enabledPlugins`で有効にする
4. claude.aiのコネクタは、使わないものをclaude.ai側で外す。コネクタのツール名一覧は数万トークン規模になることがある。コネクタを使わないリポジトリでは、`.claude/settings.local.json`に`"disableClaudeAiConnectors": true`を書くと全コネクタを切れる（個別には切れない。ユーザー設定で`true`にするとプロジェクト側で戻せない）
5. hookを整理する。応答やツールのたびに走るイベントで同期のネットワーク処理をしない。PreToolUseのmatcherは対象のツールに絞る

CLAUDE.mdはSessionStartのhookより先に読み込まれます（実測。公式には明記がない）。hookからCLAUDE.mdを書き換えても、効くのは次のセッションからです。そのセッションで渡したい内容は、SessionStartのhookの標準出力として出します。上限は10,000文字です。

### 守る

1. 機密ファイルをdenyに入れる。雛形は`templates/settings.user.example.json`。`**/.env`と書くと作業ディレクトリ基準で照合され、その外のファイルには当たらない（実測）。`//`で始めるとルート基準になる。denyはbypassPermissionsでも効く（実測）。PythonやNodeのスクリプトが間接的に読む場合は防げないので、確実に止めるにはサンドボックスを使う
2. CLAUDE.mdに「〜はしない」と書いた規則のうち、守られないと困るものはhookにする。例は`templates/hooks/no-ai-signature.py`（commitやPRの本文に決まった文言を入れない）
3. CLAUDE.mdに書いたhookやスクリプトが実在するかを確かめる。監査の「参照切れ」で見つかる

## Opus 5.5への対応

Opus 5.5は毎回の応答の前に自分で考え、どれだけ考えるかも自分で決めます（公式ガイド）。

- 「think carefully」「step by step」「よく考えて」の類を削る。監査が検出する
- 止める条件をCLAUDE.mdに書く。破壊的な操作の確認プロンプトは残す
- 長い作業の報告の形を決める（「判断待ち」「変更」「発見」）
- 長い作業では、チェックリストをTASKS.mdのようなファイルに置かせる
- 大きな監査や移行はsubagentに分け、各報告の根拠（ファイルと行）を確かめてから採用する

## 定期点検

月に1回、`/env-kit:env-audit`を実行します。hookにしないのは、毎セッション動かすと点検そのものが待ち時間になるためです。

## 実測例

ある個人の開発環境（2026年9月、Opus 5.5）で整理したときの値です。環境によって値は変わります。

| 項目 | 整理前 | 整理後 |
| --- | --- | --- |
| 応答ごとの待ち（UserPromptSubmitのhookでの`git pull`） | 約2.4秒 | 0秒（セッション開始時に1回） |
| 1回のやり取りの中央値に対する上の短縮の割合 | - | 約4% |
| セッション開始時の入力トークン | 45,185 | 約42,700 |
| claude.aiのコネクタを切った場合の入力トークン | 48,777 | 33,593（約31%減） |
| 機密ファイルのdeny | 0件 | 10件 |

速度は、モデルが考えて出力する時間が大半を占めるため、hookの整理だけでは数%しか変わりません。トークンは、コネクタのツール名一覧の影響が最も大きくなります。

## 出典

- [How Claude remembers your project](https://code.claude.com/docs/en/memory)
- [Hooks reference](https://code.claude.com/docs/en/hooks)
- [Configure permissions](https://code.claude.com/docs/en/permissions)
- [Settings reference](https://code.claude.com/docs/en/settings-reference)
- [Getting the most out of Opus 5.5 in Claude and Claude Code](https://claude.dev/blog/getting-the-most-out-of-opus-5-5/)
