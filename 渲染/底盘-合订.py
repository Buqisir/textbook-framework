#!/usr/bin/env python3
"""把整本《基础薄弱学生英语底盘展示册》的 docx 分页稿收成澄页 schema HTML。

数据流：03-DOCX分页稿/*.docx → 语义块 → 澄页 HTML（只使用 schema 内的 class）。
词缀段复用 底盘-词缀.py 的解析器（读取合订 docx 的词缀区间）。
"""

from __future__ import annotations

import html
import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent / "基础薄弱学生英语底盘展示册"
PAGES_DIR = PROJ / "03-DOCX分页稿"
COMPILED = PROJ / "04-DOCX成稿" / "基础薄弱学生英语底盘展示册-合订试排-v0.1.docx"
OUT = HERE / "底盘-合订.html"
PAGES_JSON = HERE / "底盘-合订-pages.json"

# ---------- 复用词缀解析器 ----------

spec = importlib.util.spec_from_file_location("affix", HERE / "底盘-词缀.py")
affix = importlib.util.module_from_spec(spec)
sys.modules["affix"] = affix
spec.loader.exec_module(affix)
affix.SRC = COMPILED  # 指向当前项目内的合订 docx
# 合订 docx 的样式 ID 是具名样式（Heading1/Heading3），旧表是数字 ID，两者都认
affix.STYLE.update({"Heading1": "h1", "Heading2": "h2", "Heading3": "h3"})

CJK = re.compile(r"[一-鿿]")


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def is_cjk(text: str) -> bool:
    return bool(CJK.search(text))


@dataclass
class Topic:
    no: str
    title: str
    blocks: list = field(default_factory=list)


@dataclass
class Section:
    no: str          # toc-group 编号
    title: str       # toc 条目名 / 组头名
    topics: list = field(default_factory=list)


# ---------- docx 基础工具 ----------

def iter_body(doc: Document):
    """按文档顺序产出 ("p", Paragraph) / ("tbl", Table)。"""
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield "p", Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield "tbl", Table(child, doc)


def para_runs(p: Paragraph) -> list[tuple[str, bool]]:
    """按 run 返回 (text, bold)，w:br / w:tab 转成 \n / \t。"""
    out: list[tuple[str, bool]] = []
    for r in p.runs:
        bold = bool(r.bold)
        buf = ""
        for node in r._r.iter():
            if node.tag == qn("w:t") and node.text:
                buf += node.text
            elif node.tag == qn("w:tab"):
                buf += "\t"
            elif node.tag == qn("w:br"):
                buf += "\n"
        if buf:
            out.append((buf, bold))
    return out


def para_lines(p: Paragraph) -> list[str]:
    text = "".join(t for t, _ in para_runs(p)).replace(" ", " ")
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def cell_lines(cell) -> list[str]:
    lines: list[str] = []
    for p in cell.paragraphs:
        lines.extend(para_lines(p))
    return lines


def para_text(p: Paragraph) -> str:
    return " ".join(para_lines(p))


def bold_clause(p: Paragraph) -> tuple[str, str]:
    """从 'label\\tsentence' 段落拆出 (label, sentence)；返回 sentence 内加粗片段。"""
    runs = para_runs(p)
    text = "".join(t for t, _ in runs)
    bold = "".join(t for t, b in runs if b)
    if "\t" in text:
        label, sentence = text.split("\t", 1)
    else:
        label, sentence = "", text
    # bold 部分里去掉 label 本身
    clause = bold.replace(label, "", 1).strip() if label else bold.strip()
    return label.strip(), sentence.strip(), clause


def en_zh_pairs(lines: list[str]) -> list[tuple[str, str | None]]:
    """把一串行按 英/中 交替配对；孤行返回 (line, None)。"""
    out: list[tuple[str, str | None]] = []
    held: str | None = None
    for ln in lines:
        if is_cjk(ln):
            if held is not None:
                out.append((held, ln))
                held = None
            else:
                out.append((ln, None))
        else:
            if held is not None:
                out.append((held, None))
            held = ln
    if held is not None:
        out.append((held, None))
    return out


def add_pairs(blocks: list, lines: list[str]) -> None:
    for en, zh in en_zh_pairs(lines):
        if zh is None:
            blocks.append(("zh" if is_cjk(en) else "en", en))
        else:
            blocks.append(("pair", en, zh))


def split_gloss(text: str) -> str:
    """'English gloss 中文释义' → 给英文部分加 lang。返回 HTML 片段。"""
    m = CJK.search(text)
    if not m:
        return f'<span lang="en">{esc(text)}</span>'
    en, zh = text[: m.start()].strip(), text[m.start():].strip()
    if not en:
        return esc(zh)
    return f'<span lang="en">{esc(en)}</span> {esc(zh)}'


# ---------- HTML 产出 ----------

def phrases_html(words: list[str], indent: str) -> str:
    spans = "\n".join(f'{indent}  <span lang="en">{esc(w)}</span>' for w in words)
    return f"{indent}<p class=\"phrases\">\n{spans}\n{indent}</p>"


def _td(text: str, cls: str = "", rs: int = 1, cs: int = 1) -> str:
    lang = ' lang="en"' if text and not is_cjk(text) else ""
    a = f' class="{cls}"' if cls else ""
    r = f' rowspan="{rs}"' if rs > 1 else ""
    c = f' colspan="{cs}"' if cs > 1 else ""
    return f"<td{c}{r}{a}{lang}>{esc(text)}</td>"


