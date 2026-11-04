#!/usr/bin/env python3
"""把识记机 PDF源/第NN周.md 排成澄页日卡 HTML。不改条目，只排版。"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

SRC_DIR = Path("/Users/huangxuewei/Projects/620分目标/识记机/PDF源")
OUT_DIR = Path("/Users/huangxuewei/Projects/自创教辅/渲染")

DAY_HEAD = re.compile(
    r"^# (\d{4})-(\d{2})-(\d{2}) (周.) · 第(\d+)天\s*$", re.M
)
MORNING_ITEM = re.compile(
    r"\*\*(文|理)(\d) · (.+?)\*\*(?:（(.+?)）)?\n\n(.+?)(?=\n\n\*\*|\n\n## )",
    re.S,
)
QUIZ_ITEM = re.compile(r"^(\d+)\. 【(.+?)】(.+)$", re.M)
ANS_WEN = re.compile(r"^- 文(\d)：(.+?)（`[^`]+`）\s*$", re.M)
ANS_LI = re.compile(r"^- 理(\d)：(.+?)（`[^`]+`）\s*$", re.M)
ANS_QUIZ = re.compile(r"^- (\d+)\. 【(.+?)】(.+?)（`[^`]+`）\s*$", re.M)
SUBJ_SHORT = {
    "数学": "数",
    "物理": "物",
    "化学": "化",
    "语文": "语",
    "道法": "道",
    "历史": "史",
}


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def blank(text: str) -> str:
    return esc(text).replace("____", "<u></u>")


# 电功率 / 二次方程等：字母+数字不是化学计量，禁止走 chem
_NOT_CHEM = re.compile(
    r"I2R|U2/R|ax2|sin2A|cos2A|(?<![A-Z])a2\+|(?<![A-Z])a2−|b2−4|P=I2|Q=I2|N/m2|y=ax|Δ=b2|x2=a|x3=a"
)
_CHEM_HINT = re.compile(
    r"--.+-->|"
    r"Mg2\+|Ca2\+|Ba2\+|Al3\+|Fe2\+|Fe3\+|Cu2\+|SO42-|CO32-|NH4\+|NO3-|HCO3-|"
    r"Fe2O3|Fe3O4|Cu2\(OH\)|Ca\(OH\)2|Na2CO3|CaCO3|CuSO4|H2SO4|KMnO4|KClO3|"
    r"(?:H2O|CO2|O2|H2|NaOH|HCl|CH4|C60|MnO2|AlCl3|FeCl2|ZnCl2|MgCl2|CaCl2|"
    r"NaCl|CuO|CaO|P2O5|H2CO3|H2O2|MgO|SO2|KCl|K2MnO4)"
)
_CHEM_EQ = re.compile(r"[=↑↓]")
_ELEM_DIGIT = re.compile(r"[A-Z][a-z]?\d")

# 电路 / 韦达：数字是下标。必须在「剩余字母+2 = 平方」之前做完。
_SUB_VARS = (
    "x1",
    "x2",
    "w1",
    "w2",
    "I1",
    "I2",
    "U1",
    "U2",
    "R1",
    "R2",
    "F1",
    "F2",
    "l1",
    "l2",
    "m1",
    "m2",
    "d1",
    "d2",
)


def is_chem(s: str) -> bool:
    if _CHEM_HINT.search(s):
        return True
    if _NOT_CHEM.search(s):
        return False
    return bool(_CHEM_EQ.search(s) and _ELEM_DIGIT.search(s))


def typeset_expr(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r"（`[^`]+`）", "", s)
    if "　" in s:
        parts = [p for p in s.split("　") if p]
        # 化学源常把方程式写两遍，只留一份
        uniq: list[str] = []
        for p in parts:
            # 源面「两空都填等号」提示，印出来像坏公式，只留后面的整式
            if re.fullmatch(r"=[；;]=", p):
                continue
            if p not in uniq:
                uniq.append(p)
        s = "　".join(uniq)
    if is_chem(s):
        return typeset_chem(s)
    return typeset_math(s)


def typeset_math(s: str) -> str:
    s = esc(s)
    # 焦耳 / 纯电阻功率：2 是平方，必须先于 I1/I2 下标
    s = s.replace("I2Rt", "<i>I</i><sup>2</sup><i>Rt</i>")
    s = s.replace("I2R", "<i>I</i><sup>2</sup><i>R</i>")
    s = s.replace("U2/R", "<i>U</i><sup>2</sup>/<i>R</i>")
    s = re.sub(r"(\d+(?:\.\d+)?)×10(\d+)", r"\1×10<sup>\2</sup>", s)
    s = s.replace("kg/m3", "kg/m<sup>3</sup>")
    s = s.replace("g/cm3", "g/cm<sup>3</sup>")
    s = s.replace("N/m2", "N/m<sup>2</sup>")
    s = s.replace(
        "am·aⁿ=am+ⁿ",
        "<i>a</i><sup>m</sup> · <i>a</i><sup>n</sup> = <i>a</i><sup>m+n</sup>",
    )
    s = s.replace("am·aⁿ=", "<i>a</i><sup>m</sup> · <i>a</i><sup>n</sup> =")
    s = s.replace("am·aⁿ", "<i>a</i><sup>m</sup> · <i>a</i><sup>n</sup>")
    s = s.replace(
        "am÷aⁿ=am-ⁿ",
        "<i>a</i><sup>m</sup> ÷ <i>a</i><sup>n</sup> = <i>a</i><sup>m−n</sup>",
    )
    s = s.replace("am÷aⁿ", "<i>a</i><sup>m</sup> ÷ <i>a</i><sup>n</sup>")
    s = s.replace("am-ⁿ", "<i>a</i><sup>m−n</sup>")
    s = s.replace("am+ⁿ", "<i>a</i><sup>m+n</sup>")
    s = s.replace("(am)ⁿ=amⁿ", "(<i>a</i><sup>m</sup>)<sup>n</sup> = <i>a</i><sup>mn</sup>")
    s = s.replace("(am)ⁿ", "(<i>a</i><sup>m</sup>)<sup>n</sup>")
    s = s.replace("（am）ⁿ", "(<i>a</i><sup>m</sup>)<sup>n</sup>")
    s = s.replace("amⁿ", "<i>a</i><sup>mn</sup>")
    s = s.replace("(ab)ⁿ=aⁿbⁿ", "(<i>ab</i>)<sup>n</sup> = <i>a</i><sup>n</sup><i>b</i><sup>n</sup>")
    s = s.replace("(ab)ⁿ", "(<i>ab</i>)<sup>n</sup>")
    s = s.replace("（ab）ⁿ", "(<i>ab</i>)<sup>n</sup>")
    s = s.replace("aⁿbⁿ", "<i>a</i><sup>n</sup><i>b</i><sup>n</sup>")
    s = s.replace("a×10ⁿ", "<i>a</i> × 10<sup><i>n</i></sup>")
    s = s.replace("a-ᵖ=1/aᵖ", "<i>a</i><sup>−p</sup> = 1/<i>a</i><sup>p</sup>")
    s = s.replace("a-ᵖ", "<i>a</i><sup>−p</sup>")
    s = s.replace("1/aᵖ", "1/<i>a</i><sup>p</sup>")
    s = s.replace("a0=", "<i>a</i><sup>0</sup>=")
    s = s.replace("a0等于", "<i>a</i><sup>0</sup>等于")
    s = s.replace("ⁿ", "<sup>n</sup>")
    s = s.replace("ₙ", "<sub>n</sub>")
    s = s.replace("ᵖ", "<sup>p</sup>")
    s = s.replace("sin2A", "sin<sup>2</sup><i>A</i>")
    s = s.replace("cos2A", "cos<sup>2</sup><i>A</i>")
    s = s.replace("ax2", "<i>ax</i><sup>2</sup>")
    s = s.replace("(x−h)2", "(<i>x</i>−<i>h</i>)<sup>2</sup>")
    s = re.sub(r"([（(][a-z][+−±\-][a-z][）)])2", r"\1<sup>2</sup>", s)
    s = re.sub(r"([（(]√[a-z][）)])2", r"\1<sup>2</sup>", s)
    s = s.replace("x2=a", "<i>x</i><sup>2</sup>=<i>a</i>")
    s = s.replace("x3=a", "<i>x</i><sup>3</sup>=<i>a</i>")
    s = s.replace("s2=", "<i>s</i><sup>2</sup>=")
    s = s.replace("√s2", "√<i>s</i><sup>2</sup>")
    s = s.replace("nπr2", "<i>n</i>π<i>r</i><sup>2</sup>")
    s = re.sub(r"\)2", ")<sup>2</sup>", s)
    for tok in _SUB_VARS:
        s = s.replace(tok, f"<i>{tok[0]}</i><sub>{tok[1]}</sub>")
    s = re.sub(r"(?<![A-Za-z</])([a-zA-Zπ])2(?!\d)", r"<i>\1</i><sup>2</sup>", s)
    s = s.replace("a−b=a+(−b)", "<i>a</i> − <i>b</i> = <i>a</i> + (−<i>b</i>)")
    s = s.replace("a÷b=a×(1/b)", "<i>a</i> ÷ <i>b</i> = <i>a</i> × (1/<i>b</i>)")
    s = s.replace("v=s/t", "<i>v</i> = <i>s</i>/<i>t</i>")
    s = s.replace("v=<u></u>", "<i>v</i> =<u></u>")
    s = s.replace("ρ=<u></u>", "<i>ρ</i> =<u></u>")
    s = s.replace("v=s总/t总", "<i>v</i> = <i>s</i><sub>总</sub>/<i>t</i><sub>总</sub>")
    s = s.replace("ρ=m/V", "<i>ρ</i> = <i>m</i>/<i>V</i>")
    s = s.replace("1≤｜a｜＜10", "1≤|<i>a</i>|＜10")
    s = s.replace("____", "<u></u>")
    return s


_RXN_ABOVE = frozenset({"Δ", "△", "点燃", "通电", "高温", "加热", "电解", "煅烧"})


def split_rxn_cond(cond: str) -> tuple[str, str]:
    parts = [p.strip() for p in re.split(r"[、,，]", cond) if p.strip()]
    if not parts:
        return "", ""
    above, below = [], []
    for p in parts:
        if p in _RXN_ABOVE:
            above.append(p)
        else:
            below.append(p)
    if not above and len(below) == 1 and not re.search(r"[A-Z]", below[0]):
        return below[0], ""
    return "、".join(above), "、".join(below)


def typeset_chem_fragment(s: str) -> str:
    s = esc(s)
    s = s.replace("g/cm3", "g/cm<sup>3</sup>")
    s = s.replace("kg/m3", "kg/m<sup>3</sup>")
    ions = (
        ("SO42-", "SO<sub>4</sub><sup>2−</sup>"),
        ("CO32-", "CO<sub>3</sub><sup>2−</sup>"),
        ("HCO3-", "HCO<sub>3</sub><sup>−</sup>"),
        ("NO3-", "NO<sub>3</sub><sup>−</sup>"),
        ("NH4+", "NH<sub>4</sub><sup>+</sup>"),
        ("Fe2O3", "Fe<sub>2</sub>O<sub>3</sub>"),
        ("Fe3O4", "Fe<sub>3</sub>O<sub>4</sub>"),
        ("Fe2+", "Fe<sup>2+</sup>"),
        ("Fe3+", "Fe<sup>3+</sup>"),
        ("Cu2+", "Cu<sup>2+</sup>"),
        ("Mg2+", "Mg<sup>2+</sup>"),
        ("Ca2+", "Ca<sup>2+</sup>"),
        ("Ba2+", "Ba<sup>2+</sup>"),
        ("Al3+", "Al<sup>3+</sup>"),
        ("OH-", "OH<sup>−</sup>"),
        ("H+", "H<sup>+</sup>"),
        ("Na+", "Na<sup>+</sup>"),
        ("K+", "K<sup>+</sup>"),
        ("Ag+", "Ag<sup>+</sup>"),
        ("Cl-", "Cl<sup>−</sup>"),
    )
    for src, dst in ions:
        s = s.replace(src, dst)
    s = re.sub(r"(?<![A-Za-z])([A-Z][a-z]?)(\d+)", r"\1<sub>\2</sub>", s)
    s = re.sub(r"(</sub>|[A-Za-z\)])(\d+)(?![<0-9+−−])", r"\1<sub>\2</sub>", s)
    return s


def rxn_arrow_html(cond: str) -> str:
    above, below = split_rxn_cond(cond)
    return (
        f'<span class="rxn-arrow"><span>{typeset_chem_fragment(above)}</span>'
        f"<span>{typeset_chem_fragment(below)}</span></span>"
    )


def typeset_chem(s: str) -> str:
    held: list[str] = []

    def stash(m: re.Match[str]) -> str:
        held.append(m.group(1))
        return f"\ue000{len(held) - 1}\ue001"

    s = re.sub(r"--([^>]+)-->", stash, s)
    body = typeset_chem_fragment(s)
    for i, cond in reversed(list(enumerate(held))):
        body = body.replace(f"\ue000{i}\ue001", rxn_arrow_html(cond))
    return body


def typeset_prompt(kind: str, prompt: str) -> str:
    if kind == "理":
        return typeset_expr(prompt)
    return blank(prompt)


def typeset_quiz_q(item: dict) -> str:
    subj = item["subj"]
    q = item["q"]
    if subj in {"数学", "物理"}:
        return typeset_math(q)
    if subj == "化学":
        return typeset_expr(q)
    return blank(q)


def mix_label(morning: list[dict], quiz: list[dict]) -> tuple[str, str]:
    li_subj = []
    for item in morning:
        if item["kind"] == "理":
            subj = item["title"].split(" · ", 1)[0]
            li_subj.append(SUBJ_SHORT.get(subj, subj[:1]))
    fifth = quiz[-1]["subj"] if quiz else ""
    seen: list[str] = []
    for s in li_subj:
        if s not in seen:
            seen.append(s)
    chip = "诗+" + "".join(seen)
    drill = "数物化语+" + fifth
    return chip, drill


def parse_week(text: str) -> dict:
    week_title = re.search(r"^# 第(\d+)周识记卡\s*$", text, re.M)
    week_range = re.search(r"^(\d{4}-\d{2}-\d{2}) 至 (\d{4}-\d{2}-\d{2})\s*$", text, re.M)
    week_no = week_title.group(1) if week_title else "01"
    days = []
    parts = re.split(r"(?=^# \d{4}-\d{2}-\d{2} )", text, flags=re.M)
    for part in parts:
        m = DAY_HEAD.search(part)
        if not m:
            continue
        y, mo, d, weekday, n = m.groups()
        date = f"{y}-{mo}-{d}"
        morning = []
        for kind, no, title, extra, prompt in MORNING_ITEM.findall(part):
            morning.append(
                {
                    "kind": kind,
                    "no": no,
                    "title": title.strip(),
                    "extra": extra or "",
                    "prompt": prompt.strip(),
                }
            )
        quiz_head = re.search(r"^## 抽测题.*$", part, re.M)
        quiz_block = part[quiz_head.end() :] if quiz_head else part
        ans_at = quiz_block.find("**答案")
        q_block = quiz_block[:ans_at] if ans_at != -1 else quiz_block
        a_block = quiz_block[ans_at:] if ans_at != -1 else ""
        quiz = [
            {"no": n, "subj": s, "q": q.strip()}
            for n, s, q in QUIZ_ITEM.findall(q_block)
        ]
        answers = {
            "wen": {n: t.strip() for n, t in ANS_WEN.findall(a_block)},
            "li": {n: t.strip() for n, t in ANS_LI.findall(a_block)},
            "quiz": [(n, s, t.strip()) for n, s, t in ANS_QUIZ.findall(a_block)],
        }
        chip, drill = mix_label(morning, quiz)
        days.append(
            {
                "n": n,
                "date": date,
                "md": mo,
                "dd": d,
                "weekday": weekday,
                "chip": chip,
                "drill": drill,
                "morning": morning,
                "quiz": quiz,
                "answers": answers,
            }
        )
    return {
        "week_no": week_no.zfill(2),
        "start": week_range.group(1) if week_range else "",
        "end": week_range.group(2) if week_range else "",
        "days": days,
    }


def morning_row(item: dict) -> str:
    label = f"{item['kind']}{item['no']}"
    if item["kind"] == "文":
        extra = f"（{esc(item['extra'])}）" if item["extra"] else ""
        title = esc(item["title"])
        prompt = typeset_prompt("文", item["prompt"])
        if "<u></u>" not in prompt:
            prompt += "<u></u>"
        head = f"{label} · {title}{extra}"
    else:
        title = esc(item["title"])
        prompt = typeset_prompt("理", item["prompt"])
        head = f"{label} · {title}"
    return f"          <p><b>{head}</b>{prompt}</p>"


def quiz_row(item: dict) -> str:
    return (
        "              <li>\n"
        f'                <p><span class="chip chip-freq">{esc(item["subj"])}</span>{typeset_quiz_q(item)}</p>\n'
        '                <p class="write"></p>\n'
        "              </li>"
    )


def split_note(text: str) -> tuple[str, str]:
    if "。注：" in text:
        ans, note = text.split("。注：", 1)
        return ans, note
    return text, ""


def answer_block(day: dict) -> str:
    lines = []
    for item in day["morning"]:
        key = item["no"]
        if item["kind"] == "文":
            body = esc(day["answers"]["wen"].get(key, ""))
            label = f"文{key}"
        else:
            body = typeset_expr(day["answers"]["li"].get(key, ""))
            label = f"理{key}"
        lines.append(f"        <p><b>{label}</b>{body}</p>")
    quiz_lis = []
    for n, _s, t in day["answers"]["quiz"]:
        ans, note = split_note(t)
        body = typeset_expr(ans)
        if note:
            body += f' <span class="note">{esc(note)}</span>'
        quiz_lis.append(f"          <li>{body}</li>")
    ol = "        <ol>\n" + "\n".join(quiz_lis) + "\n        </ol>"
    return "\n".join(lines) + "\n" + ol


def render_day(day: dict) -> str:
    coord = f"{day['md']}-{day['dd']} {day['weekday']} · {day['chip']}"
    morning = "\n".join(morning_row(i) for i in day["morning"])
    quiz = "\n".join(quiz_row(i) for i in day["quiz"])
    return f"""    <section class="unit day" data-no="{day['n']}" data-unit="{esc(coord)}">
      <header data-no="{day['n']}">{esc(coord)}</header>
      <header data-no="{day['n']}">{esc(coord)}</header>
      <span data-fold="recto"></span>
      <span data-fold="verso"></span>
      <div class="face">
        <header class="topic-head" data-no="{day['n']}">
          <h3>{day['date']} {day['weekday']}</h3>
        </header>
        <div class="stem">
          <p>早读 · 古诗 3 + 公式 2</p>
{morning}
        </div>
        <div class="drill">
          <h4><span>抽测 · {esc(day['drill'])}</span></h4>
          <div class="drill-atoms">
            <ol>
{quiz}
            </ol>
          </div>
        </div>
      </div>
      <p class="fold">对折朝下，写完再看</p>
      <div class="answer-key">
{answer_block(day)}
      </div>
    </section>"""


def render_html(week: dict) -> str:
    no = week["week_no"]
    toc_items = []
    for i, day in enumerate(week["days"], start=2):
        fifth = day["quiz"][-1]["subj"] if day["quiz"] else ""
        label = f"{day['md']}-{day['dd']} {day['weekday']} · {day['chip']} / {fifth}"
        toc_items.append(
            f'          <li data-no="{day["n"]}" data-page="{i}"><span>{esc(label)}</span></li>'
        )
    toc = "\n".join(toc_items)
    if week["start"] and week["end"] and week["start"] == week["end"]:
        opener_foot = week["start"]
    else:
        opener_foot = f"{week['start']} 至 {week['end']}"
    days_html = "\n\n".join(render_day(d) for d in week["days"])
    day_n = len(week["days"])
    intro = ""
    if no == "01":
        intro = """
      <aside>
        <p>每天一张纸。上半页是题，写完顺着虚线朝下折，再看底下。</p>
        <p>早饭前三句诗、两条公式。作业后再做五道：数理化语每天都有，道法历史隔天轮。</p>
        <p>2026-09-09 用到 2027-06-30。</p>
      </aside>"""
    return f"""<!DOCTYPE html>
