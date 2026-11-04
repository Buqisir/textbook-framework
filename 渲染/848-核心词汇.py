#!/usr/bin/env python3
"""把对齐后的 848 主词收成澄页 schema HTML。不发明 class。"""

from __future__ import annotations

import html
import re
from collections import OrderedDict
from pathlib import Path

from docx import Document

SRC = Path(
    "/Users/huangxuewei/Projects/自创教辅/848词汇"
    "/高考英语核心词汇真题考点精编（学生版）-去中文释义.docx"
)
OUT = Path("/Users/huangxuewei/Projects/自创教辅/渲染/848-核心词汇.html")

LINE = re.compile(r"^(\d+)\.\s*(.+?)\s+/([^/]+)/\s*(.*)$")


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def load_entries() -> list[dict]:
    doc = Document(str(SRC))
    entries: list[dict] = []
    for para in doc.paragraphs:
        raw = para.text.strip()
        if not raw:
            continue
        m = LINE.match(raw)
        if not m:
            raise SystemExit(f"unparsed: {raw}")
        rest = m.group(4)
        forms = ""
        if "【词形】" in rest:
            rest, forms = rest.split("【词形】", 1)
        word = m.group(2).strip()
        letter = next((ch.upper() for ch in word if ch.isalpha()), "#")
        entries.append(
            {
                "idx": int(m.group(1)),
                "word": word,
                "ipa": m.group(3).strip(),
                "pos_mean": rest.strip(),
                "forms": forms.strip(),
                "letter": letter,
            }
        )
    if len(entries) != 848:
        raise SystemExit(f"expected 848 entries, got {len(entries)}")
    return entries


def group_by_letter(entries: list[dict]) -> OrderedDict[str, list[dict]]:
    groups: OrderedDict[str, list[dict]] = OrderedDict()
    for e in entries:
        groups.setdefault(e["letter"], []).append(e)
    return groups


def item_html(e: dict) -> str:
    bits = [
        f'<b>{e["idx"]}</b>',
        f'<b lang="en">{esc(e["word"])}</b>',
        f'<span lang="en">/{esc(e["ipa"])}/</span>',
        esc(e["pos_mean"]),
    ]
    line = "　".join(bits)
    if e["forms"]:
        line += f"　【词形】<span lang=\"en\">{esc(e['forms'])}</span>"
    return f'        <p class="item">{line}</p>'


def topic_html(letter: str, items: list[dict]) -> str:
    first, last = items[0]["idx"], items[-1]["idx"]
    title = f"{letter}　{first}–{last}"
    rows = "\n".join(item_html(e) for e in items)
    return f"""    <section class="topic" data-no="{esc(letter)}">
      <header class="topic-head" data-no="{esc(letter)}">
        <h3>{esc(title)}</h3>
        <span class="chip chip-freq">{len(items)}词</span>
      </header>
      <div class="explain">
{rows}
      </div>
    </section>"""


def render(groups: OrderedDict[str, list[dict]]) -> str:
    toc_lis = "\n".join(
        f'          <li data-no="{esc(letter)}"><span>{esc(letter)} · {len(items)} 词'
        f'（{items[0]["idx"]}–{items[-1]["idx"]}）</span></li>'
        for letter, items in groups.items()
    )
    topics = "\n".join(topic_html(letter, items) for letter, items in groups.items())
    return f"""<!DOCTYPE html>
<html
  lang="zh-Hans"
  data-code="词汇 · 848"
  data-unit="核心词汇"
  data-booklet="澄页 · 核心词汇"
>
  <head>
    <meta charset="UTF-8" />
    <title>高考核心词汇 · 848</title>
    <link rel="stylesheet" href="澄页.css" />
  </head>
  <body>
    <section class="cover" data-compose="B">
      <p>高中英语 · 核心词汇</p>
      <h1>高考核心词汇</h1>
      <p>真题考点精编 · 848 词</p>
      <aside>
        <p>主词 848 · 音标 / 词性释义 / 词形族</p>
        <p>释义与《3000 课标词汇 · 频序版》对齐</p>
        <p>按字母检索 · 序号 1–848</p>
      </aside>
      <footer>澄页</footer>
    </section>

    <nav class="toc">
      <h2>高考核心词汇</h2>
      <div class="toc-group">
        <h3 data-no="词">字母索引</h3>
        <ol>
{toc_lis}
        </ol>
      </div>
    </nav>

    <section class="unit" data-no="01" data-unit="核心词汇">
    <header data-no="01">核心词汇</header>
    <header data-no="01">核心词汇</header>
    <span data-fold="recto"></span>
    <span data-fold="verso"></span>
{topics}
    </section>
  </body>
</html>
"""


def main() -> None:
    entries = load_entries()
    groups = group_by_letter(entries)
    OUT.write_text(render(groups), encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"entries={len(entries)} letters={''.join(groups)}")
    for letter, items in groups.items():
        print(f"  {letter} {len(items):3d}  {items[0]['idx']}–{items[-1]['idx']}")


if __name__ == "__main__":
    main()