def _th(text: str, cs: int = 1, cls: str = "") -> str:
    lang = ' lang="en"' if text and not is_cjk(text) else ""
    c = f' colspan="{cs}"' if cs > 1 else ""
    a = f' class="{cls}"' if cls else ""
    return f"<th{c}{a}{lang}>{esc(text)}</th>"


def _sheet(head_rows: list[str], body_rows: list[str]) -> str:
    head = "".join(f"<tr>{h}</tr>" for h in head_rows)
    body = "".join(f"<tr>{r}</tr>" for r in body_rows)
    return f'<table class="sheet"><thead>{head}</thead><tbody>{body}</tbody></table>'


def bold_mark(text: str, clauses: list[str]) -> str:
    """把 sentence 中列出的片段加 <b>（只标第一次出现，最多 4 处）。"""
    out = esc(text)
    used = 0
    for clause in clauses:
        clause = clause.strip().rstrip(".")
        if not clause or used >= 4:
            continue
        idx = out.find(esc(clause))
        if idx == -1:
            # 容忍大小写/空格差异
            m = re.search(re.escape(esc(clause)).replace(r"\ ", r"\s+"), out)
            if not m:
                continue
            idx, end = m.start(), m.end()
        else:
            end = idx + len(esc(clause))
        out = out[:idx] + "<b>" + out[idx:end] + "</b>" + out[end:]
        used += 1
    return out


def topic_html(topic: Topic) -> str:
    parts = [
        f'    <section class="topic" data-no="{esc(topic.no)}">',
        f'      <header class="topic-head" data-no="{esc(topic.no)}">',
        f"        <h3>{esc(topic.title)}</h3>",
        "      </header>",
        '      <div class="explain">',
    ]
    for block in topic.blocks:
        kind = block[0]
        if kind == "subhead":
            parts.append(f'        <p class="subhead">{esc(block[1])}</p>')
        elif kind == "case":
            parts.append(f'        <p class="case">{esc(block[1])}</p>')
        elif kind == "words":
            parts.append(phrases_html(block[1], "        "))
        elif kind == "item":
            term, gloss = block[1], block[2]
            lang = ' lang="en"' if not is_cjk(term) else ""
            if gloss:
                parts.append(f'        <p class="item"><b{lang}>{esc(term)}</b>　{split_gloss(gloss) if not is_cjk(gloss) else esc(gloss)}</p>')
            else:
                parts.append(f'        <p class="item"><b{lang}>{esc(term)}</b></p>')
        elif kind == "itemraw":  # term 已是 HTML（双语混合）
            parts.append(f'        <p class="item"><b>{block[1]}</b>　{split_gloss(block[2])}</p>')
        elif kind == "note":
            parts.append(f'        <aside class="note"><p>{esc(block[1])}</p></aside>')
        elif kind == "table":
            parts.append("        " + block[1])
        elif kind == "pair":
            parts.append(f'        <p lang="en">{esc(block[1])}</p>')
            parts.append(f"        <p>{esc(block[2])}</p>")
        elif kind == "enbold":
            parts.append(f'        <p lang="en">{bold_mark(block[1], block[2])}</p>')
        elif kind == "en":
            parts.append(f'        <p lang="en">{esc(block[1])}</p>')
        elif kind == "zh":
            parts.append(f"        <p>{esc(block[1])}</p>")
        elif kind == "gloss":  # 英释 + 中释 混合行
            parts.append(f"        <p>{split_gloss(block[1])}</p>")
    parts.append("      </div>")
    parts.append("    </section>")
    return "\n".join(parts)


def section_html(sec: Section) -> str:
    bits = [
        '    <div class="toc-group">',
        f'      <h3 data-no="{esc(sec.no)}">{esc(sec.title)}</h3>',
        "    </div>",
    ]
    bits.extend(topic_html(t) for t in sec.topics)
    return "\n".join(bits)


# ---------- 各板块解析 ----------

def parse_affix_sections() -> list[Section]:
    doc = Document(str(COMPILED))
    groups = affix.parse(affix.load_items(doc))
    sections: list[Section] = []
    for g in groups:
        topics = []
        for t in g.topics:
            title = f"{t.affix}　{t.gloss}" if t.gloss and "/" not in t.affix else t.affix
            topics.append(Topic(no=t.no, title=title, blocks=t.blocks))
        sections.append(Section(no=g.code, title=g.title, topics=topics))
    return sections


PREP_FILES = [
    "01-高频介词in页-v0.6.docx", "02-高频介词on页-v0.2.docx",
    "03-高频介词at页-v0.2.docx", "04-高频介词to页-v0.4.docx",
    "05-高频介词from页-v0.2.docx", "06-高频介词for页-v0.5.docx",
    "07-高频介词with页-v0.2.docx", "08-高频介词by页-v0.3.docx",
    "09-高频介词of页-v0.2.docx", "10-高频介词as页-v0.2.docx",
]


