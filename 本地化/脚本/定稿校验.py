#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定稿校验（只读）：检查 本地化/内容 下的定稿是否仍与当前题库一致。渲染前必须通过。

用法（仓库根目录）：
    python3 -I 本地化/脚本/定稿校验.py

输入：本地化/数据/题库.jsonl（只读）；本地化/内容/同步-*.定稿.json、段考-*.定稿.json（段考-样 除外）。
输出：每册一行汇总，然后逐条列出问题；有问题则退出码为 1。不改任何文件。

检查内容：
  同步-*.定稿.json（每册一份，如 同步-必修一.定稿.json）
    逐单元检查题的节：families[].atoms（②）、spelling（③ 单词拼写）、phrases[].atoms（③ 短语）、
    tricks[].atoms（③ 句式）、quiz（⑤ 小测）。缺节、或有带 id 的题落在以上之外的位置，都报为问题。
    · id 须在题库中存在；
    · 定稿 题干 与题库 题干一致（比较前规范化）；
    · 定稿 答案 与题库 答案一致（规范化后）。定稿有 answer_show 的，答案页已改写，只提示，不比对答案。
  段考-*.定稿.json（不含 段考-样）
    不存 id，只存题干和出处 src。对每个例题 stem 与每个 drill stem：
    · 在题库中找题干规范化后相等的题（找不到相等的，再找包含关系的）；
    · 候选中须有 标签 与 src 一致的题（优先在相等的候选里找）；
    · 符合出处的候选题干都相同才算唯一；题干不同则报为无法唯一定位。

规范化（两边用同一套规则，见 norm_stem）：
  · 全半角标点统一（括号、逗号、句号、引号、撇号等）；
  · 去掉所有空白；
  · [_…_] 划线标记去掉，只留内容；
  · 指令括号去掉（含 改写 / 转换 / 翻译 / 填空 / 强调 / 用…句 等字样的括号；词形提示如 (explore) 保留）；
  · 下划线空位统一为 _；
  · →、=、换行视为同一分隔符 |；改写题末尾的「→ ___」（待填目标行）不参与比较；
  · 标签与出处比较时，统一「·」符号并去掉空白。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / '本地化' / '数据'
CONTENT = ROOT / '本地化' / '内容'

PUNCT = str.maketrans({
    '，': ',', '。': '.', '；': ';', '：': ':', '？': '?', '！': '!', '．': '.',
    '（': '(', '）': ')', '［': '[', '］': ']',
    '“': '"', '”': '"', '‘': "'", '’': "'",
    '＝': '=', '　': ' ', ' ': ' ', ' ': ' ',
})
DOT_RE = re.compile(r'[·•・]')
EMPH_RE = re.compile(r'\[_(.*?)_\]', re.S)
PAREN_RE = re.compile(r'\(([^()]*)\)')
INSTR_RE = re.compile(
    r'改写|转换|同义|翻译|译|填空|拼写|完成句子|合并|改为|改成|变成|强调|句型|句式|转述|间接引语|'
    r'被动|倒装|从句|语态|汉语提示|首字母|适当形式|正确形式|汉译英|英译汉|分词|不定式|动名词|作(?:状|定|表|宾|主|补|同位)语|'
    r'用[^()]{0,12}(?:句|词|形式|从句|改写|转换|合并)'
)
SEP_RE = re.compile(r'\s*(?:→|=|\n)\s*')


def _drop_instr(m):
    return ' ' if INSTR_RE.search(m.group(1)) else m.group(0)


def norm_stem(s):
    s = (s or '').translate(PUNCT)
    s = EMPH_RE.sub(r'\1', s)
    s = PAREN_RE.sub(_drop_instr, s)
    s = re.sub(r'_+', '_', s)
    s = SEP_RE.sub('|', s)
    s = re.sub(r'\s+', '', s)
    s = re.sub(r'\|+', '|', s)
    s = re.sub(r'(?:\|_)+$', '', s)
    return s.strip('|')


def norm_ans(s):
    return re.sub(r'\s+', '', (s or '').translate(PUNCT))


def norm_tag(s):
    return re.sub(r'\s+', '', DOT_RE.sub('·', s or ''))


def snip(s, n=40):
    return (s or '').replace('\n', ' / ')[:n]


