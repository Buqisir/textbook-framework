#!/usr/bin/env python3
"""段考专题讲义 · 排版：读定稿 JSON，生成段考讲义 HTML（结构照抄 渲染/本地化/段考-样.html）。

运行：python3 -I 本地化/脚本/段考排版.py <节点名>
  期中前月考 → 本地化/内容/段考-高一上-期中前月考.定稿.json → 渲染/本地化/段考-高一上-期中前月考.html
  期中       → 本地化/内容/段考-高一上-期中.定稿.json       → 渲染/本地化/段考-高一上-期中.html
  样         → 本地化/内容/段考-样.定稿.json                → 渲染/本地化/段考-样-回放.html（手样回放，验 schema）

只用 段考.css（继承 同步.css）已有的 class；不写内联样式。

=== 定稿 JSON schema ===

行内文本（explain 段、例题句意、解析、练一练说明等）先转义，再做三个替换：
  **词**     → <b>词</b>
  [[词]]     → <span class="em-atom">词</span>
  [_词_]     → <u>词</u>（强调划线类题的划线部分）
  练一练 drill 项可带 long: true（或答案 ≥6 词时自动）→ <b class="ans long">，答案单独占一行
  ___        → <span class="blank"></span>（空位）
题干（stem.text / drill.stem）额外规则：题干里的换行（改写题原句与待填句之间）→ " → "；
  英文为主的题干 → <p lang="en">，中文为主（翻译题）→ <p>；cue 放 <span class="cue">（…）</span>；
  例题出处 stem.src 放题干段末 <span class="src">；练习出处 drill.src 放 </p> 后的 <span class="src">。
gloss / note 的 lines：每个元素一行，行间 <br>。

{
  "data_no": "01",                                  册头编号（期中前月考 "01"、期中 "02"）
  "unit_book": "段考专题　高一上",          册头 kicker
  "h2": "期中前月考",                                 册头标题
  "stats": [                                        册头三项：{pre?, b, post?}，pre/post 为普通文字
    {"b": "12", "post": "套试卷"},
    {"b": "6", "post": "个专题"},
    {"pre": "教学进度 ", "b": "U2"}
  ],
  "overview": {                                     「考情总览」（专题总表）
    "title": "考情总览",
    "chip": "2022–2025 · 东莞真题",
    "lead": "每格代表 10% 的试卷；教材进度加粗，表示考查早于教学。",
    "rows": [                                       行顺序 = 总表行顺序（讲的在前，不讲的在后）
      {"name": "非谓语", "cov": 1.0, "n": 55,      cov 覆盖率 0–1；格数 = round(cov×10)；n 题数
       "book": "必修二 U4 起", "ahead": true,       book 教材文字；ahead 为真则加粗（考在教之前）
       "go": "专题 1", "skip": false}                go 本册去向；skip 为真则整行 tr.skip（不讲）
    ],
    "after": "时态、被动语态每卷都考……"              表后一句 .after
  },
  "topics": [                                       讲的专题，按编号顺序
    {
      "no": 4,                                      编号（与 data-no 一致，从 1 起）
      "name": "虚拟语气",
      "vols": 12, "cov": 8, "n": 10,                专题头 chip：「覆盖 8/12 卷 · 10 道」
      "explain": [                                  讲解块，按顺序输出
        {"type": "subhead", "text": "recommend 型"},           <p class="subhead">
        {"type": "gloss", "lines": ["10 题里 9 题", "recommend：必修一 U1"]},   <aside class="gloss">（柱注，≤2 行）
        {"type": "p", "text": "……"},                             <p>
        {"type": "pattern", "text": "recommend that sb. (should) do"},  <p class="pattern" lang="en">
        {"type": "note", "lines": ["主语是物", "→ (should) be done"]}     <div class="note">
      ],
      "examples": [                                 例题，按顺序
        {
          "gloss": ["主语从句", "→ (should) do"],   例题柱注（.stem 内 aside.gloss），≤2 行
          "stem": {"text": "It is … that the government ___ (take) measures …",
                   "cue": [],                       cue：括号内改写指令，列表
                   "src": "2023 · 东莞外国语 · 高一上月考"},
          "ju": "强烈建议政府采取措施保护环境。",     句意
          "mid": {"label": "成分", "text": "……"},  label 只能是「成分」或「判断」
          "ans": "(should) take"                   故填；≥6 词自动用 ans-line 版式（整句答案）
        }
      ],
      "keypoint": "见 recommend that……",           要点（aside.keypoint > p）；可为空串
      "drill": [                                    练一练，全册题号连续，由排版分配 data-no
        {"stem": "……", "cue": ["用宾语从句改写"], "src": "2024 · 东莞市 · 高一上联考",
         "ans": "……", "why": "……"}                 ans 答案；why 简短说明（可空）
      ]
    }
  ]
}

练一练答案区按讲的专题分组：每组是 <h4>专题 n　名称</h4>（直接挂在 section 下）+ 独立的 <ol class="key">，<li data-no="…"><b class="ans">答案</b>说明</li>。
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / '本地化' / '内容'
RENDER = ROOT / '渲染' / '本地化'

NODE_FILES = {
    '期中前月考': ('段考-高一上-期中前月考.定稿.json', '段考-高一上-期中前月考.html'),
    '期中': ('段考-高一上-期中.定稿.json', '段考-高一上-期中.html'),
    '样': ('段考-样.定稿.json', '段考-样-回放.html'),
}

BLANK_RE = re.compile(r'_{2,}')
CJK_RE = re.compile(r'[一-鿿]')
ASCII_RE = re.compile(r'[A-Za-z]')
BOLD_RE = re.compile(r'\*\*(.+?)\*\*')
ATOM_RE = re.compile(r'\[\[(.+?)\]\]')
UL_RE = re.compile(r'\[_(.+?)_\]')   # [_划线部分_] → <u>（强调划线类题：题库无划线，按答案标出）


def esc(s):
    return html.escape(s or '', quote=False)


def inline(s):
    """行内文本：转义 → 空位 → **粗体** → [[em-atom]]。"""
    t = BLANK_RE.sub('\x00BLANK\x00', esc(s))
    t = BOLD_RE.sub(r'<b>\1</b>', t)
    t = ATOM_RE.sub(r'<span class="em-atom">\1</span>', t)
    t = UL_RE.sub(r'<u>\1</u>', t)
    return t.replace('\x00BLANK\x00', '<span class="blank"></span>')


def lines_html(lines):
    return '<br>'.join(inline(x) for x in lines)


def is_en(s):
    return len(ASCII_RE.findall(s)) > len(CJK_RE.findall(s))


def cue_html(cues):
    return ''.join(f' <span class="cue">（{esc(c)}）</span>' for c in cues or [])


def stem_p(stem_obj, src_inline=True):
    """题干段。src_inline=True：出处放 </p> 前（例题）；False：练习出处由调用方放 </p> 后。"""
    text = (stem_obj.get('text') or '').replace('\n', ' → ')
    body = inline(text) + cue_html(stem_obj.get('cue'))
    if src_inline and stem_obj.get('src'):
        body += f' <span class="src">{esc(stem_obj["src"])}</span>'
    if is_en(text):
        return f'<p lang="en">{body}</p>'
    return f'<p>{body}</p>'


def stat_html(s):
    return (esc(s.get('pre')) + f'<b>{esc(s["b"])}</b>' + esc(s.get('post')))


def header_html(d):
    stats = ''.join(f'<li>{stat_html(s)}</li>' for s in d['stats'])
    return (
        f'<section class="unit stage" data-unit="高一上 · {esc(d["h2"])}">\n'
        f'<header class="unit-head stage-head" data-no="{esc(d["data_no"])}">\n'
        f'  <p class="unit-book">{esc(d["unit_book"])}</p>\n'
        f'  <h2>{esc(d["h2"])}</h2>\n'
        f'  <ul class="unit-stats">{stats}</ul>\n'
        '</header>\n\n')


def cov_cell(cov):
    on = int(cov * 10 + 0.5)
    cells = ''.join('<i class="on"></i>' if k < on else '<i></i>' for k in range(10))
    return f'<td class="cov">{cells}<span>{int(cov * 100 + 0.5)}%</span></td>'


def overview_html(o):
    rows = []
    for r in o['rows']:
        book = inline(r['book'])
        if r.get('ahead'):
            book = f'<span class="ahead">{book}</span>'
        cls = ' class="skip"' if r.get('skip') else ''
        rows.append(
            f'      <tr{cls}><td class="name">{inline(r["name"])}</td>{cov_cell(r["cov"])}'
            f'<td class="n">{r["n"]}</td><td class="book">{book}</td>'
            f'<td class="go">{inline(r["go"])}</td></tr>')
    return (
        '<section class="part overview">\n'
        f'  <header class="topic-head"><h3>{esc(o["title"])}</h3><span class="chip chip-freq">{esc(o["chip"])}</span></header>\n'
        f'  <p class="lead">{inline(o["lead"])}</p>\n'
        '  <table class="focus">\n'
        '    <colgroup><col class="c-name"><col class="c-cov"><col class="c-n"><col><col class="c-go"></colgroup>\n'
        '    <thead><tr><th>专题</th><th>覆盖率</th><th>题数</th><th>教材进度</th><th>本册</th></tr></thead>\n'
        '    <tbody>\n' + '\n'.join(rows) + '\n    </tbody>\n'
        '  </table>\n'
        f'  <p class="after">{inline(o["after"])}</p>\n'
        '</section>\n\n')


def explain_html(blocks):
    out = []
    for b in blocks:
        t = b['type']
        if t == 'subhead':
            out.append(f'      <p class="subhead">{inline(b["text"])}</p>')
        elif t == 'gloss':
            out.append(f'      <aside class="gloss">{lines_html(b["lines"])}</aside>')
        elif t == 'p':
            out.append(f'      <p>{inline(b["text"])}</p>')
        elif t == 'pattern':
            out.append(f'      <p class="pattern" lang="en">{inline(b["text"])}</p>')
        elif t == 'note':
            out.append(f'      <div class="note">{lines_html(b["lines"])}</div>')
        else:
            raise SystemExit(f'explain 未知块类型：{t}')
    return '\n'.join(out)


def answer_p(ans):
    if len(ans.split()) >= 6:
        return f'      <p class="ans-line"><b>故填</b><b class="ans">{inline(ans)}</b></p>'
    return f'      <p><b>故填</b> <b class="ans">{inline(ans)}</b>。</p>'


def example_html(e):
    mid = e['mid']
    label = mid.get('label', '成分')
    return (
        '  <article class="example">\n'
        '    <div class="stem">\n'
        f'      <aside class="gloss">{lines_html(e["gloss"])}</aside>\n'
        f'      {stem_p(e["stem"], src_inline=True)}\n'
        '    </div>\n'
        '    <div class="solution">\n'
        '      <h4>解析</h4>\n'
        f'      <p><b>句意</b>：{inline(e["ju"])}</p>\n'
        f'      <p><b>{esc(label)}</b>：{inline(mid["text"])}</p>\n'
        + answer_p(e['ans']) + '\n'
        '    </div>\n'
        '  </article>\n')


def topic_html(t, drill_nos):
    no = t['no']
    chip = (f'覆盖 <b>{t["cov"]}</b>/{t["vols"]} 卷 · <b>{t["n"]}</b> 道')
    parts = [
        f'<section class="topic" data-no="{no}">\n',
        f'  <header class="topic-head" data-no="{no}"><h3>{esc(t["name"])}</h3>'
        f'<span class="chip chip-freq">{chip}</span></header>\n',
        '  <div class="explain">\n' + explain_html(t['explain']) + '\n  </div>\n',
    ]
    parts += [example_html(e) for e in t['examples']]
    if t.get('keypoint'):
        parts.append(f'  <aside class="keypoint">\n    <p>{inline(t["keypoint"])}</p>\n  </aside>\n')
    if t.get('drill'):
        items = []
        for d, n in zip(t['drill'], drill_nos):
            stem = {'text': d['stem'], 'cue': d.get('cue')}
            items.append(f'      <li data-no="{n}">{stem_p(stem, src_inline=False)}'
                         f'<span class="src">{esc(d.get("src"))}</span></li>')
        parts.append('  <div class="drill">\n    <h4>练一练</h4>\n    <ol class="atoms">\n'
                     + '\n'.join(items) + '\n    </ol>\n  </div>\n')
    parts.append('</section>\n\n')
    return ''.join(parts)


def answers_html(topics, drill_nos_by_topic):
    groups = []
    for t in topics:
        if not t.get('drill'):
            continue
        lis = []
        for d, n in zip(t['drill'], drill_nos_by_topic[t['no']]):
            why = inline(d.get('why') or '')
            long = d.get('long') or len(d['ans'].split()) >= 6   # 整句答案单独占一行
            cls = 'ans long' if long else 'ans'
            lis.append(f'    <li data-no="{n}"><b class="{cls}">{inline(d["ans"])}</b>{why}</li>')
        groups.append(f'  <h4>专题 {t["no"]}　{esc(t["name"])}</h4>\n'
                      '  <ol class="key">\n' + '\n'.join(lis) + '\n  </ol>')
    return (
        '<section class="part answers">\n'
        '  <header class="topic-head" data-no="答"><h3>练一练答案</h3></header>\n'
        + '\n'.join(groups) + '\n'
        '</section>\n')


def validate(D):
    errs = []
    if len(D['stats']) != 3:
        errs.append('册头 stats 必须 3 项')
    names = set()
    for r in D['overview']['rows']:
        if not (0 <= r['cov'] <= 1):
            errs.append(f'总表 {r["name"]} 覆盖率不在 0–1')
        if r['name'] in names:
            errs.append(f'总表重复专题 {r["name"]}')
        names.add(r['name'])
    last = 0
    for t in D['topics']:
        if t['no'] <= last:
            errs.append(f'专题编号应严格递增，{t["name"]} 写成 {t["no"]}')
        last = t['no']
        if t['name'] not in names:
            errs.append(f'专题 {t["name"]} 不在总表中')
        if t['cov'] > t['vols']:
            errs.append(f'专题 {t["name"]} 覆盖卷数超过总卷数')
        for b in t['explain']:
            if b['type'] in ('gloss', 'note') and len(b['lines']) > 2:
                errs.append(f'专题 {t["name"]} 柱注/note 超过 2 行')
            if b['type'] == 'gloss' and any(len(CJK_RE.findall(x)) > 10 for x in b['lines']):
                errs.append(f'专题 {t["name"]} 柱注单行超过 10 字')
        for e in t['examples']:
            if e['mid'].get('label', '成分') not in ('成分', '判断'):
                errs.append(f'例题 {e["stem"]["text"][:20]} 的 mid.label 只能是 成分/判断')
            if not e.get('ans'):
                errs.append(f'例题 {e["stem"]["text"][:20]} 缺故填')
            if len(e['gloss']) > 2:
                errs.append(f'例题柱注超过 2 行：{e["gloss"]}')
        for d in t.get('drill', []):
            if not d.get('ans'):
                errs.append(f'练习缺答案：{d["stem"][:20]}')
    return errs


def build(D):
    # 练一练题号全册连续
    drill_nos_by_topic, n = {}, 0
    for t in D['topics']:
        ids = []
        for _ in t.get('drill', []):
            n += 1
            ids.append(n)
        drill_nos_by_topic[t['no']] = ids
    body = (header_html(D) + overview_html(D['overview'])
            + ''.join(topic_html(t, drill_nos_by_topic[t['no']]) for t in D['topics'])
            + answers_html(D['topics'], drill_nos_by_topic)
            + '</section>\n')
    title = f'段考专题讲义 · 高一上 · {D["h2"]}'
    return ('<!DOCTYPE html>\n<html lang="zh-Hans">\n<head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(title)}</title>'
            '<link rel="stylesheet" href="段考.css"></head>\n<body>\n'
            + body + '</body>\n</html>\n')


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in NODE_FILES:
        raise SystemExit(f'用法：段考排版.py <{"|".join(NODE_FILES)}>')
    src_name, out_name = NODE_FILES[sys.argv[1]]
    src = CONTENT / src_name
    D = json.loads(src.read_text(encoding='utf-8'))
    errs = validate(D)
    if errs:
        for e in errs:
            print('错误', e, file=sys.stderr)
        raise SystemExit(1)
    doc = build(D)
    assert 'style=' not in doc, '出现内联样式'
    out = RENDER / out_name
    out.write_text(doc, encoding='utf-8')
    print('写入', out)


if __name__ == '__main__':
    main()