def parse_prepositions() -> list[Section]:
    files = [PAGES_DIR / "介词页" / f for f in PREP_FILES]
    sections: list[Section] = []
    for idx, f in enumerate(files):
        m = re.search(r"介词(\w+)页", f.name)
        prep = m.group(1) if m else f.stem
        doc = Document(str(f))
        blocks: list = []
        count_line = ""
        for p in doc.paragraphs:
            style = p.style.name
            text = para_text(p)
            if not text:
                continue
            if text.startswith("PREPOSITION FIELD GUIDE"):
                continue
            if text.startswith("高频介词"):
                continue
            if "单项用法" in text and len(text) < 20:
                count_line = text
                continue
            if style == "Heading 2":
                blocks.append(("subhead", text))
                continue
            lines = para_lines(p)
            first = lines[0]
            if blocks and blocks[-1][0] == "subhead" and ("表示" in first or "指" in first or "某人" in first or "某物" in first or "某事" in first or "用来" in first or "因为" in first):
                # 义项定义行：英文 gloss + 中文说明
                blocks.append(("gloss", first))
                lines = lines[1:]
            add_pairs(blocks, lines)
        title = f"{prep}　{count_line}" if count_line else prep
        no = f"{24 + idx}"
        sections.append(Section(no=no, title=f"高频介词 {prep}", topics=[Topic(no=no, title=title, blocks=blocks)]))
    return sections


def parse_phonics() -> Section:
    doc = Document(str(PAGES_DIR / "音标拼读重音页" / "01-音标拼读重音基础表-v0.7.docx"))
    topics: list[Topic] = []
    topic: Topic | None = None
    page_no = 0
    pending_title = pending_sub = ""

    def flush():
        nonlocal topic
        if topic is not None:
            topics.append(topic)
        topic = None

    for kind, el in iter_body(doc):
        if kind == "p":
            text = para_text(el)
            if not text:
                continue
            m = re.match(r"PRONUNCIATION GUIDE\s+(\d+)", text)
            if m:
                flush()
                page_no = int(m.group(1))
                pending_title = pending_sub = ""
                state = "title"
                continue
            if topic is None:
                if not pending_title:
                    pending_title = text
                elif not pending_sub:
                    pending_sub = text
                    topic = Topic(no=f"1.{page_no}", title=pending_title, blocks=[])
                    if pending_sub:
                        topic.blocks.append(("zh", pending_sub))
                continue
            # 页内小节字母行 / 说明行
            if re.match(r"^[A-D]\s\s", text):
                topic.blocks.append(("subhead", re.sub(r"\s+", " ", text)))
            else:
                topic.blocks.append(("note", text) if len(text) < 60 and ("。" in text or "，" in text) else ("zh", text))
            continue

        # ---- 表格（原表继承：sheet 件） ----
        t: Table = el
        hdr = [c.text.strip() for c in t.rows[0].cells]
        ncol = len(t.columns)
        if topic is None:
            continue
        if ncol == 6 and hdr[0] == "Consonants":
            rows = [[c.text.strip() for c in r.cells] for r in t.rows[2:]]
            span: dict[int, tuple[str, int]] = {}
            covered: set[int] = set()
            i = 0
            while i < len(rows):
                ty = rows[i][3]
                j = i + 1
                while ty and j < len(rows) and rows[j][3] == ty:
                    j += 1
                if ty:
                    span[i] = (ty, j - i)
                    covered.update(range(i + 1, j))
                i = j
            vtype = {"short": "short 短元音", "long": "long 长元音", "diphthongs": "diphthongs 双元音"}
            head = [
                _th("Consonants", cs=2) + _th("", cls="gap") + _th("Vowels", cs=3),
                _th("Symbol") + _th("Keyword") + _th("", cls="gap") + _th("Type") + _th("Symbol") + _th("Keyword"),
            ]
            body = []
            for ri, c in enumerate(rows):
                tds = _td(c[0], "sym") + _td(c[1]) + '<td class="gap"></td>'
                if ri in span:
                    tds += _td(vtype.get(span[ri][0], span[ri][0]), "tag", rs=span[ri][1])
                elif ri not in covered:
                    tds += "<td></td>"
                tds += _td(c[4], "sym") + _td(c[5])
                body.append(tds)
            topic.blocks.append(("table", _sheet(head, body)))
        elif ncol == 11:
            head = ["".join(_th(h) for h in hdr[:5]) + _th("", cls="gap") + "".join(_th(h) for h in hdr[6:])]
            body = []
            for r in t.rows[1:]:
                c = [x.text.strip() for x in r.cells]
                left = _td(c[0], "sym") + "".join(_td(x) for x in c[1:5])
                right = _td(c[6], "sym") + "".join(_td(x) for x in c[7:11])
                body.append(left + '<td class="gap"></td>' + right)
            topic.blocks.append(("table", _sheet(head, body)))
        elif ncol == 3 and hdr[0] == "Letters":
            head = ["".join(_th(h) for h in hdr)]
            body = [
                _td(r.cells[0].text.strip(), "sym")
                + "".join(_td(x.text.strip()) for x in r.cells[1:])
                for r in t.rows[1:]
            ]
            topic.blocks.append(("table", _sheet(head, body)))
        elif ncol == 6 and hdr[0] == "Letters":
            head = ["".join(_th(h) for h in hdr[:3]) + _th("", cls="gap") + "".join(_th(h) for h in hdr[3:])]
            body = []
            for r in t.rows[1:]:
                c = [x.text.strip() for x in r.cells]
                left = _td(c[0], "sym") + _td(c[1]) + _td(c[2])
                right = _td(c[3], "sym") + _td(c[4]) + _td(c[5])
                body.append(left + '<td class="gap"></td>' + right)
            topic.blocks.append(("table", _sheet(head, body)))
        elif ncol in (2, 3, 4):
            head = ["".join(_th(h) for h in hdr)]
            body = [
                _td(r.cells[0].text.strip(), "sym")
                + "".join(_td(x.text.strip()) for x in r.cells[1:])
                for r in t.rows[1:]
            ]
            topic.blocks.append(("table", _sheet(head, body)))
        else:
            # 兜底：逐行首格加粗
            for r in t.rows[1:]:
                c = [x.text.strip() for x in r.cells]
                if c[0]:
                    topic.blocks.append(("item", c[0], " — ".join(x for x in c[1:] if x)))
    flush()
    return Section(no="01", title="音标、拼读和重音基础表", topics=topics)


