#!/usr/bin/env python3
"""コードのリポジトリで、claude.aiのコネクタの読み込みを切る。

claude.aiのコネクタのツール名一覧は、使わないセッションでも毎回読み込まれ、実測で入力トークンの約3割を占めた例がある。
実装作業ではコネクタをほとんど使わないので、コードのリポジトリの .claude/settings.local.json に
"disableClaudeAiConnectors": true を書く。Slackやドキュメントの作業は、リポジトリの外で起動すれば今までどおり使える。

  python3 connector-scope.py <探すディレクトリ>            # 対象を表示するだけ
  python3 connector-scope.py <探すディレクトリ> --apply    # 書き込む

判定の基準
  - コードのリポジトリ(gitのルートに package.json / pyproject.toml / go.mod / Cargo.toml / Gemfile / pom.xml がある)を対象にする
  - .claude/settings.json か .claude/settings.local.json に disableClaudeAiConnectors が既に書かれていれば、
    true でも false でもその判断を尊重して触らない。コネクタを使うリポジトリは false を書いておけば対象から外れる
"""
import json, os, subprocess, sys

MARKERS = ('package.json', 'pyproject.toml', 'go.mod', 'Cargo.toml', 'Gemfile', 'pom.xml')
KEY = 'disableClaudeAiConnectors'
SKIP_DIRS = {'node_modules', '.git', 'dist', 'build', '.next', 'vendor', '.venv'}


def load(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def repos(root, depth=4):
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        if d.count(os.sep) - root.count(os.sep) >= depth:
            dirs[:] = []
        if os.path.isdir(os.path.join(d, '.git')) and any(m in files for m in MARKERS):
            yield d
            dirs[:] = []  # 入れ子のリポジトリは親の判断に従う


def decided(repo):
    for name in ('settings.json', 'settings.local.json'):
        data = load(os.path.join(repo, '.claude', name))
        if isinstance(data, dict) and KEY in data:
            return f'{name}で{str(data[KEY]).lower()}'
    return None


def exclude_local(repo):
    # settings.local.json を誤って commit しないよう .git/info/exclude に足す
    try:
        common = subprocess.run(['git', '-C', repo, 'rev-parse', '--git-common-dir'],
                                capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return
    if not common:
        return
    path = os.path.join(common if os.path.isabs(common) else os.path.join(repo, common), 'info', 'exclude')
    line = '.claude/settings.local.json'
    cur = open(path, encoding='utf-8').read().splitlines() if os.path.exists(path) else []
    if line not in cur:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(f'{line}\n')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print(__doc__)
        return 2
    apply = '--apply' in sys.argv
    root = os.path.abspath(os.path.expanduser(args[0]))
    todo = []
    for repo in sorted(repos(root)):
        why = decided(repo)
        rel = os.path.relpath(repo, root)
        if why:
            print(f'触らない  {rel}（{why}）')
        else:
            print(f'切る      {rel}')
            todo.append(repo)
    print(f'\n切る対象は{len(todo)}件')
    if not apply:
        print('--apply で書き込む')
        return 0
    for repo in todo:
        path = os.path.join(repo, '.claude', 'settings.local.json')
        data = load(path) or {}
        data[KEY] = True
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, path)
        exclude_local(repo)
    print('書き込んだ。各リポジトリで新しく始めたセッションから効く')
    return 0


if __name__ == '__main__':
    sys.exit(main())
