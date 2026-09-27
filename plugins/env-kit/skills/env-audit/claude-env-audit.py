#!/usr/bin/env python3
"""Claude Code環境の監査。読むだけで、何も書き換えない。

毎セッション読み込まれる量、hookの重さ、参照切れ、使われていない設定、古い書き方、権限を表にして報告する。
標準ライブラリだけで動き、macOS・Linux・WSL2で同じように使える。月に1回程度、手で実行する想定。

  python3 claude-env-audit.py [プロジェクトのディレクトリ]   # 省略時はカレントディレクトリ
  python3 claude-env-audit.py --json                          # 機械可読の出力

判定の目安は公式ドキュメントに合わせている。
  - CLAUDE.md は1ファイル200行未満 (https://code.claude.com/docs/en/memory)
  - hookの出力は10,000文字が上限 (https://code.claude.com/docs/en/hooks)
"""
import glob, json, os, re, sys

HOME = os.path.expanduser('~')
CLAUDE = os.path.join(HOME, '.claude')
LINE_LIMIT = 200
BYTE_LIMIT = 10_000  # 行数が目安内でも1行が長いと重い。公式の数値ではなく、この監査の目安
HOT_EVENTS = ('UserPromptSubmit', 'PreToolUse', 'PostToolUse')  # 応答のたび、ツールのたびに走るイベント
# git -C <dir> pull のように間に引数が入る形も拾う
NETWORK = re.compile(r'\bgit\b[^\n;|&]*?\s(pull|fetch|push|clone)\b|\b(curl|wget|gh\s+api)\b|\bnpm\s+(i|install|view)\b')
OLD_PHRASES = re.compile(r'think (carefully|hard|step by step)|step[- ]by[- ]step|ステップバイステップ|よく考えて|じっくり考え', re.I)

rows = []  # (区分, 項目, 状態, 詳細)
def add(kind, item, status, detail=''):
    rows.append((kind, item, status, detail))

def load_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None

