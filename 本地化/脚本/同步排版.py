#!/usr/bin/env python3
"""同步课单元讲义 · 排版：读定稿 JSON，生成 渲染/本地化/同步-必修一-W-U2.html。

运行：python3 -I 本地化/脚本/同步排版.py
输入：本地化/内容/同步-必修一-W-U2.定稿.json
输出：渲染/本地化/同步-必修一-W-U2.html（内联结构，样式只用 同步.css 已有 class）

结构：单元头 → ① 单元考情 → ② 词性转换 → ③ 短语与句式转换 → ⑤ 单元小测 → 答案。
③ 前半是短语块（.phrase），后半先一行「句式转换」（.lead），再接句式块（.phrase.trick）。

定稿 JSON 的字段（每个单元）：
  序、data_no、unit_book、h2、zh、chips{year_range, n_questions, n_kaofa, n_phrase}
  stats{卷数, 词数, 短语数, 句式题数}
  freq[{词头, forms[{form, n}], 考法[], 题数}]                     ① 考情总表
  families[{词头, gloss, chain[{词, 词性, 释义, hit, 来源}], atoms}]  ② 词族行
  phrases[{短语, 释义, 词头, gloss, atoms}]                       ③ 前半：短语块（可无题）
  tricks[{句式, gloss, formula, atoms}]                          ③ 后半：句式块
      句式：句式名，≤6 字
      gloss：两行，第一行「M 题」（M 与 atoms 数一致），第二行 ≤10 字
      formula：一行，「原句骨架 → 改后骨架」，≤50 字符，取自本块原题
  quiz[atoms]                                                    ⑤ 单元小测
  numbered_total
每道题 atoms 的字段：id、no（每单元内 ② ③ ⑤ 连续编号）、标签、题型、题干、题干HTML、
  cue[]（改写指令，放句末）、答案、解析、句意、reason（≤20 字，答案页用）
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
        f'  <header class="topic-head" data-no="1"><h3>单元考情</h3>'
        f'<span class="chip chip-freq">{esc(ch["year_range"])} · 东莞真题 {ch["n_questions"]} 道</span></header>\n'
        '  <table class="freq">\n'
        '    <colgroup><col class="c-word"><col><col class="c-how"><col class="c-tally"></colgroup>\n'
        '    <thead><tr><th>词汇</th><th>考查形式</th><th>考法</th><th>频次</th></tr></thead>\n'
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
        f'<span class="chip chip-freq">真题 <b>{ch["n_kaofa"]}</b> 道</span></header>\n'
        '  <p class="lead"><span class="dot"></span>为东莞真题考过的形式</p>\n'
        + ''.join(parts) + '</section>\n')


def phrase_html(p):
    atoms = '\n      '.join(atom_li(a) for a in p['atoms'])
    return (
        '  <div class="phrase">\n'
        f'    <aside class="gloss">{p["gloss"]}</aside>\n'
        f'    <p class="ph"><b lang="en">{esc(p["短语"])}</b><span class="zh">{esc(p["释义"])}</span></p>\n'
        f'    <ol class="atoms">\n      {atoms}\n    </ol>\n'
        '  </div>\n')


def trick_html(t):
    atoms = '\n      '.join(atom_li(a) for a in t['atoms'])
    # 公式不包 <b>：同步.css 的 .trick > .ph > b（10.5pt、arrow 字体）与 12pt 段落混排，会把行盒撑高 0.56pt，
    # 半格对不齐。公式直接放在 .ph 里，字号、字重与短语名相同。
    return (
        '  <div class="phrase trick">\n'
        f'    <p class="fam-head">{esc(t["句式"])}</p>\n'
        f'    <aside class="gloss">{t["gloss"]}</aside>\n'
        f'    <p class="ph">{esc(t["formula"])}</p>\n'
        f'    <ol class="atoms">\n      {atoms}\n    </ol>\n'
        '  </div>\n')


def phrase_section(u):
    ch = u['chips']
    return (
        '<section class="part">\n'
        f'  <header class="topic-head" data-no="3"><h3>短语与句式转换</h3>'
        f'<span class="chip chip-freq">真题 <b>{ch["n_phrase"]}</b> 道</span></header>\n'
        + ''.join(phrase_html(p) for p in u['phrases'])
        + '  <p class="lead">句式转换</p>\n'
        + ''.join(trick_html(t) for t in u['tricks'])
        + '</section>\n')


def quiz_section(u):
    items = '\n      '.join(atom_li(a) for a in u['quiz'])
    return (
        '<section class="part">\n'
        f'  <header class="topic-head" data-no="4"><h3>单元小测</h3>'
        f'<span class="chip chip-freq"><b>{len(u["quiz"])}</b> 道</span></header>\n'
        f'  <ol class="atoms">\n      {items}\n  </ol>\n'
        '</section>\n')


def answers_section(u):
    numbered = []
    for f in u['families']:
        numbered += f['atoms']
    for p in u['phrases']:
        numbered += p['atoms']
    for t in u['tricks']:
        numbered += t['atoms']
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
        f'<li><b>{stats["卷数"]}</b>套试卷</li>'
        f'<li><b>{stats["词数"]}</b>个词汇</li>'
        f'<li><b>{stats["短语数"]}</b>个短语</li>'
        f'<li><b>{stats["句式题数"]}</b>道句式转换</li>'
        '</ul>\n'
        '</header>\n\n')
    body = (freq_section(u) + '\n' + family_section(u) + '\n' + phrase_section(u) + '\n'
            + quiz_section(u) + '\n' + answers_section(u))
    return head + body + '\n</section>\n'


def validate(S):
    errs = []
    for u in S['单元']:
        if 'grammar' in u:
            errs.append(f'{u["data_no"]} 仍含已删除的 grammar 节')
        glosses = [('②', f['gloss']) for f in u['families']] + [('③', p['gloss']) for p in u['phrases']]
        glosses += [('句式', t['gloss']) for t in u['tricks']]
        for tag, g in glosses:
            for ln in g.split('<br>'):
                if len(CJK_RE.findall(ln)) > 10:
                    errs.append(f'{u["data_no"]} {tag} 柱注超过 10 字：{ln}')
            if len(g.split('<br>')) > 2:
                errs.append(f'{u["data_no"]} {tag} 柱注超过 2 行：{g}')
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
        if not 1 <= len(u['tricks']) <= 4:
            errs.append(f'{u["data_no"]} 句式块数不在 1–4')
        for t in u['tricks']:
            if len(t['句式']) > 6:
                errs.append(f'{u["data_no"]} 句式名超过 6 字：{t["句式"]}')
            if not 1 <= len(t['atoms']) <= 3:
                errs.append(f'{u["data_no"]} 句式「{t["句式"]}」题数不在 1–3')
            first = t['gloss'].split('<br>')[0]
            if first != f'{len(t["atoms"])} 题':
                errs.append(f'{u["data_no"]} 句式「{t["句式"]}」柱注第一行与题数不符：{first}')
            if '\n' in t['formula'] or len(t['formula']) > 50:
                errs.append(f'{u["data_no"]} 句式「{t["句式"]}」公式超过 50 字符或多行')
        if len(u['quiz']) > 8:
            errs.append(f'{u["data_no"]} 小测超过 8 道')
        nos = sorted(a['no'] for a in
                     [a for f in u['families'] for a in f['atoms']] +
                     [a for p in u['phrases'] for a in p['atoms']] +
                     [a for t in u['tricks'] for a in t['atoms']] + u['quiz'])
        if nos != list(range(1, len(nos) + 1)):
            errs.append(f'{u["data_no"]} 编号不连续：{nos[:5]}…')
        if u['stats']['句式题数'] != sum(len(t['atoms']) for t in u['tricks']):
            errs.append(f'{u["data_no"]} 句式题数与句式块不符')
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
           '<title>同步讲义 · 必修一 W–U2</title>'
           '<link rel="stylesheet" href="同步.css"></head>\n<body>\n'
           + body + '</body>\n</html>\n')
    OUT.write_text(doc, encoding='utf-8')
    print('写入', OUT)


if __name__ == '__main__':
    main()