def parse_wordfamily() -> Section:
    doc = Document(str(PAGES_DIR / "词汇与音形义" / "05-词性转化规律总览-v0.3.docx"))
    topics: list[Topic] = []
    topic: Topic | None = None
    page_no = 0
    pend: list[str] = []
    for kind, el in iter_body(doc):
        if kind == "p":
            text = para_text(el)
            if not text:
                continue
            m = re.match(r"WORD FAMILY MAP\s+(\d+)", text)
            if m:
                if topic:
                    topics.append(topic)
                topic = None
                page_no = int(m.group(1))
                pend = []
                continue
            if topic is None:
                pend.append(text)
                if len(pend) == 2:
                    topic = Topic(no=f"21.{page_no}", title=pend[0], blocks=[("zh", pend[1])])
                continue
            topic.blocks.append(("zh", text))
            continue
        t: Table = el
        if topic is None:
            continue
        for r in t.rows[1:]:
            cells = [cell_lines(c) for c in r.cells]
            label = " · ".join(cells[0])  # R01 + 层级
            rule = "　".join(cells[1])
            examples = cells[2] if len(cells) > 2 else []
            topic.blocks.append(("item", label, rule))
            if examples:
                words: list[str] = []
                for ln in examples:
                    words.extend(p.strip() for p in ln.split("\t") if p.strip())
                topic.blocks.append(("words", words))
    if topic:
        topics.append(topic)
    return Section(no="21", title="词性转化规律总览", topics=topics)


INFLECTION_MD = (
    PROJ / "02-单页内容草稿" / "词汇与音形义" / "规则变形页"
    / "规则变形总表-设计草案-v0.1.md"
)


def md_clean(text: str) -> str:
    return re.sub(r"\*\*|~~", "", text)


def md_inline(text: str) -> str:
    """**bold** / ~~strike~~ → <b>/<s>，其余转义。"""
    out: list[str] = []
    pos = 0
    for m in re.finditer(r"\*\*(.+?)\*\*|~~(.+?)~~", text):
        out.append(esc(text[pos:m.start()]))
        out.append(f"<b>{esc(m.group(1))}</b>" if m.group(1) is not None else f"<s>{esc(m.group(2))}</s>")
        pos = m.end()
    out.append(esc(text[pos:]))
    return "".join(out)


def _td_md(text: str, cls: str = "") -> str:
    lang = ' lang="en"' if text and not is_cjk(text) else ""
    a = f' class="{cls}"' if cls else ""
    return f"<td{a}{lang}>{md_inline(text)}</td>"


def md_sheet(rows: list[list[str]]) -> str:
    head = ["".join(
        f'<th{" lang=\"en\"" if c and not is_cjk(c) else ""}>{md_inline(c)}</th>'
        for c in rows[0]
    )]
    body = ["".join(_td_md(c) for c in r) for r in rows[1:]]
    return _sheet(head, body)


def parse_inflection() -> Section:
    """规则变形总表：DOCX 分页稿未排前，直接读 Markdown 草案作内容源。"""
    raw_lines = INFLECTION_MD.read_text(encoding="utf-8").splitlines()

    topic_of = [
        ("全表地图", 0), ("一、动词", 0), ("二、过去式", 0), ("三、-ing", 0),
        ("四、名词", 1), ("五、比较级", 2), ("常见误区速查", 3), ("连接题型", 3),
    ]
    titles = [
        "动词：三单 / 过去式 / -ing",
        "名词：复数",
        "形容词：比较级 / 最高级",
        "常见误区速查",
    ]
    topics = [Topic(no=f"22.{i + 1}", title=t, blocks=[]) for i, t in enumerate(titles)]

    def emit_labeled(topic: Topic, term: str, gloss: str) -> None:
        term = "派生（母词→派生）" if term == "派生" else term
        if gloss and not is_cjk(gloss) and "," in gloss:
            words = [w.strip() for w in re.split(r"[,，、;；]", gloss) if w.strip()]
            topic.blocks.append(("item", term, ""))
            topic.blocks.append(("words", words))
        else:
            topic.blocks.append(("item", term, gloss))

    cur: int | None = None
    in_code = False
    code_buf: list[str] = []
    mantra: list[str] = []
    table_rows: list[list[str]] = []

    def flush_table() -> None:
        if table_rows:
            topics[cur].blocks.append(("table", md_sheet(table_rows)))
            table_rows.clear()

    for raw in raw_lines:
        s = raw.strip()
        if s.startswith("```"):
            if in_code:
                if cur is None and not mantra:
                    mantra = code_buf[:]
                elif cur is not None:
                    for cl in code_buf:
                        topics[cur].blocks.append(("zh", cl))
                code_buf = []
            in_code = not in_code
            continue
        if in_code:
            code_buf.append(s)
            continue
        if s.startswith("## "):
            flush_table()
            title = s[3:].strip()
            cur = None
            for key, ti in topic_of:
                if title.startswith(key):
                    cur = ti
                    break
            if cur is not None and not title.startswith(("全表地图", "常见误区", "连接题型")):
                topics[cur].blocks.append(("subhead", title))
            continue
        if cur is None:
            continue
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            table_rows.append(cells)
            continue
        flush_table()
        if not s or s == "---":
            continue
        if s.startswith(">"):
            txt = md_clean(s.lstrip(">").strip())
            if txt:
                topics[cur].blocks.append(("note", txt))
            continue
        if s.startswith("### "):
            topics[cur].blocks.append(("case", md_clean(s[4:].strip())))
            continue
        if s.startswith("- "):
            body = md_clean(s[2:].strip())
            m = re.match(r"^(.{2,30}?)：(.*)$", body)
            if m:
                emit_labeled(topics[cur], m.group(1), m.group(2).strip())
            else:
                topics[cur].blocks.append(("zh", f"· {body}"))
            continue
        m = re.match(r"^\*\*(.+?)\*\*[:：]?\s*(.*)$", s)
        if m:
            emit_labeled(topics[cur], md_clean(m.group(1)), md_clean(m.group(2)))
            continue
        m = re.match(r"^(.{2,24}?)：(.*)$", s)
        if m and "。" not in m.group(1):
            emit_labeled(topics[cur], md_clean(m.group(1)), md_clean(m.group(2)))
            continue
        if "," in s and not is_cjk(s):
            words = [w.strip() for w in re.split(r"[,，、;；]", s) if w.strip()]
            topics[cur].blocks.append(("words", words))
            continue
        topics[cur].blocks.append(("zh", md_clean(s)))

    intro = [
        ("zh", "变尾巴之前，先看词尾——五种变形共用同一套词尾判断。"),
        ("note", "本页只讲规则变形：went、better、children 这类不规则形式去不规则动词三态表。词表以英式拼写为准。"),
    ] + [("zh", ln) for ln in mantra]
    topics[0].blocks = intro + topics[0].blocks
    return Section(no="22", title="规则变形总表", topics=topics)


