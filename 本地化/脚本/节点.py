"""段考节点判定：每学期四个节点——期中前月考、期中、期中后月考、期末。

月考归属先看序号（第一次 / 第二次……），再看月份：
  上学期  9、10 月 → 期中前；11、12、1 月 → 期中后（11 月为推定）
  下学期  2、3、4 月 → 期中前（4 月为推定）；5、6 月 → 期中后
联考按同样规则归入月考 / 期中 / 期末。判不出的标「月考?」。
"""
import re

NODES = ('期中前月考', '期中', '期中后月考', '期末')
GRADE_TERMS = ('高一上', '高一下', '高二上', '高二下')   # 全年 16 册按此顺序 × NODES 连续编号


def split_gt(gt):
    """'高一上' → ('高一', '上')。"""
    return gt[:2], gt[2:]


def book_no(gt, node):
    """全年连续册号（2026-11-05 定）：高一上 01–04、高一下 05–08、高二上 09–12、高二下 13–16；节点顺序同 NODES。"""
    return f'{GRADE_TERMS.index(gt) * len(NODES) + NODES.index(node) + 1:02d}'


def all_books():
    """16 个 (年级学期, 节点)，按全年册号顺序。"""
    return [(gt, n) for gt in GRADE_TERMS for n in NODES]


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


# 口径（2026-11-05 负责人定）：
#  · 特征词专题（非谓语——东莞解析常把它写成「考查动词」，只能看全文；it 形式主宾语、强调句、虚拟、倒装、独立主格、反意疑问）：解析全文出现即算——这些词不会当套话写；
#  · 易成套话的专题（非谓语、各类从句、被动、时态、情态、比较级、省略）：只看「考查……」那一句；
#    状语从句另认「考查连词」且答案以从属连词开头的题（解析常把 although / unless 写成「考查连词」）；
#  · 主谓一致：提到就近原则，或「考查」句里有主谓一致且不夹时态／语态／短语／搭配。
LOOSE = {'非谓语', 'it 形式主语／宾语', '强调句', '虚拟语气', '倒装', '独立主格／with 复合', '反意疑问'}
SUBORD = re.compile(r'(?i)^\(?\s*(although|though|even though|even if|because|unless|while|whereas|when|whenever|if|as|since|until|till|before|after|once|so that|in order that|now that|as long as|as soon as|no matter|wherever|however|whatever)\b')


def topic_hit(name, pat, jie, ans=''):
    jie = jie or ''
    m = re.search(r'考查([^。]*)', jie)
    clause = m.group(1) if m else jie   # 无「考查」句的解析（另一种体例）退回全文
    if name in LOOSE:
        return re.search(pat, jie) is not None
    if name == '主谓一致':
        if '就近原则' in jie:
            return True
        return '主谓一致' in clause and not re.search(r'时态|语态|短语|搭配', clause)
    if re.search(pat, clause):
        return True
    if name == '状语从句' and '连词' in clause and SUBORD.match((ans or '').strip()):
        return True
    return False


# 段考专题（TOPICS）：段考专题.py、段考选题.py 共用，只在这里改。
# 名称与定稿 JSON 的 topics[].name、overview.rows[].name 对应（「it 形式主宾语」是讲义里的短称）。
TOPICS = [
    ('非谓语', r'非谓语|动名词|不定式|现在分词|过去分词'),
    ('it 形式主语／宾语', r'形式主语|形式宾语'),
    ('定语从句', r'定语从句'),
    ('名词性从句', r'宾语从句|主语从句|表语从句|同位语从句|名词性从句'),
    ('状语从句', r'状语从句'),
    ('强调句', r'强调句'),
    ('虚拟语气', r'虚拟'),
    ('倒装', r'倒装'),
    ('主谓一致', r'主谓一致|就近原则'),
    ('独立主格／with 复合', r'独立主格|with\s*复合|with的复合'),
    ('被动', r'被动'),
    ('时态', r'一般过去时|现在完成|过去完成|将来时|进行时'),
    ('情态动词', r'情态动词'),
    ('比较级', r'比较级|最高级'),
    ('省略', r'省略'),
    ('反意疑问', r'反意疑问|附加疑问'),
]
