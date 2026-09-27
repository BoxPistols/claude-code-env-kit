"""監査スクリプトと署名禁止hookのテスト。標準ライブラリだけで動く。

  python3 -m unittest discover -s tests
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, 'plugins', 'env-kit', 'skills', 'env-audit', 'claude-env-audit.py')
SIGN = os.path.join(ROOT, 'templates', 'hooks', 'no-ai-signature.py')


def audit(home, project):
    # WindowsのPythonはホームの判定にUSERPROFILEを使うので、両方を仮の場所に向ける
    env = {**os.environ, 'HOME': home, 'USERPROFILE': home}
    out = subprocess.run([sys.executable, AUDIT, project, '--json'], env=env,
                         capture_output=True, text=True, encoding='utf-8', check=True).stdout
    return json.loads(out)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, 'home')
        self.project = os.path.join(self.tmp.name, 'project')
        os.makedirs(self.project)

    def tearDown(self):
        self.tmp.cleanup()

    def items(self, status):
        return [r for r in audit(self.home, self.project) if r['status'] == status]

    def test_整理が要る設定を要確認として報告する(self):
        write(os.path.join(self.home, '.claude', 'CLAUDE.md'), '規則\n' * 250 + '`~/.claude/hooks/missing.py`\n')
        script = os.path.join(self.home, 'sync.sh')
        write(script, '#!/bin/sh\ngit -C "$HOME/notes" pull --ff-only\n')
        write(os.path.join(self.home, '.claude', 'settings.json'), json.dumps({
            'hooks': {'UserPromptSubmit': [{'hooks': [{'type': 'command', 'command': f'bash "{script}"'}]}]},
            'enabledPlugins': {'not-installed@example': True},
        }))
        kinds = {r['kind'] for r in self.items('要確認')}
        self.assertEqual(kinds, {'読み込み量', 'hook', '参照切れ', 'プラグイン', '権限'})

    def test_整えた設定では要確認が出ない(self):
        # 「~/dir/<名前>/file」のような書き方の例は参照切れにしない
        write(os.path.join(self.home, '.claude', 'CLAUDE.md'), '# 規則\n- 短い規則\n- 退避先は `~/.claude/backup/<ホスト名>/claude-md.md`\n')
        write(os.path.join(self.home, '.claude', 'settings.json'), json.dumps({
            'permissions': {'deny': ['Read(//**/.env)']},
            'hooks': {'Notification': [{'hooks': [{'type': 'command', 'command': 'true', 'async': True}]}]},
        }))
        self.assertEqual(self.items('要確認'), [])

    def test_作業ディレクトリ基準のdenyを指摘する(self):
        write(os.path.join(self.home, '.claude', 'settings.json'), json.dumps({
            'permissions': {'deny': ['Read(**/.env)']},
        }))
        self.assertIn('denyの書き方', [r['item'] for r in self.items('要確認')])

    def test_考えて系の指示を指摘する(self):
        write(os.path.join(self.home, '.claude', 'CLAUDE.md'), '- think carefully before answering\n')
        self.assertIn('書き方', [r['kind'] for r in self.items('要確認')])


    def test_コネクタを切っていなければ情報として示す(self):
        write(os.path.join(self.home, '.claude', 'settings.json'), json.dumps({}))
        self.assertIn('claude.aiのコネクタ', [r['item'] for r in self.items('情報')])
        write(os.path.join(self.project, '.claude', 'settings.local.json'), json.dumps({'disableClaudeAiConnectors': True}))
        self.assertIn('claude.aiのコネクタ', [r['item'] for r in self.items('OK')])


class SignatureHookTest(unittest.TestCase):
    def run_hook(self, command):
        data = json.dumps({'tool_input': {'command': command}, 'cwd': ROOT})
        return subprocess.run([sys.executable, SIGN], input=data, capture_output=True, text=True, encoding='utf-8').returncode

    def test_止めるもの(self):
        for cmd in (
            'git commit -m "fix\n\nCo-Authored-By: Claude <noreply@anthropic.com>"',
            'gh pr create --body "Generated with [Claude Code](https://claude.ai/code)"',
            'gh pr comment 1 --body "done \U0001F389"',
        ):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.run_hook(cmd), 2)

    def test_通すもの(self):
        for cmd in (
            'git commit -m "修正する"',
            'gh pr create --body "詳細は https://claude.ai/code/artifact/abc"',
            'echo "Co-Authored-By: Claude"',
            'ALLOW_AI_SIGNATURE=1 gh issue create --body "Co-Authored-By: Claude を禁止する"',
        ):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.run_hook(cmd), 0)


if __name__ == '__main__':
    unittest.main()