def parse_irregular() -> Section:
    doc = Document(str(PAGES_DIR / "不规则动词三态表" / "01-不规则动词三态表-v1.0.docx"))
    topics: list[Topic] = []
    topic: Topic | None = None
    page_no = 0
    pend: list[str] = []
    for kind, el in iter_body(doc):
        if kind == "p":
            text = para_text(el)
            if not text:
                continue
            m = re.match(r"IRREGULAR VERBS\s+(\d+)", text)
            if m:
                if topic:
                    topics.append(topic)
                topic = None
                page_no = int(m.group(1))
                pend = []
                continue
            if topic is None:
                pend.append(text)
                if len(pend) == 2:
                    topic = Topic(no=f"23.{page_no}", title=pend[0], blocks=[("zh", pend[1])])
                continue
            if re.match(r"^[A-C]\s\s", text):
                topic.blocks.append(("subhead", re.sub(r"\s+", " ", text)))
            else:
                topic.blocks.append(("note", text) if "。" in text else ("zh", text))
            continue
        t: Table = el
        if topic is None:
            continue
        ncol = len(t.columns)
        hdr = [c.text.strip() for c in t.rows[0].cells]
        if ncol == 9:
            for off in (0, 5):
                gname = hdr[off].strip()
                if gname:
                    topic.blocks.append(("subhead", gname))
                words = []
                seen: set[str] = set()
                for r in t.rows[2:]:
                    c = [x.text.strip() for x in r.cells]
                    if not c[off] or c[off] in seen:
                        continue
                    seen.add(c[off])
                    if "\n" in c[off]:
                        # 跨行合并的侧栏串读块：首行作小标题，其余作条目
                        box = [ln.strip() for ln in c[off].splitlines() if ln.strip()]
                        topic.blocks.append(("subhead", box[0]))
                        topic.blocks.append(("words", box[1:]))
                        continue
                    words.append(f"{c[off]} – {c[off+1]} – {c[off+2]}　{c[off+3]}")
                if words:
                    topic.blocks.append(("words", words))
        elif ncol == 4 and hdr[0] == "Pattern":
            seen4: set[tuple] = set()
            for r in t.rows[1:]:
                c = [x.text.strip() for x in r.cells]
                key = tuple(c)
                if not c[0] or key in seen4:
                    continue
                seen4.add(key)
                topic.blocks.append(("item", c[0], f"{c[1]}｜{c[2]}｜{c[3]}"))
        elif ncol == 3:
            seen3: set[tuple] = set()
            for r in t.rows[1:]:
                c = [x.text.strip() for x in r.cells]
                key = tuple(c)
                if c[0] and key not in seen3:
                    seen3.add(key)
                    topic.blocks.append(("item", c[0], f"{c[1]}｜{c[2]}"))
        elif ncol == 5 and hdr[0] == "Base":
            seen5: set[tuple] = set()
            for r in t.rows[1:]:
                c = [x.text.strip() for x in r.cells]
                key = tuple(c)
                if c[0] and key not in seen5:
                    seen5.add(key)
                    topic.blocks.append(("item", c[0], f"{c[1]} – {c[2]} – {c[3]}　{c[4]}"))
        elif ncol == 5 and hdr[0] == "Verb":
            seen5v: set[tuple] = set()
            for r in t.rows[1:]:
                c = [x.text.strip() for x in r.cells]
                key = tuple(c)
                if c[0] and key not in seen5v:
                    seen5v.add(key)
                    tail = f"｜{c[4]}" if len(c) > 4 and c[4] else ""
                    topic.blocks.append(("item", c[0], f"{c[1]} – {c[2]}　{c[3]}{tail}"))
    if topic:
        topics.append(topic)
    return Section(no="23", title="不规则动词三态表", topics=topics)


