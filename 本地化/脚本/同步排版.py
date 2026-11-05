#!/usr/bin/env python3
"""同步课单元讲义 · 排版（英式，规范/04 §7）：读定稿 JSON，生成 渲染/本地化/同步-必修一-W-U2.html。

运行：python3 -I 本地化/脚本/同步排版.py
输入：本地化/内容/同步-必修一-W-U2.定稿.json
输出：渲染/本地化/同步-必修一-W-U2.html（引 英式.css；样式只用 英式.css 的 class）

结构（每单元起新页）：单元头 → ① 单元考情（考情表）→ ② 词性转换（词族）→ ③ 单词拼写 → ④ 短语与句式转换 → ⑤ 单元小测 → 答案与解析。
  单元头：kicker（册名）+ 英文单元名 30pt + 中文名 14pt 同行 + 统计行；单元号做右上角角标。
  ①：.freq 表，词汇 / 考查形式 / 考法 / 频次。
  ②：每个词族 .family = 词头行（词头 + gloss 同一行）+ 词族链（.fam-chain 浅底条）+ 原题（.atoms）。
  ③：单词拼写：节头（无 chip）+ 原题列表（6–8 道，给中文提示写英文单词）。
  ④：短语块 .phrase（.ph：短语 + 释义 + gloss 同一行）+ 原题；随后一行「句式转换」描边药丸（.lead）；
      句式块 .phrase.trick（句式名药丸 + gloss 同行 / 公式浅底条 / 原题）。
  ⑤：原题列表。
  答案：一个标题 + 两栏 key，不分组。
原题（atoms）：出处 <span class="src"> 放题干段行首，后空 1 字接题干；改写指令 cue 仍在句末。
英式结构的 class 与段考英式（段考排版.py）同名的沿用；同步专用的 freq、family、fam-head、fam-chain、phrase、ph、trick、form、zh、tally、dot 由 英式.css 同步讲义段（文件末）定义。

定稿 JSON 的字段（每个单元）：
  序、data_no、unit_book、h2、zh、chips{year_range, n_questions, n_kaofa, n_phrase}
  stats{卷数, 词数, 短语数, 句式题数}
  freq[{词头, forms[{form, n}], 考法[], 题数}]                     ① 考情总表（本单元考过的全部词）
  families[{词头, 题数, gloss, chain[{词, 词性, 释义, hit, 来源}], atoms}]  ② 词族行（每个词族的原题；每个形式一道）
      gloss：一到两行，多行在排版时用「 · 」接成一行
  spelling[atoms]                                                ③ 单词拼写（6–8 道，每词一道）
  phrases[{短语, 释义, 词头, gloss, atoms}]                       ④ 前半：短语块（可无题）
  tricks[{句式, gloss, formula, atoms}]                          ④ 后半：句式块
      句式：句式名，≤6 字
      gloss：两行，第一行「M 题」（M 与 atoms 数一致），第二行 ≤10 字
      formula：一行，「原句骨架 → 改后骨架」，≤50 字符，取自本块原题
  quiz[atoms]                                                    ⑤ 单元小测
  numbered_total
每道题 atoms 的字段：id、no（每单元内 ② ③ ④ ⑤ 连续编号）、标签、题型、题干、题干HTML、
  cue[]（改写指令，放句末）、答案、解析、句意、reason（≤20 字，答案页用）、answer_show（可空）
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / '本地化' / '内容' / '同步-必修一-W-U2.定稿.json'
OUT = ROOT / '渲染' / '本地化' / '同步-必修一-W-U2.html'


def src_text(label):
    """出处显示（所有者定，2026-11-05）：「2023 · 学校 · 高一上月考」显示为「2023 学校高一上月考」——年份后空一格，校名与考试连写。
    数据（题库标签、定稿 src）不变，只改显示。"""
    parts = (label or '').split(' · ')
    if len(parts) == 3:
        return f'{parts[0]} {parts[1]}{parts[2]}'
    return label or ''

BLANK_RE = re.compile(r'_{2,}')
CJK_RE = re.compile(r'[一-鿿]')
ASCII_RE = re.compile(r'[A-Za-z]')
HYPHEN_RE = re.compile(r'(?<=[\s>（(])-(?=[A-Za-z])')   # 独立的 -ing / -ed 前缀，连字符后不断行（同段考英式）


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


def gloss_line(g):
    """柱注多行合成一行，用「 · 」接起（英式没有柱）。"""
    return '；'.join(x for x in g.split('<br>') if x)   # 两条提示用分号接（不用「 · 」，所有者 2026-11-05）


# ── 作答方式（2026-11-05 所有者定）──
# whole：整句作答（题干无空，或以「→ ___」收尾）→ 题下单独两条书写横线 <div class="answer-lines">，去掉句末的「→ ___」；
# half ：给了改写句框架、只填中间（有「→」且空在句中）→ 空位加长 <span class="blank long">；
# normal：其余（含单句改错）不变。只用于练习题（练一练 / 原题），例题不加。
ANSWER_LINES = '<div class="answer-lines"></div>'
_TAIL_BLANK_RE = re.compile(r'\s*(?:→|=)\s*_{2,}\s*[。.]?\s*$')


def answer_mode(stem, cues=None):
    if '改错' in ''.join(cues or []):
        return 'normal'
    s = (stem or '').replace('\n', ' → ').strip()
    if not re.search(r'_{2,}', s) or _TAIL_BLANK_RE.search(s):
        return 'whole'
    return 'half' if '→' in s else 'normal'


def strip_tail_blank(stem):
    return _TAIL_BLANK_RE.sub('', stem or '')


def atom_li(a):
    """原题：出处在题干行首（后空 1 字接题干，CSS 定），改写指令仍在句末。"""
    mode = answer_mode(a['题干'], a.get('cue'))
    text = strip_tail_blank(a['题干']) if mode == 'whole' else a['题干']
    stem = stem_html(text)
    if mode == 'half':
        stem = stem.replace('<span class="blank"></span>', '<span class="blank long"></span>')
    body = f'<span class="src">{esc(src_text(a["标签"]))}</span>' + stem + cue_html(a.get('cue'))
    lang = ' lang="en"' if is_en(text) else ''
    tail = ANSWER_LINES if mode == 'whole' else ''
    return f'<li data-no="{a["no"]}"><p{lang}>{body}</p>{tail}</li>'


def atoms_html(atoms):
    return '<ol class="atoms">\n      ' + '\n      '.join(atom_li(a) for a in atoms) + '\n    </ol>\n'


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


def freq_tier(n):
    """考情表按频次分档（2026-11-05：档内不画行线，档与档之间空半格加细线，减轻密度）。"""
    return 0 if n >= 5 else 1 if n >= 3 else 2 if n == 2 else 3


def freq_section(u):
    groups = {}
    for r in u['freq']:
        # 版面：形式列每行最多 3 个（按次数）；其余在报告里交代
        shown = r['forms'][:3]
        forms = ''.join(f'<span>{esc(f["form"])}<sub>{f["n"]}</sub></span>' for f in shown)
        how = '、'.join(r['考法']) or '—'
        n = r['题数']
        bars = '<i></i>' * min(n, 12)
        groups.setdefault(freq_tier(n), []).append(
            f'<tr><td>{esc(r["词头"])}</td><td class="forms">{forms}</td>'
            f'<td class="how">{esc(how)}</td><td class="tally">{bars}<span>{n}</span></td></tr>')
    bodies = ''.join('    <tbody>\n      ' + '\n      '.join(groups[k]) + '\n    </tbody>\n'
                     for k in sorted(groups))
    ch = u['chips']
    return (
        '<section class="part">\n'
        f'  <header class="topic-head" data-no="1"><h3>单元考情</h3>'
        f'<span class="chip chip-freq">{esc(ch["year_range"])} 东莞真题 {ch["n_questions"]} 道</span></header>\n'
        '  <table class="freq">\n'
        '    <colgroup><col class="c-word"><col><col class="c-how"><col class="c-tally"></colgroup>\n'
        '    <thead><tr><th>词汇</th><th>考查形式</th><th>考法</th><th>频次</th></tr></thead>\n'
        + bodies + '  </table>\n'
        '</section>\n')


def family_section(u):
    parts = []
    for f in u['families']:
        parts.append(
            '  <div class="family">\n'
            f'    <p class="fam-head" lang="en">{esc(f["词头"])}<span class="gloss">{gloss_line(f["gloss"])}</span></p>\n'
            f'    <p class="fam-chain" lang="en">{chain_html(f["chain"])}</p>\n'
            '    ' + atoms_html(f['atoms']) +
            '  </div>\n')
    ch = u['chips']
    return (
        '<section class="part">\n'
        f'  <header class="topic-head" data-no="2"><h3>词性转换</h3>'
        '</header>\n'   # 不报题库计数（所有者 2026-11-05：不散报数据）
        '  <p class="lead"><span class="dot"></span>东莞考过的形式</p>\n'
        + ''.join(parts) + '</section>\n')


def phrase_html(p):
    """短语条。可带「对照」：{短语, 释义}——教材常见但东莞没考的相关搭配，与实考搭配并列，
    实考的那个加主色圆点、半粗（同词族链的 hit），对照在前。"""
    if p.get('对照'):
        alt = p['对照']
        head = (f'<span class="form"><b>{esc(alt["短语"])}</b><span class="zh">{esc(alt["释义"])}</span></span>'
                f'<span class="form hit"><b>{esc(p["短语"])}</b><span class="zh">{esc(p["释义"])}</span></span>')
        cls = 'ph pair'
    else:
        head = f'<b>{esc(p["短语"])}</b><span class="zh">{esc(p["释义"])}</span>'
        cls = 'ph'
    return (
        '  <div class="phrase">\n'
        f'    <p class="{cls}" lang="en">{head}'
        f'<span class="gloss">{gloss_line(p["gloss"])}</span></p>\n'
        '    ' + atoms_html(p['atoms']) +
        '  </div>\n')


def trick_html(t):
    # 公式放 .ph（lang=en，12pt STIX 粗），由 英式.css 垫在 --accent-wash 条里；不包 <b>，免得字号与行盒走样
    return (
        '  <div class="phrase trick">\n'
        f'    <p class="fam-head"><span class="subhead">{esc(t["句式"])}</span>'
        f'<span class="gloss">{gloss_line(t["gloss"])}</span></p>\n'
        f'    <p class="ph" lang="en">{esc(t["formula"])}</p>\n'
        '    ' + atoms_html(t['atoms']) +
        '  </div>\n')


def spelling_section(u):
    """③ 单词拼写：节头不加 chip（不报题数）；原题列表，复用 atoms_html。"""
    return (
        '<section class="part">\n'
        '  <header class="topic-head" data-no="3"><h3>单词拼写</h3></header>\n'
        '  ' + atoms_html(u['spelling']) +
        '</section>\n')


def phrase_section(u):
    ch = u['chips']
    return (
        '<section class="part">\n'
        f'  <header class="topic-head" data-no="4"><h3>短语与句式转换</h3>'
        '</header>\n'
        + ''.join(phrase_html(p) for p in u['phrases'])
        + '  <p class="lead"><b>句式转换</b></p>\n'
        + ''.join(trick_html(t) for t in u['tricks'])
        + '</section>\n')


def quiz_section(u):
    items = '\n      '.join(atom_li(a) for a in u['quiz'])
    return (
        '<section class="part">\n'
        f'  <header class="topic-head" data-no="5"><h3>单元小测</h3>'
        '</header>\n'
        f'  <ol class="atoms">\n      {items}\n  </ol>\n'
        '</section>\n')


def answers_section(u):
    numbered = []
    for f in u['families']:
        numbered += f['atoms']
    numbered += u['spelling']
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
    book_title = u['unit_book'].split('　')[-1]
    kicker = u['unit_book'].split('　')[0]          # 册名；英文单元名已在标题行
    head = (
        f'<section class="unit" data-unit="必修一 {esc(book_title)}">\n'
        f'<header class="unit-head" data-no="{u["data_no"]}">\n'
        f'  <p class="unit-book">{esc(kicker)}</p>\n'
        f'  <h2 lang="en">{esc(u["h2"])}<small>{esc(u["zh"])}</small></h2>\n'
        '</header>\n\n')
    body = (freq_section(u) + '\n' + family_section(u) + '\n' + spelling_section(u) + '\n'
            + phrase_section(u) + '\n' + quiz_section(u) + '\n' + answers_section(u))
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
        for f in u['families']:
            if len(f['chain']) > 4:
                errs.append(f'{u["data_no"]} 词族链超过 4 个形式')
        if not 6 <= len(u['spelling']) <= 8:
            errs.append(f'{u["data_no"]} 单词拼写题数不在 6–8')
        if len({a['提示词'] or a['题干'] for a in u['spelling']}) != len(u['spelling']):
            errs.append(f'{u["data_no"]} 单词拼写有重复的题')
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
                     [a for f in u['families'] for a in f['atoms']] + u['spelling'] +
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
    body = HYPHEN_RE.sub('-⁠', body)   # U+2060 词连接符（零宽）：「用 -ing」的连字符后不断行
    doc = ('<!DOCTYPE html>\n<html lang="zh-Hans">\n<head><meta charset="UTF-8">'
           '<meta name="viewport" content="width=device-width, initial-scale=1">'
           '<title>同步讲义 · 必修一 W–U2</title>'
           '<link rel="stylesheet" href="英式.css"></head>\n<body>\n'
           + body + '</body>\n</html>\n')
    OUT.write_text(doc, encoding='utf-8')
    print('写入', OUT)


if __name__ == '__main__':
    main()
