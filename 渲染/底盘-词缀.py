#!/usr/bin/env python3
"""把合订试排 v0.1 的词缀段（原 8–56 页）收成澄页 schema HTML。不发明 class。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

SRC = Path(
    "/Users/huangxuewei/Desktop/教学资料/11_通用学生资料"
    "/03_基础补弱/基础薄弱学生英语底盘展示册/04-DOCX成稿"
    "/基础薄弱学生英语底盘展示册-合订试排-v0.1.docx"
)
OUT = Path("/Users/huangxuewei/Projects/自创教辅/渲染/底盘-词缀.html")

STYLE = {"1": "normal", "3": "h1", "4": "h2", "5": "h3"}
GUIDE = re.compile(r"^(PREFIX|SUFFIX) FIELD GUIDE\s+(\d+)\s*$")
END_MARKERS = ("词性转化", "WORD FAMILY", "IRREGULAR", "转化规律")
ARROW = re.compile(r"\s*(?:->|→)\s*")
CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")
SENTENCE_END = re.compile(r"[.!?。！？]")


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def para_text(el) -> str:
    parts: list[str] = []
    for node in el.iter():
        if node.tag == qn("w:t") and node.text:
            parts.append(node.text)
        elif node.tag == qn("w:tab"):
            parts.append("\t")
    return "".join(parts).replace("\u00a0", " ").strip()


def para_style(el) -> str:
    ppr = el.find(qn("w:pPr"))
    if ppr is None:
        return "normal"
    ps = ppr.find(qn("w:pStyle"))
    if ps is None:
        return "normal"
    return STYLE.get(ps.get(qn("w:val")), "normal")


def is_cjk(text: str) -> bool:
    return bool(CJK.search(text))


def split_affixes(title: str) -> list[str]:
    return [p.strip() for p in re.split(r"\s*/\s*", title) if p.strip()]


def parse_pairs(text: str) -> list[tuple[str, str]] | None:
    raw = text.replace("→", "->")
    if "->" not in raw:
        return None
    if "\t" in raw:
        parts = [p.strip() for p in raw.split("\t") if p.strip()]
        pairs: list[tuple[str, str]] = []
        i = 0
        while i < len(parts):
            if i + 2 < len(parts) and parts[i + 1] == "->":
                pairs.append((parts[i], parts[i + 2]))
                i += 3
            elif i + 1 < len(parts) and parts[i] != "->" and "->" not in parts[i]:
                # able -> unable glued? unlikely
                i += 1
            else:
                i += 1
        return pairs or None
    bits = [p.strip() for p in raw.split() if p.strip() and p != "->"]
    # "college -> pre-college presentation -> pre-presentation" without tabs
    tokens = [p.strip() for p in re.split(r"\s+", raw) if p.strip()]
    pairs = []
    i = 0
    while i < len(tokens):
        if i + 2 < len(tokens) and tokens[i + 1] == "->":
            pairs.append((tokens[i], tokens[i + 2]))
            i += 3
        else:
            i += 1
    return pairs or None


def parse_words(text: str, section: str = "") -> list[str] | None:
    if parse_pairs(text):
        return None
    in_word_slot = section in {"例词", "常见整体词"}
    if "\t" in text:
        words = [p.strip() for p in text.split("\t") if p.strip()]
        if words and all(not is_cjk(w) and len(w) < 40 for w in words):
            return words
    if " / " in text and not is_cjk(text) and not SENTENCE_END.search(text.rstrip("./")):
        words = [p.strip() for p in text.split(" / ") if p.strip()]
        if 2 <= len(words) <= 12 and all(len(w) < 30 for w in words):
            return words
    if in_word_slot and not is_cjk(text) and not SENTENCE_END.search(text) and len(text) <= 40:
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9\-']*(?:\s+[A-Za-z][A-Za-z0-9\-']*)*", text):
            return [text]
    return None


def parse_item(text: str) -> list[tuple[str, str]] | None:
    if "=" not in text or "->" in text:
        return None
    chunks = [c.strip() for c in re.split(r"[；;]", text) if c.strip()]
    items: list[tuple[str, str]] = []
    for chunk in chunks:
        if " = " in chunk:
            left, right = chunk.split(" = ", 1)
        elif "=" in chunk:
            left, right = chunk.split("=", 1)
        else:
            return None
        left, right = left.strip(), right.strip()
        if not left or not right or " " in left and len(left) > 24:
            return None
        items.append((left, right))
    return items or None


def mark_affixes(text: str, affixes: list[str]) -> str:
    out = esc(text)
    used = 0

    def repl(m: re.Match) -> str:
        nonlocal used
        if used >= 3:
            return m.group(0)
        used += 1
        return f'<span class="em-atom">{m.group(0)}</span>'

    for aff in sorted(affixes, key=len, reverse=True):
        token = esc(aff)
        if not token:
            continue
        out = re.sub(
            r"(?<![\w\-])" + re.escape(token) + r"(?![\w\-])",
            repl,
            out,
        )
    return out


@dataclass
class Topic:
    no: str
    affix: str
    gloss: str
    blocks: list = field(default_factory=list)


@dataclass
class Group:
    code: str
    kind: str
    title: str
    affix_line: str
    topics: list[Topic] = field(default_factory=list)


def load_items(doc: Document) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    started = False
    for child in doc.element.body.iterchildren():
        if child.tag != qn("w:p"):
            continue
        text = para_text(child)
        if not text:
            continue
        if not started:
            if GUIDE.match(text) and text.endswith("02"):
                started = True
            else:
                continue
        if started and any(m in text for m in END_MARKERS):
            break
        items.append((para_style(child), text))
    return items


def parse(items: list[tuple[str, str]]) -> list[Group]:
    groups: list[Group] = []
    group: Group | None = None
    topic: Topic | None = None
    section = ""
    header_buf: list[str] = []
    word_buf: list[str] = []
    held_en: str | None = None

    def flush_lists():
        nonlocal word_buf
        if topic is None:
            word_buf = []
            return
        if word_buf:
            topic.blocks.append(("words", list(word_buf)))
            word_buf = []

    def flush_en():
        nonlocal held_en
        if topic is not None and held_en:
            topic.blocks.append(("en", held_en))
            held_en = None

    def close_topic():
        nonlocal topic, section, held_en
        flush_lists()
        flush_en()
        if group is not None and topic is not None:
            group.topics.append(topic)
        topic = None
        section = ""
        held_en = None

    def close_group():
        nonlocal group, header_buf
        close_topic()
        if group is not None:
            if header_buf and not group.title:
                group.title = header_buf[0]
                group.affix_line = header_buf[1] if len(header_buf) > 1 else ""
            groups.append(group)
        group = None
        header_buf = []

    for style, text in items:
        m = GUIDE.match(text)
        if m:
            close_group()
            group = Group(code=m.group(2), kind=m.group(1), title="", affix_line="")
            header_buf = []
            continue

        if group is None:
            continue

        if style == "h1":
            close_topic()
            if header_buf:
                group.title = group.title or header_buf[0]
                if len(header_buf) > 1:
                    group.affix_line = group.affix_line or header_buf[1]
                header_buf = []
            if "\t" in text:
                affix, gloss = text.split("\t", 1)
            else:
                affix, gloss = text, ""
            n = len(group.topics) + 1
            topic = Topic(no=f"{int(group.code)}.{n}", affix=affix.strip(), gloss=gloss.strip())
            continue

        if topic is None:
            header_buf.append(text)
            continue

        if style == "h3":
            flush_lists()
            flush_en()
            label = re.sub(r"\s+", " ", text).strip()
            section = label
            if label == "容易误判":
                continue
            topic.blocks.append(("subhead", label))
            continue

        if text.startswith("注意"):
            flush_lists()
            flush_en()
            note = re.sub(r"^注意\s*", "", text).strip()
            topic.blocks.append(("note", note or text))
            continue

        if section == "容易误判":
            flush_lists()
            topic.blocks.append(("note", text))
            continue

        pairs = parse_pairs(text)
        if pairs:
            flush_en()
            word_buf.extend(f"{a} → {b}" for a, b in pairs)
            continue

        words = parse_words(text, section)
        if words and section in {"例词", "常见整体词"}:
            flush_en()
            word_buf.extend(words)
            continue

        items_eq = parse_item(text)
        if items_eq and section == "例词":
            flush_lists()
            flush_en()
            for term, gloss in items_eq:
                topic.blocks.append(("item", term, gloss))
            continue

        flush_lists()
        if section == "真题例句":
            if is_cjk(text):
                if held_en:
                    topic.blocks.append(("pair", held_en, text))
                    held_en = None
                else:
                    topic.blocks.append(("zh", text))
            else:
                flush_en()
                held_en = text
            continue

        flush_en()
        kind = "zh" if is_cjk(text) else "en"
        topic.blocks.append((kind, text))

    close_group()
    return groups


def phrases_html(words: list[str], indent: str) -> str:
    spans = "\n".join(
        f'{indent}  <span lang="en">{esc(w)}</span>' for w in words
    )
    return f'{indent}<p class="phrases">\n{spans}\n{indent}</p>'


def topic_html(topic: Topic) -> str:
    affixes = split_affixes(topic.affix)
    if topic.gloss and "/" not in topic.affix:
        title = f"{topic.affix}　{topic.gloss}"
    else:
        title = topic.affix
    parts = [
        f'    <section class="topic" data-no="{esc(topic.no)}">',
        f'      <header class="topic-head" data-no="{esc(topic.no)}">',
        f"        <h3>{esc(title)}</h3>",
        "      </header>",
        '      <div class="explain">',
    ]
    for block in topic.blocks:
        kind = block[0]
        if kind == "subhead":
            parts.append(f'        <p class="subhead">{esc(block[1])}</p>')
        elif kind == "words":
            parts.append(phrases_html(block[1], "        "))
        elif kind == "item":
            parts.append(
                f'        <p class="item"><b lang="en">{esc(block[1])}</b>　{esc(block[2])}</p>'
            )
        elif kind == "note":
            parts.append(f"        <aside class=\"note\"><p>{esc(block[1])}</p></aside>")
        elif kind == "pair":
            parts.append(f'        <p lang="en">{esc(block[1])}</p>')
            parts.append(f"        <p>{esc(block[2])}</p>")
        elif kind == "en":
            parts.append(f'        <p lang="en">{mark_affixes(block[1], affixes)}</p>')
        elif kind == "zh":
            parts.append(f"        <p>{mark_affixes(block[1], affixes)}</p>")
    parts.append("      </div>")
    parts.append("    </section>")
    return "\n".join(parts)


def group_code_label(group: Group) -> str:
    return group.code


# 独立目录页页码。改完正文后重渲，再按组头所在页改这一表。
TOC_PAGES = {
    "02": "3",
    "03": "5",
    "04": "7",
    "05": "9",
    "06": "11",
    "07": "13",
    "08": "15",
    "09": "16",
    "10": "18",
    "11": "19",
    "12": "20",
    "13": "22",
    "14": "23",
    "15": "24",
    "16": "26",
    "17": "27",
    "18": "29",
    "19": "31",
    "20": "33",
}


def render(groups: list[Group]) -> str:
    def toc_group(code: str, title: str, subset: list[Group]) -> str:
        lis = "\n".join(
            (
                f'          <li data-no="{esc(g.code)}" data-page="{TOC_PAGES[g.code]}"><span>{esc(g.title)}</span></li>'
                if g.code in TOC_PAGES
                else f'          <li data-no="{esc(g.code)}"><span>{esc(g.title)}</span></li>'
            )
            for g in subset
        )
        return (
            "      <div class=\"toc-group\">\n"
            f'        <h3 data-no="{esc(code)}">{esc(title)}</h3>\n'
            f"        <ol>\n{lis}\n        </ol>\n"
            "      </div>"
        )

    prefixes = [g for g in groups if g.kind == "PREFIX"]
    suffixes = [g for g in groups if g.kind == "SUFFIX"]
    book_toc = [
        toc_group("前", "前缀", prefixes),
        toc_group("后", "后缀", suffixes),
    ]

    body_bits = []
    for g in groups:
        body_bits.append(
            "    <div class=\"toc-group\">\n"
            f'      <h3 data-no="{esc(group_code_label(g))}">{esc(g.title)}</h3>\n'
            "    </div>"
        )
        for t in g.topics:
            body_bits.append(topic_html(t))

    prefix_n = sum(1 for g in groups if g.kind == "PREFIX")
    suffix_n = sum(1 for g in groups if g.kind == "SUFFIX")
    topic_n = sum(len(g.topics) for g in groups)

    return f"""<!DOCTYPE html>