def read(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return None

def has_paths(text):
    m = re.match(r'^---\n(.*?)\n---', text, re.S)
    return bool(m and re.search(r'^paths:', m.group(1), re.M))

def short(p):
    return p.replace(HOME, '~')

# ── 1. 毎セッション読み込まれる量 ──
def audit_instructions(project):
    files = [os.path.join(CLAUDE, 'CLAUDE.md')]
    files += [os.path.join(project, n) for n in ('CLAUDE.md', 'CLAUDE.local.md', os.path.join('.claude', 'CLAUDE.md'))]
    for f in files:
        t = read(f)
        if t is None:
            continue
        n = t.count('\n') + 1
        b = len(t.encode())
        status = '要確認' if n >= LINE_LIMIT or b > BYTE_LIMIT else 'OK'
        add('読み込み量', short(f), status, f'{n}行 / {b}バイト' + (f'（目安{LINE_LIMIT}行未満・{BYTE_LIMIT}バイト以下）' if status != 'OK' else ''))
    for d in (os.path.join(CLAUDE, 'rules'), os.path.join(project, '.claude', 'rules')):
        for f in sorted(glob.glob(os.path.join(d, '**', '*.md'), recursive=True)):
            t = read(f) or ''
            if has_paths(t):
                add('読み込み量', short(f), 'OK', f'paths指定あり。該当ファイルを読んだときだけ読み込まれる（{len(t.encode())}バイト）')
            else:
                add('読み込み量', short(f), '情報', f'paths指定なし。毎セッション読み込まれる（{len(t.encode())}バイト）')

# ── 2. hookの重さ ──
def iter_hooks(settings):
    for event, groups in (settings.get('hooks') or {}).items():
        for g in groups or []:
            for h in g.get('hooks') or []:
                yield event, g.get('matcher', ''), h

SCRIPT_RX = re.compile(r'([~/][^\s"\']+\.(?:sh|py|js|mjs|cjs))')
def script_body(cmd):
    # hookが呼ぶスクリプトの中身。ネットワーク処理がコマンド文字列ではなくスクリプトの中にある場合に拾う
    out = []
    for m in SCRIPT_RX.finditer(cmd):
        t = read(os.path.expanduser(m.group(1)))
        if t:
            out.append('\n'.join(l for l in t.splitlines() if not l.lstrip().startswith(('#', '//'))))
    return '\n'.join(out)

def audit_hooks(sources):
    for label, s in sources:
        counts = {}
        for event, matcher, h in iter_hooks(s):
            counts[event] = counts.get(event, 0) + 1
            cmd = h.get('command', '')
            if event in HOT_EVENTS and not h.get('async') and (NETWORK.search(cmd) or NETWORK.search(script_body(cmd))):
                add('hook', f'{label} {event}', '要確認', f'応答やツールのたびに同期でネットワーク処理を行う: {cmd[:80]}')
            if event in ('PreToolUse', 'PostToolUse') and matcher in ('', '*') and not h.get('async'):
                add('hook', f'{label} {event}', '情報', f'すべてのツール呼び出しで同期実行される: {cmd[:80]}')
        if counts:
            add('hook', f'{label} イベントごとの本数', '情報', ', '.join(f'{k}={v}' for k, v in sorted(counts.items())))

# ── 3. 参照切れ ──
PATH_RX = re.compile(r'(?<![\w/.])(~/[\w./-]+|/(?:Users|home)/[\w./-]+)')
def audit_refs(sources, project):
    texts = [(short(os.path.join(CLAUDE, 'CLAUDE.md')), read(os.path.join(CLAUDE, 'CLAUDE.md')) or '')]
    for label, s in sources:
        texts.append((label, ' '.join(h.get('command', '') for _, _, h in iter_hooks(s))))
    seen = set()
    for label, t in texts:
        for m in PATH_RX.finditer(t):
            p = m.group(1).rstrip('.,)')
            # 直後が<なら「~/dir/<名前>」のような書き方の例なので実在を問わない
            if '*' in p or '<' in p or t[m.end():m.end() + 1] == '<' or p in seen:
                continue
            seen.add(p)
            if not os.path.exists(os.path.expanduser(p)):
                add('参照切れ', label, '要確認', f'存在しないパス: {p}')

# ── 4. プラグイン ──
def audit_plugins(user, project_settings):
    installed = set(((load_json(os.path.join(CLAUDE, 'plugins', 'installed_plugins.json')) or {}).get('plugins') or {}))
    enabled = {k: v for k, v in ((user or {}).get('enabledPlugins') or {}).items()}
    for name, on in enabled.items():
        if on and name not in installed:
            add('プラグイン', name, '要確認', '有効になっているがインストールされていない')
    for name, on in enabled.items():
        if not on or name not in installed:
            continue
        plugin, _, market = name.partition('@')
        skills = glob.glob(os.path.join(CLAUDE, 'plugins', 'cache', market, plugin, '*', 'skills', '*', 'SKILL.md'))
        versions = {p.split(os.sep)[-4] for p in skills}
        n = len(skills) // max(len(versions), 1)
        add('プラグイン', name, '情報', f'ユーザー設定で全ディレクトリ有効。スキル{n}個。使うリポジトリが限られるなら、そのリポジトリの.claude/settings.local.jsonで有効にする')
    for name, on in ((project_settings or {}).get('enabledPlugins') or {}).items():
        add('プラグイン', f'{name}（このプロジェクト）', '情報', '有効' if on else '無効')

def audit_connectors(user, project_settings):
    # claude.aiのコネクタのツール名一覧は、使わないセッションでも毎回読み込まれる。実測で入力の約3割を占めた例がある
    off = (user or {}).get('disableClaudeAiConnectors') or (project_settings or {}).get('disableClaudeAiConnectors')
    if off:
        add('読み込み量', 'claude.aiのコネクタ', 'OK', 'このプロジェクトでは読み込まない（disableClaudeAiConnectors）')
    else:
        add('読み込み量', 'claude.aiのコネクタ', '情報', 'claude.aiに接続したコネクタのツール名一覧が毎セッション読み込まれる。'
            'コネクタを使わないリポジトリでは、.claude/settings.local.jsonに"disableClaudeAiConnectors": trueを書くと読み込まれない。'
            'ユーザー設定でtrueにするとプロジェクト側で戻せない')

# ── 5. 古い書き方 ──
def audit_phrases(project):
    targets = [os.path.join(CLAUDE, 'CLAUDE.md'), os.path.join(project, 'CLAUDE.md')]
    targets += glob.glob(os.path.join(CLAUDE, 'rules', '**', '*.md'), recursive=True)
    targets += glob.glob(os.path.join(CLAUDE, 'skills', '*', 'SKILL.md'))
    targets += glob.glob(os.path.join(project, '.claude', 'skills', '*', 'SKILL.md'))
    hits = 0
    for f in targets:
        t = read(f) or ''
        for i, line in enumerate(t.splitlines(), 1):
            if OLD_PHRASES.search(line):
                hits += 1
                add('書き方', f'{short(f)}:{i}', '要確認', '「考えて」系の指示。Opus 5.5では不要とされている: ' + line.strip()[:60])
    if not hits:
        add('書き方', '「考えて」系の指示', 'OK', f'{len(targets)}ファイルで0件')

# ── 6. 権限 ──
def audit_permissions(user, project_settings):
    deny = list(((user or {}).get('permissions') or {}).get('deny') or [])
    deny += list(((project_settings or {}).get('permissions') or {}).get('deny') or [])
    if not deny:
        add('権限', 'deny', '要確認', 'denyが0件。.envや鍵の読み取りを止める設定が無い。denyは確認を増やさない')
    else:
        rel = [r for r in deny if re.match(r'^(Read|Edit)\(\*\*/', r)]
        add('権限', 'deny', 'OK', f'{len(deny)}件')
        if rel:
            add('権限', 'denyの書き方', '要確認', f'**/ は作業ディレクトリ基準で照合される。どこでも止めるなら //**/ にする: {", ".join(rel[:3])}')
    mode = ((user or {}).get('permissions') or {}).get('defaultMode')
    if mode == 'bypassPermissions' or (user or {}).get('skipDangerousModePermissionPrompt'):
        add('権限', 'bypassモード', '情報', '公式はコンテナやVMでの利用を推奨している。速度を優先して選んでいるなら、denyと署名などのhookで最低限を守る')

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    project = os.path.abspath(args[0] if args else os.getcwd())
    user = load_json(os.path.join(CLAUDE, 'settings.json')) or {}
    proj = load_json(os.path.join(project, '.claude', 'settings.json')) or {}
    local = load_json(os.path.join(project, '.claude', 'settings.local.json')) or {}
    merged_proj = {**proj, **local, 'enabledPlugins': {**(proj.get('enabledPlugins') or {}), **(local.get('enabledPlugins') or {})}}
    sources = [('ユーザー', user), ('プロジェクト', proj), ('プロジェクト(local)', local)]
    audit_instructions(project)
    audit_hooks(sources)
    audit_refs(sources, project)
    audit_plugins(user, merged_proj)
    audit_connectors(user, {**proj, **local})
    audit_phrases(project)
    audit_permissions(user, merged_proj)
    order = {'要確認': 0, '情報': 1, 'OK': 2}
    rows.sort(key=lambda r: order.get(r[2], 3))
    if '--json' in sys.argv:
        print(json.dumps([dict(zip(('kind', 'item', 'status', 'detail'), r)) for r in rows], ensure_ascii=False, indent=2))
        return
    print(f'# Claude Code環境の監査（{short(project)}）\n')
    print('| 状態 | 区分 | 項目 | 詳細 |\n| --- | --- | --- | --- |')
    for kind, item, status, detail in rows:
        print(f'| {status} | {kind} | {item} | {detail.replace("|", "/")} |')
    n = sum(1 for r in rows if r[2] == '要確認')
    print(f'\n要確認は{n}件。自動では直さない。直すかどうかは表を見て決める。')

if __name__ == '__main__':
    main()
