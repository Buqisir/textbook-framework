"""段考节点判定：每学期四个节点——期中前月考、期中、期中后月考、期末。

月考归属先看序号（第一次 / 第二次……），再看月份：
  上学期  9、10 月 → 期中前；11、12、1 月 → 期中后（11 月为推定）
  下学期  2、3、4 月 → 期中前（4 月为推定）；5、6 月 → 期中后
联考按同样规则归入月考 / 期中 / 期末。判不出的标「月考?」。
"""
import re

NODES = ('期中前月考', '期中', '期中后月考', '期末')


_CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12}


def _month(fn):
    m = re.search(r'(?<!\d)(\d{1,2})月', fn)
    if m:
        return int(m.group(1))
    m = re.search(r'(十[一二]|[一二三四五六七八九十])月', fn)
    return _CN[m.group(1)] if m else None


def node_of(fn, rs):
    """fn: 文件名；rs: 该卷的题记录。返回 (年级, 学期, 节点, 推定?)。"""
    grade = rs[0]['年级']
    sem = rs[0]['学期']
    yuan = {r['考试原文'] or '' for r in rs}
    mo = _month(fn)
    term = sem if sem in ('上', '下') else (
        None if mo is None else ('上' if mo in (9, 10, 11, 12, 1) else '下'))
    if term is None:
        return grade, '?', '月考?', True
    if '期末' in fn or any('期末' in y for y in yuan):
        return grade, term, '期末', False
    if '期中' in fn or '中段' in fn or any('期中' in y or '中段' in y for y in yuan):
        return grade, term, '期中', False
    if re.search(r'第一次|月考一|月考（一）|（一）|期初', fn):
        return grade, term, '期中前月考', False
    if re.search(r'第二次|第三次|月考二|月考（二）|（二）|（三）', fn):
        return grade, term, '期中后月考', False
    if mo is not None:
        if term == '上':
            if mo in (9, 10):
                return grade, term, '期中前月考', False
            if mo in (11, 12, 1):
                return grade, term, '期中后月考', mo == 11
        else:
            if mo in (2, 3):
                return grade, term, '期中前月考', False
            if mo == 4:
                return grade, term, '期中前月考', True
            if mo in (5, 6):
                return grade, term, '期中后月考', False
    return grade, term, '月考?', True


def papers(rows):
    """把同一份卷的多个文件并成一卷：两文件共享的重复组 ≥ 较小者题数的 80% 即视为同卷。
    返回 [(代表文件, [全部文件], 年级, 学期, 节点, 推定?)]。代表文件优先取期中 / 期末（标题明确）。"""
    from collections import defaultdict
    files = defaultdict(list)
    for r in rows:
        files[r['文件']].append(r)
    groups = {f: {r['重复组'] for r in rs if r['重复组'] is not None} for f, rs in files.items()}
    parent = {f: f for f in files}

    def find(f):
        while parent[f] != f:
            parent[f] = parent[parent[f]]
            f = parent[f]
        return f

    fs = list(files)
    for i, a in enumerate(fs):
        for b in fs[i + 1:]:
            o = len(groups[a] & groups[b])
            if o and o >= 0.8 * min(len(files[a]), len(files[b])):
                parent[find(a)] = find(b)
    clusters = defaultdict(list)
    for f in fs:
        clusters[find(f)].append(f)
    out = []
    for members in clusters.values():
        info = {f: node_of(f, files[f]) for f in members}
        rank = {'期末': 0, '期中': 1, '期中前月考': 2, '期中后月考': 2, '月考?': 3}
        rep = min(sorted(members), key=lambda f: (info[f][3], rank[info[f][2]]))
        g, t, n, guess = info[rep]
        out.append((rep, sorted(members), g, t, n, guess))
    return out


def topic_hit(name, pat, jie):
    """解析命中专题。主谓一致特殊：东莞解析常把「时态和主谓一致」当套话写在任何谓语题上，
    只有 ①提到就近原则，或 ②「考查」句里有主谓一致且不夹时态／语态／短语／搭配，才算。"""
    jie = jie or ''
    if name != '主谓一致':
        return re.search(pat, jie) is not None
    if '就近原则' in jie:
        return True
    m = re.search(r'考查([^。]*)', jie)
    return bool(m and '主谓一致' in m.group(1) and not re.search(r'时态|语态|短语|搭配', m.group(1)))