def parse_sentence_components() -> Section:
    doc = Document(str(PAGES_DIR / "句法语法底盘" / "03-句子成分和形式速查表-v0.4.docx"))
    topic = Topic(no="1", title="句子成分和形式速查表", blocks=[])
    tables = [el for k, el in iter_body(doc) if k == "tbl"]
    # T0：成分速查
    t0 = tables[0]
    topic.blocks.append(("subhead", "成分速查"))
    for r in t0.rows[1:]:
        c = [cell_lines(x) for x in r.cells]
        sym, name, func = c[0][0], c[1][0], c[2][0] if c[2] else ""
        demo = " ".join(c[3])
        comp = " ".join(c[4])
        topic.blocks.append(("item", f"{sym} · {name}", func))
        if demo:
            topic.blocks.append(("pair", demo, f"标出的成分 → {comp}" if comp else ""))
    # T1：形式 → 成分
    t1 = tables[1]
    topic.blocks.append(("subhead", "成分可以由什么形式充当"))
    for r in t1.rows[1:]:
        c = [cell_lines(x) for x in r.cells]
        topic.blocks.append(("item", c[0][0], c[1][0] if c[1] else ""))
        for ln in c[2]:
            topic.blocks.append(("en" if not is_cjk(ln) else "zh", ln))
    return Section(no="01", title="句子成分和形式速查表", topics=[topic])


def parse_basic_patterns() -> Section:
    doc = Document(str(PAGES_DIR / "句法语法底盘" / "02-基本句型表-v0.1.docx"))
    topic = Topic(no="2", title="基本句型表", blocks=[])
    for p in doc.paragraphs:
        text = para_text(p)
        if not text or text.startswith("SYNTAX MAP") or text == "基本句型表":
            continue
        if text.startswith("SV /"):
            topic.blocks.append(("zh", text))
            continue
        if re.match(r"^\d{2}\s\s", text):
            topic.blocks.append(("subhead", re.sub(r"\s+", " ", text)))
            continue
        lines = para_lines(p)
        for ln in lines:
            if re.match(r"^[SVOCAP][:/]", ln) or re.match(r"^S:\s", ln):
                topic.blocks.append(("zh", f"成分　{ln}"))
            elif is_cjk(ln):
                topic.blocks.append(("zh", ln))
            else:
                topic.blocks.append(("en", ln))
    return Section(no="02", title="基本句型表", topics=[topic])


def parse_linking_verbs() -> Section:
    doc = Document(str(PAGES_DIR / "句法语法底盘" / "01-系动词补充表-v0.3.docx"))
    topic = Topic(no="3", title="系动词补充表", blocks=[])
    for p in doc.paragraphs:
        text = para_text(p)
        if not text or text.startswith("SYNTAX MAP") or text == "系动词补充表":
            continue
        if re.match(r"^\d{2}\s\s", text):
            topic.blocks.append(("subhead", re.sub(r"\s+", " ", text)))
            continue
        if re.match(r"^(be|look|seem|remain|keep|stay|become|get|grow|turn|go|come|prove|appear|feel|smell|sound|taste)[,\s]", text) and not is_cjk(text):
            verbs = [v.strip() for v in re.split(r"[,，]", text) if v.strip()]
            topic.blocks.append(("words", verbs))
            continue
        lines = para_lines(p)
        if len(lines) >= 2 and not is_cjk(lines[0]) and is_cjk(lines[1]):
            topic.blocks.append(("enbold", lines[0], [lines[0].split()[0]]))
            for extra in lines[1:]:
                topic.blocks.append(("zh", extra) if is_cjk(extra) else ("en", extra))
        else:
            for ln in lines:
                topic.blocks.append(("zh" if is_cjk(ln) else "en", ln))
    return Section(no="03", title="系动词补充表", topics=[topic])


def parse_parallel() -> Section:
    doc = Document(str(PAGES_DIR / "句法语法底盘" / "06-常见并列结构和平行成分表-v0.2.docx"))
    topics: list[Topic] = []
    topic: Topic | None = None
    for kind, el in iter_body(doc):
        if kind == "p":
            text = para_text(el)
            if not text or text.startswith("SYNTAX MAP") or text == "常见并列结构和平行成分表":
                continue
            if text.startswith("PART"):
                continue
            if topic is None:
                # PART 后的标题 + 副题
                topic = Topic(no="", title=text, blocks=[])
                pend_sub = True
                continue
            topic.blocks.append(("note" if len(text) < 50 else "zh", text))
            continue
        t: Table = el
        if topic is None:
            continue
        topic.no = f"4.{len(topics) + 1}"
        for r in t.rows[1:]:
            c = [cell_lines(x) for x in r.cells]
            level = " ".join(c[0])
            sent = " ".join(x for x in c[1])
            parts = " ".join(c[2]) if len(c) > 2 else ""
            lines = sent.split("  ") if "  " in sent else [sent]
            en = lines[0]
            zh = " ".join(lines[1:]) if len(lines) > 1 else ""
            # sent 内可能已含中文行（cell 多段落）
            en_lines = [x for x in c[1] if not is_cjk(x)]
            zh_lines = [x for x in c[1] if is_cjk(x)]
            en = " ".join(en_lines)
            zh = " ".join(zh_lines)
            topic.blocks.append(("item", level, ""))
            clauses = [p.strip() for p in re.split(r"\s*/\s*", parts) if p.strip()]
            topic.blocks.append(("enbold", en, clauses))
            if zh:
                topic.blocks.append(("zh", zh))
            if parts:
                topic.blocks.append(("zh", f"平行成分：{parts}"))
        topics.append(topic)
        topic = None
    return Section(no="04", title="常见并列结构和平行成分表", topics=topics)