def load_bank():
    with open(DATA / '题库.jsonl', encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def walk_ids(node, path, out):
    """收集所有带 id 的 dict，路径形如 单元[0].families[2].atoms[1]。"""
    if isinstance(node, dict):
        if 'id' in node:
            out.append((path, node))
        for k, v in node.items():
            walk_ids(v, f'{path}.{k}' if path else k, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_ids(v, f'{path}[{i}]', out)


SYNC_SECTIONS = ('families', 'spelling', 'phrases', 'tricks', 'quiz')


def sync_atoms(p, doc, problems):
    """按节收集同步定稿的题：每单元 families / spelling / phrases / tricks / quiz。
    缺节报问题；带 id 的题若不在这些节里（walk_ids 全量统计对不上），也报问题。"""
    atoms = []
    for i, u in enumerate(doc.get('单元', [])):
        tag = f'单元[{i}]({u.get("data_no", "?")})'
        for sec in SYNC_SECTIONS:
            if sec not in u:
                problems.append((p.name, tag, f'缺 {sec} 节'))
        for j, f in enumerate(u.get('families', [])):
            for k, a in enumerate(f.get('atoms', [])):
                atoms.append((f'{tag}.families[{j}].atoms[{k}]', a))
        for k, a in enumerate(u.get('spelling', [])):
            atoms.append((f'{tag}.spelling[{k}]', a))
        for j, ph in enumerate(u.get('phrases', [])):
            for k, a in enumerate(ph.get('atoms', [])):
                atoms.append((f'{tag}.phrases[{j}].atoms[{k}]', a))
        for j, t in enumerate(u.get('tricks', [])):
            for k, a in enumerate(t.get('atoms', [])):
                atoms.append((f'{tag}.tricks[{j}].atoms[{k}]', a))
        for k, a in enumerate(u.get('quiz', [])):
            atoms.append((f'{tag}.quiz[{k}]', a))
    walked = []
    walk_ids(doc, '', walked)
    if len(walked) != len(atoms):
        problems.append((p.name, '全文', f'带 id 的题 {len(walked)} 道，按节检查 {len(atoms)} 道，有题落在已知节之外'))
    return atoms


def check_sync(p, bank_by_id, problems, notices):
    doc = json.loads(p.read_text(encoding='utf-8'))
    atoms = sync_atoms(p, doc, problems)
    n_ok = 0
    for loc, atom in atoms:
        qid = atom['id']
        where = f"{loc} id={qid}「{snip(atom.get('题干'))}」"
        q = bank_by_id.get(qid)
        if q is None:
            problems.append((p.name, where, '题库中无此 id'))
            continue
        bad = []
        if norm_stem(atom.get('题干')) != norm_stem(q.get('题干')):
            bad.append(f"题干不一致：定稿「{snip(atom.get('题干'))}」，题库「{snip(q.get('题干'))}」")
        if atom.get('answer_show'):
            notices.append((p.name, where, '答案页已改写（未比对答案）'))
        elif norm_ans(atom.get('答案')) != norm_ans(q.get('答案')):
            bad.append(f"答案不一致：定稿「{snip(atom.get('答案'), 30)}」，题库「{snip(q.get('答案'), 30)}」")
        for reason in bad:
            problems.append((p.name, where, reason))
        if not bad:
            n_ok += 1
    return len(atoms), n_ok


def locate(stem, src, pool):
    """在题库中定位一道段考题。pool = [(规范化题干, 题行)]。返回 (题行, 原因)；原因为 None 表示唯一定位。"""
    ns = norm_stem(stem)
    exact = [q for n, q in pool if n == ns]
    contained = [q for n, q in pool if ns and n and n != ns and (ns in n or n in ns)]
    cands = exact + contained
    if not cands:
        return None, '题库中找不到（题干既不相等也不包含）'
    for group in (exact, cands):
        same = [q for q in group if norm_tag(q.get('标签')) == norm_tag(src)]
        if same:
            break
    else:
        tags = sorted({q.get('标签') or '' for q in cands})
        return None, f"出处不符：定稿 src「{src}」，题库候选标签 {tags}"
    distinct = {norm_stem(q.get('题干')) for q in same}
    if len(distinct) > 1:
        return None, '符合出处的候选题干不同，无法唯一定位：' + ' ／ '.join(snip(q.get('题干'), 30) for q in same[:3])
    return same[0], None


def check_duankao(p, pool, problems):
    doc = json.loads(p.read_text(encoding='utf-8'))
    stems = []
    for t in doc.get('topics', []):
        name = t.get('name', '')
        for i, e in enumerate(t.get('examples', [])):
            stems.append((f'{name} 例题[{i}]', e['stem']['text'], e['stem'].get('src')))
        for i, x in enumerate(t.get('drill', [])):
            stems.append((f'{name} 练一练[{i}]', x['stem'], x.get('src')))
    n_ok = 0
    for loc, stem, src in stems:
        q, reason = locate(stem, src, pool)
        if reason:
            problems.append((p.name, f'{loc}「{snip(stem)}」', reason))
        else:
            n_ok += 1
    return len(stems), n_ok


def main():
    bank = load_bank()
    bank_by_id = {q['id']: q for q in bank}
    pool = [(norm_stem(q.get('题干')), q) for q in bank]
    tong = sorted(CONTENT.glob('同步-*.定稿.json'))
    duan = sorted(p for p in CONTENT.glob('段考-*.定稿.json') if not p.name.startswith('段考-样'))
    if not tong and not duan:
        print('未找到定稿（本地化/内容/同步-*.定稿.json、段考-*.定稿.json）')
        return 1

    problems, notices = [], []
    lines = []
    for p in tong:
        n, ok = check_sync(p, bank_by_id, problems, notices)
        lines.append(f'{p.name}：检查 {n} 题，通过 {ok}')
    for p in duan:
        n, ok = check_duankao(p, pool, problems)
        lines.append(f'{p.name}：检查 {n} 题，通过 {ok}')

    print(f'定稿校验 · 题库 {len(bank)} 题')
    for ln in lines:
        print(ln)
    if notices:
        print('\n提示（不计入问题）：')
        for f, where, msg in notices:
            print(f'  [{f}] {where}：{msg}')
    print()
    if problems:
        print(f'问题 {len(problems)} 条：')
        for f, where, msg in problems:
            print(f'  [{f}] {where}：{msg}')
        return 1
    print('问题：无')
    return 0


if __name__ == '__main__':
    sys.exit(main())
