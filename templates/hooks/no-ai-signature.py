#!/usr/bin/env python3
"""PreToolUse(Bash)フック: 利用者の名義で外に出る文にClaude関連の署名と絵文字を入れさせない。

対象は git commit と gh の pr / issue / release / api。コマンド文字列と、--body-file / -F / --file で
渡したファイルの中身を検査する。それ以外のコマンドはすぐに終わる。
禁止事項を引用する必要があるときだけ、コマンドの先頭に ALLOW_AI_SIGNATURE=1 を付ける。
"""
import json, os, re, shlex, sys

TARGET = re.compile(r'\b(git\s+(-C\s+\S+\s+)?commit|gh\s+(pr|issue|release|api))\b')
SIGNS = [
    (re.compile(r'Generated (with|by) \[?Claude Code', re.I), 'Generated with Claude Code'),
    (re.compile(r'Co-Authored-By:\s*Claude', re.I), 'Co-Authored-By: Claude'),
    (re.compile(r'noreply@anthropic\.com', re.I), 'noreply@anthropic.com'),
    # Claude Docsなどの成果物のリンク(claude.ai/code/artifact/...)は署名ではないので除く
    (re.compile(r'claude\.(ai/code(?!/artifact)|com/claude-code)', re.I), 'Claude Codeへのリンク'),
    (re.compile('[\U0001F300-\U0001FAFF]'), '絵文字'),
]
FILE_OPTS = ('--body-file', '-F', '--file', '--message-file')

def files_in(command, cwd):
    try:
        toks = shlex.split(command, posix=True)
    except ValueError:
        return []
    out = []
    for i, t in enumerate(toks):
        val = None
        if t in FILE_OPTS and i + 1 < len(toks):
            val = toks[i + 1]
        else:
            for o in FILE_OPTS:
                if o.startswith('--') and t.startswith(o + '='):
                    val = t.split('=', 1)[1]
        if val and val != '-':
            p = os.path.expanduser(val)
            out.append(p if os.path.isabs(p) else os.path.join(cwd, p))
    return out

def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    command = (data.get('tool_input') or {}).get('command') or ''
    if not TARGET.search(command) or 'ALLOW_AI_SIGNATURE=1' in command:
        return 0
    texts = [command]
    for f in files_in(command, data.get('cwd') or os.getcwd()):
        try:
            with open(f, encoding='utf-8', errors='replace') as fh:
                texts.append(fh.read())
        except OSError:
            pass
    found = sorted({label for t in texts for rx, label in SIGNS if rx.search(t)})
    if not found:
        return 0
    print('no-ai-signature: 利用者の名義で出る文にClaude関連の署名または絵文字があります: '
          + ', '.join(found)
          + '。取り除いてから実行し直してください。禁止事項の引用が必要な場合だけ、コマンドの先頭に ALLOW_AI_SIGNATURE=1 を付けます。',
          file=sys.stderr)
    return 2

if __name__ == '__main__':
    sys.exit(main())