def parse_clause_docx(fname: str, sec_no: str, sec_title: str, kicker: str) -> Section:
    """定语从句 / 名词性从句：段落流 '关系词  类型\\t句子' + 译文行。"""
    doc = Document(str(PAGES_DIR / "句法语法底盘" / fname))
    topic = Topic(no=sec_no, title=sec_title, blocks=[])
    for p in doc.paragraphs:
        text = para_text(p)
        if not text or text.startswith(kicker) or text == sec_title:
            continue
        if re.match(r"^第[一二三四]部分", text) or re.match(r"^(that|which|who|whom|whose|when|where|why|how|what|whether|if|because|as if|it)\b.*\t", text):
            if re.match(r"^第[一二三四]部分", text):
                topic.blocks.append(("subhead", re.sub(r"\s+", " ", text)))
                continue
        if re.match(r"^(关系代词|关系副词|主语|宾语|表语|同位语)\s*位置|^(that|which|who)\s*/", text):
            topic.blocks.append(("case", re.sub(r"\s+", " ", text)))
            continue
        if "\t" in text:
            label, sentence, clause = bold_clause(p)
            if label:
                m = re.match(r"^(\S+)\s+(.*)$", label)
                if m:
                    topic.blocks.append(("itemraw", f'<span lang="en">{esc(m.group(1))}</span>　{esc(m.group(2))}', ""))
                else:
                    topic.blocks.append(("item", label, ""))
            if clause:
                topic.blocks.append(("enbold", sentence, [clause]))
            else:
                topic.blocks.append(("en", sentence))
            continue
        # 无 tab 行：介绍文字或译文
        if is_cjk(text):
            topic.blocks.append(("zh", text))
        else:
            topic.blocks.append(("en", text))
    return Section(no=sec_no, title=sec_title, topics=[topic])


def parse_discourse() -> Section:
    doc = Document(str(PAGES_DIR / "语篇衔接与阅读题型" / "01-逻辑词与语篇衔接手段表-v0.3.docx"))
    topics: list[Topic] = []
    topic: Topic | None = None
    page_no = 0
    pend: list[str] = []
    last_rel = ""
    for kind, el in iter_body(doc):
        if kind == "p":
            text = para_text(el)
            if not text:
                continue
            m = re.match(r"DISCOURSE\s+(\d+)", text)
            if m:
                if topic:
                    topics.append(topic)
                topic = None
                page_no = int(m.group(1))
                pend = []
                last_rel = ""
                continue
            if topic is None:
                pend.append(text)
                if len(pend) == 2:
                    topic = Topic(no=f"1.{page_no}", title=pend[0], blocks=[("zh", pend[1])])
                continue
            topic.blocks.append(("zh", text))
            continue
        t: Table = el
        if topic is None:
            continue
        for r in t.rows[1:]:
            c = [cell_lines(x) for x in r.cells]
            rel = " ".join(c[0])
            marker = " ".join(c[1])
            sent_lines = c[2]
            en = " ".join(x for x in sent_lines if not is_cjk(x))
            zh = " ".join(x for x in sent_lines if is_cjk(x))
            if rel and rel != last_rel:
                last_rel = rel
                topic.blocks.append(("subhead", rel))
            if marker:
                topic.blocks.append(("item", marker, ""))
            if en:
                topic.blocks.append(("enbold", en, [marker] if marker else []))
            if zh:
                topic.blocks.append(("zh", zh))
    if topic:
        topics.append(topic)
    return Section(no="01", title="逻辑词与语篇衔接手段表", topics=topics)


# ---------- 装配 ----------

