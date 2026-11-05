#!/usr/bin/env python3
"""同步课单元讲义 · 排版：读定稿 JSON，生成 渲染/本地化/同步-必修一-W-U2.html。

运行：python3 -I 本地化/脚本/同步排版.py
输入：本地化/内容/同步-必修一-W-U2.定稿.json
输出：渲染/本地化/同步-必修一-W-U2.html（内联结构，样式只用 同步.css 已有 class）

结构照抄 渲染/本地化/同步-样.html：单元头 → ① 考情 → ② 词性转换 → ③ 短语 → ④ 语法 → ⑤ 小测 → 答案。
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / '本地化' / '内容' / '同步-必修一-W-U2.定稿.json'
OUT = ROOT / '渲染' / '本地化' / '同步-必修一-W-U2.html'

BLANK_RE = re.compile(r'_{2,}')
CJK_RE = re.compile(r'[一-鿿]')
ASCII_RE = re.compile(r'[A-Za-z]')


def esc(s):
    return html.escape(s or '', quote=False)


def is_en(s):
    return len(ASCII_RE.findall(s)) > len(CJK_RE.findall(s))


def stem_html(text):
    return BLANK_RE.sub('<span class="blank"></span>', esc(text))


def show_answer(a):
    if a.get('answer_show'):
        return a['answer_show']
    t = re.sub(r'\s*[；;]\s*', ' ', a['答案'])
    return re.sub(r'\s+', ' ', t).strip()


def cue_html(cues):
    return ''.join(f' <span class="cue">（{esc(c)}）</span>' for c in cues or [])


def stem_p(text, cues=(), src=None):
    """题干段：英文为主的标 lang=en；纯中文不标。改写指令（cue）与出处（src）放句末。"""
    stem = stem_html(text) + cue_html(cues)
    if src is not None:
        stem += f' <span class="src">{esc(src)}</span>'
    if is_en(text):
        return f'<p lang="en">{stem}</p>'
    return f'<p>{stem}</p>'


def atom_li(a):
    p = stem_p(a['题干'], a.get('cue'))
    return f'<li data-no="{a["no"]}">{p}<span class="src">{esc(a["标签"])}</span></li>'


def chain_html(chain):
    out = []
    for c in chain:
        cls = 'form hit' if c['hit'] else 'form'
        inner = f'<b>{esc(c["词"])}</b>'
        if c['词性']:
            inner += f'<i>{esc(c["词性"])}</i>'
        if c['释义']:
            inner += f'<span class="zh">{esc(c["释义"])}</span>'
        out.append(f'<span class="{cls}">{inner}</span>')
    return ''.join(out)


def freq_section(u):
    rows = []
    for r in u['freq']:
        # 版面：形式列每行最多 3 个（按次数）；其余在报告里交代
        shown = r['forms'][:3]
        forms = ''.join(f'<span>{esc(f["form"])}<sub>{f["n"]}</sub></span>' for f in shown)
        how = ' · '.join(r['考法']) or '—'
        n = r['题数']
        bars = '<i></i>' * min(n, 12)
        rows.append(
            f'<tr><td>{esc(r["词头"])}</td><td class="forms">{forms}</td>'
            f'<td class="how">{esc(how)}</td><td class="tally">{bars}<span>{n}</span></td></tr>')
    ch = u['chips']
    return (
        '<section class="part">\n'
        f'  <header class="topic-head" data-no="1"><h3>东莞怎么考本单元</h3>'
        f'<span class="chip chip-freq">{esc(ch["year_range"])} · 东莞单句题 {ch["n_questions"]} 题</span></header>\n'
        '  <table class="freq">\n'
        '    <colgroup><col class="c-word"><col><col class="c-how"><col class="c-tally"></colgroup>\n'
        '    <thead><tr><th>词</th><th>东莞考过的形式</th><th>考法</th><th>题数</th></tr></thead>\n'
        '    <tbody>\n      ' + '\n      '.join(rows) + '\n    </tbody>\n  </table>\n'
        '</section>\n')


def family_section(u):
    parts = []
    for f in u['families']:
        atoms = '\n      '.join(atom_li(a) for a in f['atoms'])
        parts.append(
            '  <div class="family">\n'
            f'    <p class="fam-head" lang="en">{esc(f["词头"])}</p>\n'
            f'    <aside class="gloss">{f["gloss"]}</aside>\n'
            f'    <p class="fam-chain" lang="en">{chain_html(f["chain"])}</p>\n'
            f'    <ol class="atoms">\n      {atoms}\n    </ol>\n'
            '  </div>\n')
    ch = u['chips']
    return (
        '<section class="part">\n'
        f'  <header class="topic-head" data-no="2"><h3>词性转换</h3>'
        f'<span class="chip chip-freq">本单元 <b>{ch["n_kaofa"]}</b> 题</span></header>\n'
        '  <p class="lead"><span class="dot"></span>东莞考过的形式。先看空格修饰谁、作什么成分，再定词性。</p>\n'
        + ''.join(parts) + '</section>\n')


def phrase_section(u):
    parts = []
    for p in u['phrases']:
        atoms = '\n      '.join(atom_li(a) for a in p['atoms'])
        parts.append(
            '  <div class="phrase">\n'
            f'    <aside class="gloss">{p["gloss"]}</aside>\n'
            f'    <p class="ph"><b lang="en">{esc(p["短语"])}</b><span class="zh">{esc(p["释义"])}</span></p>\n'
            f'    <ol class="atoms">\n      {atoms}\n    </ol>\n'
            '  </div>\n')
    ch = u['chips']
    return (
        '<section class="part">\n'
        f'  <header class="topic-head" data-no="3"><h3>短语与句型</h3>'
        f'<span class="chip chip-freq">本单元 <b>{ch["n_phrase"]}</b> 题</span></header>\n'
        + ''.join(parts) + '</section>\n')


def explain_html(ex):
    out = ['      <div class="explain">']
    out.append(f'        <p class="subhead">{esc(ex["subhead"])}</p>')
    paras = ex['paragraphs']
    out.append(f'        <p>{esc(paras[0])}</p>')
    if ex.get('pattern'):
        out.append(f'        <p class="pattern" lang="en">{esc(ex["pattern"])}</p>')
    for p in paras[1:]:
        out.append(f'        <p>{esc(p)}</p>')
    cmp_ = ex.get('compare')
    if cmp_:
        head = ''.join(f'<th>{esc(h)}</th>' for h in cmp_['head'])
        body = ''.join('<tr>' + ''.join(f'<td>{esc(c)}</td>' for c in row) + '</tr>' for row in cmp_['rows'])
        out.append(f'        <table class="compare"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>')
    if ex.get('evidence'):
        text, page = ex['evidence']
        out.append(f'        <p lang="en" class="evidence">{esc(text)}〔{esc(page)}〕</p>')
    out.append('      </div>')
    return '\n'.join(out)


def grammar_section(u):
    g = u['grammar']
    ch = u['chips']
    ex_html = []
    for e in g['examples']:
        q = e['q']
        sol = e['solution']
        if '判断' in sol:
            mid = f'<p><b>判断</b>：{esc(sol["判断"])}</p>'
        else:
            mid = f'<p><b>成分</b>：{esc(sol["成分"])}</p>'
        ex_html.append(
            '    <article class="example">\n'
            '      <div class="stem">\n'
            f'        <aside class="gloss">{e["gloss"]}</aside>\n'
            f'        {stem_p(q["题干"], q.get("cue"), q["标签"])}\n'
            '      </div>\n'
            '      <div class="solution">\n'
            '        <h4>解析</h4>\n'
            f'        <p><b>句意</b>：{esc(sol["句意"])}</p>\n'
            f'        {mid}\n'
            + ('        <p class="ans-line"><b>故填</b><b class="ans">' + esc(sol["故填"]) + '</b></p>\n'
               if len(sol["故填"].split()) >= 6 else
               f'        <p><b>故填</b> <b class="ans">{esc(sol["故填"])}</b>。</p>\n') +
            '      </div>\n'
            '    </article>')
    drill = '\n      '.join(atom_li(a) for a in g['drill'])
    return (
        '<section class="part">\n'
        f'  <header class="topic-head" data-no="4"><h3>本单元语法</h3>'
        f'<span class="chip chip-freq">例 {len(g["examples"])} · 练 {len(g["drill"])}</span></header>\n'
        + explain_html(g['explain']) + '\n'
        + '\n'.join(ex_html) + '\n'
        '  <div class="drill">\n'
        '    <h4>练一练</h4>\n'
        '    <div class="drill-atoms">\n'
        f'      <ol class="atoms">\n      {drill}\n      </ol>\n'
        '    </div>\n'
        '  </div>\n'
        '</section>\n')


def quiz_section(u):
    ch = u['chips']
    items = '\n      '.join(atom_li(a) for a in u['quiz'])
    return (
        '<section class="part">\n'
        f'  <header class="topic-head" data-no="5"><h3>单元小测</h3>'
        f'<span class="chip chip-freq">本单元 <b>{len(u["quiz"])}</b> 题</span></header>\n'
        f'  <ol class="atoms">\n      {items}\n  </ol>\n'
        '</section>\n')


def answers_section(u):
    numbered = []
    for f in u['families']:
        numbered += f['atoms']
    for p in u['phrases']:
        numbered += p['atoms']
    numbered += u['grammar']['drill']
    numbered += u['quiz']
    numbered.sort(key=lambda a: a['no'])
    lis = []
    for a in numbered:
        show = show_answer(a)
        alt = ''
        if '（亦可' in show:
            # 亦可部分中文，放在 .ans（西文字体）之外，免得中文掉到系统字体
            show, rest = show.split('（亦可', 1)
            alt = '（亦可' + rest + ' '
        lis.append(f'<li data-no="{a["no"]}"><b class="ans">{esc(show.strip())}</b>{esc(alt)}{esc(a["reason"])}</li>')
    return (
        '<section class="part answers">\n'
        '  <header class="topic-head" data-no="答"><h3>答案与解析</h3></header>\n'
        '  <ol class="key">\n    ' + '\n    '.join(lis) + '\n  </ol>\n'
        '</section>\n')


def unit_section(u):
    stats = u['stats']
    book_title = u['unit_book'].split('　')[-1]
    head = (
        f'<section class="unit" data-unit="必修一 {esc(book_title)}">\n'
        f'<header class="unit-head" data-no="{u["data_no"]}">\n'
        f'  <p class="unit-book">{esc(u["unit_book"])}</p>\n'
        f'  <h2 lang="en">{esc(u["h2"])}<small>{esc(u["zh"])}</small></h2>\n'
        '  <ul class="unit-stats">'
        f'<li><b>{stats["卷数"]}</b>套东莞卷考过本单元</li>'
        f'<li><b>{stats["词数"]}</b>个词</li>'
        f'<li><b>{stats["短语数"]}</b>个短语</li>'
        f'<li><b>{stats["语法题数"]}</b>道语法题</li>'
        '</ul>\n'
        '</header>\n\n')
    body = (freq_section(u) + '\n' + family_section(u) + '\n' + phrase_section(u) + '\n'
            + grammar_section(u) + '\n' + quiz_section(u) + '\n' + answers_section(u))
    return head + body + '\n</section>\n'


def validate(S):
    errs = []
    for u in S['单元']:
        for p in u['grammar']['explain']['paragraphs']:
            if len(p) > 80:
                errs.append(f'{u["data_no"]} 讲解段超过 80 字：{p[:20]}…')
        if len(u['grammar']['explain']['paragraphs']) not in (2, 3):
            errs.append(f'{u["data_no"]} 讲解段数不是 2–3')
        if u['grammar'].get('explain', {}).get('compare') and len(u['grammar']['explain']['compare']['rows']) > 3:
            errs.append(f'{u["data_no"]} 辨析表超过 4 行（含表头）')
        for g in [f['gloss'] for f in u['families']] + [p['gloss'] for p in u['phrases']] + \
                 [e['gloss'] for e in u['grammar']['examples']]:
            for ln in g.split('<br>'):
                if len(CJK_RE.findall(ln)) > 10:
                    errs.append(f'{u["data_no"]} 柱注超过 10 字：{ln}')
            if len(g.split('<br>')) > 2:
                errs.append(f'{u["data_no"]} 柱注超过 2 行：{g}')
        if len(u['freq']) > 10:
            errs.append(f'{u["data_no"]} 考情表超过 10 行')
        if len(u['families']) > 8:
            errs.append(f'{u["data_no"]} 词族超过 8 个')
        for f in u['families']:
            if len(f['atoms']) > 2:
                errs.append(f'{u["data_no"]} 词族题超过 2 道')
            if len(f['chain']) > 4:
                errs.append(f'{u["data_no"]} 词族链超过 4 个形式')
        if len(u['phrases']) > 6:
            errs.append(f'{u["data_no"]} 短语超过 6 条')
        if len(u['quiz']) > 8:
            errs.append(f'{u["data_no"]} 小测超过 8 道')
        nos = sorted(a['no'] for a in
                     [a for f in u['families'] for a in f['atoms']] +
                     [a for p in u['phrases'] for a in p['atoms']] +
                     u['grammar']['drill'] + u['quiz'])
        if nos != list(range(1, len(nos) + 1)):
            errs.append(f'{u["data_no"]} 编号不连续：{nos[:5]}…')
    return errs


def main():
    S = json.loads(SRC.read_text(encoding='utf-8'))
    errs = validate(S)
    if errs:
        for e in errs:
            print('错误', e, file=sys.stderr)
        raise SystemExit(1)
    body = ''.join(unit_section(u) for u in S['单元'])
    doc = ('<!DOCTYPE html>\n<html lang="zh-Hans">\n<head><meta charset="UTF-8">'
           '<meta name="viewport" content="width=device-width, initial-scale=1">'
           '<title>同步课单元讲义 · 必修一 W–U2</title>'
           '<link rel="stylesheet" href="同步.css"></head>\n<body>\n'
           + body + '</body>\n</html>\n')
    OUT.write_text(doc, encoding='utf-8')
    print('写入', OUT)


if __name__ == '__main__':
    main()
