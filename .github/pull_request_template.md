## 何を良くするか

<!-- 1〜2文で。どの作業が速くなる・安全になる・読み込みが減るか -->

## 確かめたこと

- [ ] `python3 -m unittest discover -s tests`が通る
- [ ] プラグインの中身を変えた場合、`plugins/env-kit/.claude-plugin/plugin.json`の`version`を上げた
- [ ] 個人や勤務先・顧客の実名、非公開のURL、トークンの実値を入れていない

## 監査の結果（プラグインや雛形を変えた場合）

変更の前と後で`/env-kit:env-audit`を実行し、変わった行だけを貼る。