def extract_pages(pdf: Path) -> None:
    """两遍渲染的第二遍前置：从 PDF 里找每个 section 的起始页，写 PAGES_JSON。

    判定规则：某页存在一整行恰好等于 section 标题（strip 后）即为该 section 起始页。
    目录/章扉页的条目是 "NN 标题" 同一行，不会误中。
    """
    import subprocess

    raw = subprocess.run(
        ["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout
    page_lines = [[ln.strip() for ln in pg.splitlines()] for pg in raw.split("\f")]

    ch1: list[Section] = [parse_phonics()] + parse_affix_sections() + [
        parse_wordfamily(),
        parse_inflection(),
        parse_irregular(),
    ] + parse_prepositions()
    ch2: list[Section] = [
        parse_sentence_components(),
        parse_basic_patterns(),
        parse_linking_verbs(),
        parse_parallel(),
        parse_clause_docx("04-定语从句例句表-v0.7.docx", "05", "定语从句例句表", "SYNTAX MAP"),
        parse_clause_docx("05-名词性从句例句表-v0.6.docx", "06", "名词性从句例句表", "SYNTAX MAP"),
    ]
    ch3: list[Section] = [parse_discourse()]

    pages: dict[str, str] = {}
    cursor = 1
    for prefix, secs in (("c1", ch1), ("c2", ch2), ("c3", ch3)):
        for sec in secs:
            for pi in range(cursor, len(page_lines)):
                if sec.title in page_lines[pi]:
                    pages[f"{prefix}:{sec.no}"] = str(pi + 1)
                    cursor = pi
                    break
            else:
                print(f"  WARN 未找到页码 {prefix}:{sec.no} {sec.title}")
    PAGES_JSON.write_text(json.dumps(pages, ensure_ascii=False, indent=1))
    print(f"wrote {PAGES_JSON}  {len(pages)} entries")


def main() -> None:
    toc_pages: dict[str, str] = {}
    if PAGES_JSON.exists():
        toc_pages = json.loads(PAGES_JSON.read_text())

    ch1: list[Section] = [parse_phonics()] + parse_affix_sections() + [
        parse_wordfamily(),
        parse_inflection(),
        parse_irregular(),
    ] + parse_prepositions()

    ch2: list[Section] = [
        parse_sentence_components(),
        parse_basic_patterns(),
        parse_linking_verbs(),
        parse_parallel(),
        parse_clause_docx("04-定语从句例句表-v0.7.docx", "05", "定语从句例句表", "SYNTAX MAP"),
        parse_clause_docx("05-名词性从句例句表-v0.6.docx", "06", "名词性从句例句表", "SYNTAX MAP"),
    ]

    ch3: list[Section] = [parse_discourse()]

    def toc_li(sec: Section, prefix: str) -> str:
        page = toc_pages.get(f"{prefix}:{sec.no}", "")
        dp = f' data-page="{page}"' if page else ""
        return f'          <li data-no="{esc(sec.no)}"{dp}><span>{esc(sec.title)}</span></li>'

    def toc_group(code: str, name: str, secs: list[Section], prefix: str) -> str:
        lis = "\n".join(toc_li(s, prefix) for s in secs)
        return f'      <div class="toc-group">\n        <h3 data-no="{code}">{name}</h3>\n        <ol>\n{lis}\n        </ol>\n      </div>'

    def opener(no: str, name: str, secs: list[Section], prefix: str,
               items: list[tuple[str, str, str]] | None = None) -> str:
        # items: (序号, 标题, toc_pages 键) —— 供长章改用板块级清单，避免 32 行溢出
        if items is None:
            items = [(s.no, s.title, f"{prefix}:{s.no}") for s in secs]
        lis = "\n".join(
            f'          <li data-no="{esc(n)}"{f" data-page={chr(34)}{toc_pages[k]}{chr(34)}" if k in toc_pages else ""}><span>{esc(t)}</span></li>'
            for n, t, k in items
        )
        return f'''    <section class="opener">
      <h1 data-no="{no}">{name}</h1>
      <nav class="toc">
        <ol>
{lis}
        </ol>
      </nav>
      <footer>澄页</footer>
    </section>'''

    def unit(no: str, name: str, secs: list[Section]) -> str:
        body = "\n".join(section_html(s) for s in secs)
        return f'''    <section class="unit" data-no="{no}" data-unit="{esc(name)}">
    <header data-no="{no}">{esc(name)}</header>
    <header data-no="{no}">{esc(name)}</header>
    <span data-fold="recto"></span>
    <span data-fold="verso"></span>
{body}
    </section>'''

    n_topics = sum(len(s.topics) for s in ch1 + ch2 + ch3)

    out = f'''<!DOCTYPE html>
<html
  lang="zh-Hans"
  data-code="底盘"
  data-unit="英语底盘"
  data-booklet="澄页 · 英语底盘"
>
  <head>
    <meta charset="UTF-8" />
    <title>基础薄弱学生英语底盘展示册</title>
    <link rel="stylesheet" href="澄页.css" />
  </head>
  <body>
    <section class="cover" data-compose="B">
      <p>基础薄弱学生 · 高中英语</p>
      <h1>英语底盘展示册</h1>
      <p>词汇 · 构词 · 介词 · 句法 · 语篇</p>
      <aside>
        <p>01 词汇与音形义 · 音标 / 词缀 / 词性转化 / 规则变形 / 不规则动词 / 介词</p>
        <p>02 句法与语法底盘 · 成分 / 句型 / 系动词 / 并列 / 从句</p>
        <p>03 语篇衔接与阅读题型 · 逻辑词 / 指代 / 复现</p>
      </aside>
      <footer>澄页</footer>
    </section>

    <nav class="toc">
      <h2>英语底盘展示册</h2>
{toc_group("01", "词汇与音形义", ch1, "c1")}
{toc_group("02", "句法与语法底盘", ch2, "c2")}
{toc_group("03", "语篇衔接与阅读题型", ch3, "c3")}
    </nav>

{opener("01", "词汇与音形义", ch1, "c1", items=[
    ("01", "音标、拼读和重音", "c1:01"),
    ("02", "词缀：前缀与后缀", "c1:02"),
    ("03", "词性转化规律", "c1:21"),
    ("04", "规则变形总表", "c1:22"),
    ("05", "不规则动词三态", "c1:23"),
    ("06", "高频介词十词", "c1:24"),
])}
{unit("01", "词汇与音形义", ch1)}

{opener("02", "句法与语法底盘", ch2, "c2")}
{unit("02", "句法与语法底盘", ch2)}

{opener("03", "语篇衔接与阅读题型", ch3, "c3")}
{unit("03", "语篇衔接与阅读题型", ch3)}
  </body>
</html>
'''
    OUT.write_text(out, encoding="utf-8")
    print(f"wrote {OUT}  sections={len(ch1)}+{len(ch2)}+{len(ch3)} topics={n_topics}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--extract-pages":
        extract_pages(Path(sys.argv[2]))
    else:
        main()