<html
  lang="zh-Hans"
  data-code="识记 · {no}"
  data-unit="第{no}周"
  data-booklet="东莞2027中考"
>
  <head>
    <meta charset="UTF-8" />
    <title>识记卡 · 第{no}周</title>
    <link rel="stylesheet" href="澄页.css" />
  </head>
  <body>
    <section class="opener" data-days="{day_n}">
      <h1 data-no="{no}">识记卡</h1>
      <nav class="toc">
        <ol>
{toc}
        </ol>
      </nav>{intro}
      <footer>{opener_foot}</footer>
    </section>

{days_html}
  </body>
</html>
"""


def write_week(week_no: int) -> dict:
    src = SRC_DIR / f"第{week_no:02d}周.md"
    week = parse_week(src.read_text(encoding="utf-8"))
    out = OUT_DIR / f"识记机-第{week['week_no']}周.html"
    out.write_text(render_html(week), encoding="utf-8")
    return week


_TYPESET_BAD = (
    (re.compile(r"I<sub>2</sub>R"), "I²R 被收成 I₂R"),
    (re.compile(r"U<sub>2</sub>/R"), "U²/R 被收成 U₂/R"),
    (re.compile(r"Mg<sub>2</sub>\+"), "Mg²⁺ 被收成 Mg₂⁺"),
    (re.compile(r"Ca<sub>2</sub>\+"), "Ca²⁺ 被收成 Ca₂⁺"),
    (re.compile(r"SO<sub>42</sub>"), "SO₄²⁻ 被收成 SO₄₂"),
    (re.compile(r"CO<sub>32</sub>"), "CO₃²⁻ 被收成 CO₃₂"),
    (re.compile(r"×10\d"), "科学记数未上标"),
    (re.compile(r"[ⁿₙᵖ]"), "Unicode 伪指数"),
    (re.compile(r"--[^>]+-->"), "化学箭头未收"),
    (re.compile(r" —[^<\n]{0,24}→"), "反应条件挤在箭杆上"),
    (re.compile(r"(?<![<\w])(ax2|sin2A|cos2A|\(a\+b\)2|\(a−b\)2)"), "平方仍是扁 2"),
    (re.compile(r"(?<![;\w>])a0="), "零指数仍是扁 a0="),
    (re.compile(r">=\s*[；;]\s*="), "钥匙残留 =；="),
    (re.compile(r"瞳瞳识记机|曈曈识记机"), "刊名残留瞳瞳/曈曈"),
)


def audit_html(path: Path) -> list[str]:
    html_text = path.read_text(encoding="utf-8")
    problems = []
    for rx, why in _TYPESET_BAD:
        if rx.search(html_text):
            problems.append(f"{path.name}：{why}")
    return problems


def audit_week(week: dict) -> list[str]:
    problems = []
    no = week["week_no"]
    if not week["days"]:
        problems.append(f"第{no}周：没有解析到任何一天")
        return problems
    for day in week["days"]:
        tag = f"第{no}周 {day['date']}"
        wen = [i for i in day["morning"] if i["kind"] == "文"]
        li = [i for i in day["morning"] if i["kind"] == "理"]
        if len(wen) != 3 or len(li) != 2:
            problems.append(f"{tag}：早读 {len(wen)} 文 + {len(li)} 理")
        if len(day["quiz"]) != 5:
            problems.append(f"{tag}：抽测 {len(day['quiz'])} 条")
        for item in wen:
            if not day["answers"]["wen"].get(item["no"]):
                problems.append(f"{tag}：缺文{item['no']}答案")
        for item in li:
            if not day["answers"]["li"].get(item["no"]):
                problems.append(f"{tag}：缺理{item['no']}答案")
        if len(day["answers"]["quiz"]) != 5:
            problems.append(f"{tag}：抽测答案 {len(day['answers']['quiz'])} 条")
    return problems


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "1"
    if arg in {"all", "--all"}:
        problems = []
        total_days = 0
        for n in range(1, 44):
            week = write_week(n)
            total_days += len(week["days"])
            problems.extend(audit_week(week))
            problems.extend(audit_html(OUT_DIR / f"识记机-第{week['week_no']}周.html"))
            print(f"wrote 第{week['week_no']}周 ({len(week['days'])} days)")
        print(f"html {43} weeks / {total_days} days")
        if problems:
            print("AUDIT")
            for p in problems:
                print(p)
            sys.exit(1)
        return
    week = write_week(int(arg))
    problems = audit_week(week)
    problems.extend(audit_html(OUT_DIR / f"识记机-第{week['week_no']}周.html"))
    print(f"wrote 第{week['week_no']}周 ({len(week['days'])} days)")
    for p in problems:
        print(p)
    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