<html
  lang="zh-Hans"
  data-code="词缀"
  data-unit="词缀"
  data-booklet="澄页 · 英语底盘"
>
  <head>
    <meta charset="UTF-8" />
    <title>英语底盘 · 词缀</title>
    <link rel="stylesheet" href="澄页.css" />
  </head>
  <body>
    <section class="cover" data-compose="B">
      <p>高中英语 · 底盘展示</p>
      <h1>词缀</h1>
      <p>前缀与后缀识别 · 真题例词</p>
      <aside>
        <p>02–07 前缀 · 否定 / 时间 / 程度 / 空间 / 自我 / 主题</p>
        <p>08–20 后缀 · 性质 / 人物 / 名词 / 形容词 / 副词</p>
        <p>{topic_n} 个识别条目 · 真题例词</p>
      </aside>
      <footer>澄页</footer>
    </section>

    <nav class="toc">
      <h2>词缀</h2>
{chr(10).join(book_toc)}
    </nav>

    <section class="unit" data-no="01" data-unit="词缀">
    <header data-no="01">词缀</header>
    <header data-no="01">词缀</header>
    <span data-fold="recto"></span>
    <span data-fold="verso"></span>
{chr(10).join(body_bits)}
    </section>
  </body>
</html>
"""


def apply_toc_pages(html: str, pages: dict[str, str]) -> str:
    def repl(m: re.Match) -> str:
        code = m.group(1)
        page = pages.get(code)
        if not page:
            return m.group(0)
        return f'<li data-no="{code}" data-page="{page}">'

    return re.sub(r'<li data-no="(\d+)">', repl, html)


def main() -> None:
    groups = parse(load_items(Document(str(SRC))))
    if not groups:
        raise SystemExit("no groups parsed")
    html_out = render(groups)
    OUT.write_text(html_out, encoding="utf-8")
    topics = sum(len(g.topics) for g in groups)
    notes = sum(1 for g in groups for t in g.topics for b in t.blocks if b[0] == "note")
    pairs = sum(1 for g in groups for t in g.topics for b in t.blocks if b[0] == "pair")
    print(f"wrote {OUT}")
    print(f"groups={len(groups)} topics={topics} notes={notes} exam-pairs={pairs}")
    for g in groups:
        affixes = " / ".join(t.affix for t in g.topics)
        print(f"  {g.code} {g.title} ({len(g.topics)}) {affixes}")


if __name__ == "__main__":
    main()
