# -*- coding: utf-8 -*-
"""搜索框二次校验（顾超 2026-11-21 21:01/21:03 令 · 最高规格通用技能）

【对账第一锚点 · 标准流程】
  对账时先在聊天搜索框输入订单金额或编号，调取带时间戳的原始交易记录，
  与工作台、账面数据做三账比对；不一致时以搜索框调出的原始记录为优先锚点，
  确认无误再推进流程；发现问题直接调三脑重新决断。
  本脚本 = 该流程的机器化实现：账里所有数字 → 镜像正文倒排检索 → 三账比对 → 红项清单。

【通用场景覆盖】
  ① 账期全量：--账期 1111 （默认读 数字唯一源.json 当前账期，上家锚/实付/差+合计+客欠+三方差）
  ② 订单告警单查：--nums 1614,3228 --家 鑫隆 （单条订单金额/编号异常时秒查原始记录）
  ③ 任意账目 json：--json <path> （提取全部金额数字通用校验）

【判定口径】
  锚金额：命中聊天原话且上下文含「需付款」或家名 → 绿（聊天原话=第一锚点成立）；
          命中但上下文弱 → 黄；零命中 → 红（三脑决断入口）。
  实付  ：命中正文或转账消息金额 → 绿；零命中 → 黄（图内金额，转付款图/S15 图锚核验，不判红）。
  派生数（差/合计/客欠/三方差）：列参考命中，不作硬判据。
"""
import argparse
import datetime
import json
import os
import re
import sys

MIRROR = r'D:\聊天抓取\区间聊天分片_1001-1111'
BUILD = r'D:\workbuddy-data\WorkBuddy\2026-09-30-12-16-33\workbench_status\build'
OUTD = os.path.join(MIRROR, 'build')
NUM_RE = re.compile(r'\d+(?:\.\d+)?')

TOKEN_RE = re.compile(r'\d+(?:\.\d+)?')


def toks(s):
    out = []
    for t in TOKEN_RE.findall(str(s)):
        try:
            v = float(t)
        except ValueError:
            continue
        if v:
            out.append(round(v, 2))
    return out


def load_corpus():
    """载入方方+吴丹全部分片正文，建 数字→消息 倒排索引（唯一真源=镜像数据分片）。"""
    idx = {}
    meta = []
    for line in ('方方', '吴丹'):
        d = os.path.join(MIRROR, '镜像数据', line)
        for fn in sorted(os.listdir(d)):
            if not fn.endswith('.json') or fn in ('索引.json', '新朋友.json'):
                continue
            try:
                j = json.load(open(os.path.join(d, fn), encoding='utf-8'))
            except Exception:
                continue
            name = j.get('name') or fn
            for m in j.get('msgs') or []:
                # 与镜像搜索框 normHit 完全同口径：正文 + 转账金额/备注 + 引用标题
                s = (m.get('x') or '')
                if m.get('ty') == 'pay' and m.get('pay'):
                    s += ' ' + str(m['pay'].get('amt') or '') + ' ' + str(m['pay'].get('memo') or '')
                if m.get('ty') == 'quote':
                    s += ' ' + str(m.get('title') or '')
                for v in toks(s):
                    idx.setdefault(v, []).append(len(meta))
                meta.append({'线': line, '会话': name, 't': m.get('t') or '',
                             'who': m.get('nick') or m.get('who') or '',
                             'mine': m.get('mine'), 'x': str(m.get('x') or '')[:70],
                             'ty': m.get('ty') or ''})
    return idx, meta


def hits(idx, meta, v, need=None, limit=6):
    """金额 v 的全部命中；need=上下文过滤词（家名/需付款）。
    返回（样例截断, 全量计数, 全量强命中计数）——强锚判定用全量计数，
    样例截断不影响判定（21:06 修复：美时代1000/星空426/雅莉莱402 因样例截断误判黄）。"""
    res = []
    n_all = n_strong = 0
    for i in idx.get(round(float(v), 2), []):
        m = meta[i]
        n_all += 1
        if need and (need in m['x']):
            n_strong += 1
        if len(res) < limit:
            if not need or need in m['x']:
                res.append(m)
    if need and not res:  # 强命中样例为空时回退全量样例
        for i in idx.get(round(float(v), 2), []):
            if len(res) >= limit:
                break
            res.append(meta[i])
    return res, n_all, n_strong


def ctx_ok(ms, name):
    """锚上下文判定：原话含「需付款」或家名 → 强锚。"""
    for m in ms:
        if '需付款' in m['x'] or (name and name in m['x']):
            return True
    return False


def probe(idx, meta, v, name='', kind='锚'):
    """单数字三账比对。kind: 锚/实付/派生"""
    strong, n_all, n_strong = hits(idx, meta, v, need=name or None)
    allm, _, _ = hits(idx, meta, v)
    r = {'数字': v, '类型': kind, '会话': name,
         '原话强命中数': n_strong, '全文命中数': n_all,
         '命中样例': [{'时间': m['t'], '线': m['线'], '会话': m['会话'],
                      '发送人': m['who'], '原文': m['x']} for m in (strong or allm)[:4]]}
    if kind == '锚':
        if n_strong:
            r['判定'] = '绿'
            r['理由'] = '聊天原话强锚成立（原话含家名，带时间戳）×%d' % n_strong
        elif n_all and ctx_ok(allm, name):
            r['判定'] = '绿'
            r['理由'] = '命中样例含「需付款」强锚'
        elif n_all:
            r['判定'] = '黄'
            r['理由'] = '数字有命中但无家名强锚，需人工看原话'
        else:
            r['判定'] = '红'
            r['理由'] = '聊天全文零命中——锚无原话依据，调三脑决断'
    elif kind == '实付':
        if n_all:
            r['判定'] = '绿'
            r['理由'] = '正文/转账消息金额命中'
        else:
            r['判定'] = '黄'
            r['理由'] = '正文零命中→图内金额，转付款图/S15 图锚核验，不判红'
    else:
        r['判定'] = '参考'
        r['理由'] = '派生数仅列参考命中'
    return r


def extract_unique_source():
    """数字唯一源.json → 校验清单（上家锚/实付/差 + 合计 + 客欠 + 三方差）。"""
    d = json.load(open(os.path.join(BUILD, '数字唯一源.json'), encoding='utf-8'))
    items = []
    for name, x in (d.get('上家') or {}).items():
        for k, kind in (('锚', '锚'), ('实付', '实付')):
            v = x.get(k)
            if v:
                items.append((v, name, kind))
        if x.get('差'):
            items.append((x['差'], name, '派生'))
    for k in ('合计', '客欠', '三方差'):
        v = d.get(k)
        if isinstance(v, (int, float)):
            items.append((v, '', '派生'))
        elif isinstance(v, dict):
            for kk, vv in v.items():
                if isinstance(vv, (int, float)) and vv:
                    items.append((vv, kk, '派生'))
    return items, d.get('账期')


# ═══════════════════════════════════════════════════════════════════════
# 外挂一：聊天搜索框接口（顾超 21:09 令）—— 可编程调用，不改原有主流程
# 输入订单金额或编号 → 拉取带时间戳的原始交易记录（与镜像搜索框 normHit 同口径）
# ═══════════════════════════════════════════════════════════════════════
_CORPUS = None


def _corpus():
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = load_corpus()
    return _CORPUS


def 聊天搜索框接口(金额或编号, 家名=None, limit=8):
    """调用聊天搜索框：输入订单金额或编号 → 带时间戳原始记录。
    数字输入走倒排精确等值；文本/编号输入走全文子串。家名可选过滤。"""
    idx, meta = _corpus()
    qs = str(金额或编号).strip()
    recs = []
    vals = toks(qs)
    if vals:
        for i in idx.get(round(vals[0], 2), []):
            m = meta[i]
            if 家名 and 家名 not in m['x']:
                continue
            recs.append(m)
    else:
        ql = qs.lower()
        for m in meta:
            if ql in m['x'].lower() and (not 家名 or 家名 in m['x']):
                recs.append(m)
                if len(recs) >= 300:
                    break
    recs.sort(key=lambda m: m['t'], reverse=True)
    return {'查询': qs, '家名': 家名 or '', '命中数': len(recs),
            '原始记录': [{'时间': m['t'], '线': m['线'], '会话': m['会话'],
                        '发送人': m['who'], '原文': m['x']} for m in recs[:limit]]}


# ═══════════════════════════════════════════════════════════════════════
# 外挂二：三账比对判断（顾超 21:09 令）—— 不一致时自动标记「优先取搜索框结果」
# 账A=聊天搜索框原话提取金额（第一锚点）；账B=工作台（数字唯一源，页面唯一出处）；
# 账C=账面（锚台账.json 天数据 + 付款核对_<账期>.json 逐家）
# ═══════════════════════════════════════════════════════════════════════
def _锚台账金额(家名, 账期):
    """账C·锚台账：天 列表中账期当日 锚[家名]（天=[{日期,锚:{家:金额}}...]）。"""
    try:
        d = json.load(open(os.path.join(BUILD, '锚台账.json'), encoding='utf-8'))
    except Exception:
        return None, '锚台账不可读'
    key = '2026-' + 账期[:2] + '-' + 账期[2:]
    for row in (d.get('天') or []):
        if row.get('日期') == key:
            return (row.get('锚') or {}).get(家名), '锚台账 ' + key
    return None, '锚台账无 ' + key


def _付款核对金额(家名, 账期):
    """账C·付款核对：逐家[].锚/实付。"""
    p = os.path.join(BUILD, '付款核对_%s.json' % 账期)
    if not os.path.isfile(p):
        return None, None, '付款核对_%s 缺文件' % 账期
    d = json.load(open(p, encoding='utf-8'))
    for x in d.get('逐家') or []:
        if x.get('家') == 家名:
            return x.get('锚'), x.get('实付'), '付款核对_' + str(账期)
    return None, None, '付款核对无该家'


def 三账比对(数字, 家名=None, 账期=None):
    """三账二次校验：A 搜索框原话 vs B 工作台 vs C 账面。
    不一致 → 标记「⚠ 不一致→优先取搜索框结果」（聊天原始记录=第一锚点）。"""
    if 账期 is None:
        try:
            账期 = json.load(open(os.path.join(BUILD, '数字唯一源.json'),
                                  encoding='utf-8')).get('账期')
        except Exception:
            账期 = '1111'
    A = 聊天搜索框接口(数字, 家名)
    # 账A：从强锚原话提取「<家名>…需付款： NNNN」金额
    a_amt, a_src = None, ''
    name = 家名 or ''
    for r in A['原始记录']:
        if '需付款' not in r['原文']:
            continue
        pat = (re.escape(name) if name else r'[\u4e00-\u9fa5A-Za-z]{2,6}') + \
              r'[^\d\n]{0,14}(\d+(?:\.\d+)?)'
        m = re.search(pat, r['原文'])
        if m:
            a_amt = float(m.group(1))
            a_src = r['时间'] + ' ' + r['会话'] + '｜' + r['原文']
            break
    # 账B：工作台=数字唯一源
    b = {}
    try:
        d = json.load(open(os.path.join(BUILD, '数字唯一源.json'), encoding='utf-8'))
        x = (d.get('上家') or {}).get(家名 or '', {})
        b = {'锚': x.get('锚'), '实付': x.get('实付'),
             '源': '数字唯一源.json（工作台页面唯一出处）'}
    except Exception as e:
        b = {'锚': None, '实付': None, '源': '数字唯一源不可读 %s' % e}
    # 账C：账面=锚台账+付款核对
    c1, c1src = _锚台账金额(家名 or '', 账期) if 家名 else (None, '')
    c2, c3, csrc = _付款核对金额(家名 or '', 账期) if 家名 else (None, None, '')
    v = round(float(数字), 2)
    amts = {'账A_搜索框原话': a_amt, '账B_工作台锚': b.get('锚'),
            '账C_锚台账': c1, '账C_付款核对锚': c2}
    vals = [x for x in amts.values() if x is not None]
    一致 = bool(vals) and all(abs(x - v) < 0.005 for x in vals)
    if 一致:
        mark = '✔ 三账一致（与第一锚点等值）'
    elif a_amt is None:
        mark = '⚠ 搜索框原话未提取到金额 → 不判红，走图锚核验'
    else:
        mark = '🚩 不一致 → 优先取搜索框结果（聊天原始记录=第一锚点），差异方调三脑'
    return {'数字': v, '家名': 家名 or '', '账期': 账期,
            '账A_搜索框原话': {'提取金额': a_amt, '原话': a_src,
                          '命中数': A['命中数'], '原始记录': A['原始记录']},
            '账B_工作台': b,
            '账C_账面': {'锚台账锚': c1, '锚台账源': c1src,
                      '付款核对锚': c2, '付款核对实付': c3, '源': csrc},
            '三账金额': amts, '三账一致': 一致, '标记': mark}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--账期', default=None, help='默认读数字唯一源当前账期')
    ap.add_argument('--nums', default=None, help='逗号分隔告警数字（订单告警单查场景）')
    ap.add_argument('--家', default='', help='单查时指定会话名过滤')
    ap.add_argument('--json', default=None, help='任意账目 json，提取全部金额通用校验')
    ap.add_argument('--q', default=None, help='外挂：调用聊天搜索框接口查单个金额/编号（拉带时间戳原始记录+三账比对）')
    a = ap.parse_args()

    # ── 外挂分支：--q 调聊天搜索框接口 + 三账比对（不动原有主流程）──
    if a.q:
        r = 三账比对(a.q, a.家 or None, a.账期)
        os.makedirs(OUTD, exist_ok=True)
        jp = os.path.join(OUTD, '搜索框接口_三账_%s_%s.json'
                          % (a.家 or '通用', datetime.datetime.now().strftime('%Y%m%d_%H%M%S')))
        json.dump(r, open(jp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('[搜索框接口] 查询 %s（%s）｜原话命中 %d' % (a.q, a.家 or '不限', r['账A_搜索框原话']['命中数']))
        print('  账A原话:', r['账A_搜索框原话']['原话'] or '（无强锚原话）')
        print('  账B工作台: 锚=%s 实付=%s' % (r['账B_工作台'].get('锚'), r['账B_工作台'].get('实付')))
        print('  账C账面: 锚台账=%s 付款核对锚=%s' % (r['账C_账面'].get('锚台账锚'), r['账C_账面'].get('付款核对锚')))
        print('  三账金额:', r['三账金额'])
        print('  判定:', r['标记'])
        print('[报告]', jp)
        return

    t0 = datetime.datetime.now()
    idx, meta = load_corpus()
    print('[索引] 消息 %d 条 · 数字 token %d 个 · 耗时 %s' % (len(meta), len(idx), datetime.datetime.now() - t0), flush=True)

    if a.nums:
        items = [(float(x.strip()), a.家, '锚' if a.家 else '实付') for x in a.nums.split(',') if x.strip()]
        src = '订单告警单查 ' + a.nums
        zq = a.账期 or '单查'
    elif a.json:
        j = json.load(open(a.json, encoding='utf-8'))
        seen, items = set(), []
        for v in toks(json.dumps(j, ensure_ascii=False)):
            if v not in seen:
                seen.add(v); items.append((v, '', '锚'))
        src = 'json ' + os.path.basename(a.json)
        zq = a.账期 or os.path.basename(a.json)
    else:
        items, zq = extract_unique_source()
        src = '数字唯一源.json（账期 %s）' % zq

    results = [probe(idx, meta, v, name, kind) for v, name, kind in items]
    red = [r for r in results if r['判定'] == '红']
    yellow = [r for r in results if r['判定'] == '黄']
    green = [r for r in results if r['判定'] == '绿']

    rep = {'时间': t0.strftime('%Y-%m-%d %H:%M:%S'),
           '指令': '聊天搜索框原始记录=对账第一锚点；三账二次校验；红项调三脑（顾超 21:01/21:03 令）',
           '数据源': src, '账期': zq,
           '镜像检索底座': '镜像数据/方方+吴丹 全部分片（与镜像 HTML 搜索框 normHit 同口径：正文+转账金额/备注+引用标题）',
           '标准流程': '输入金额/编号→调取带时间戳原始记录→三账比对（聊天原话 vs 工作台 vs 账面）→不一致以聊天原始记录为优先锚点→红项调三脑',
           '统计': {'校验数字数': len(results), '绿': len(green), '黄': len(yellow), '红': len(red)},
           '结果': results,
           '红项三脑决断入口': [{'数字': r['数字'], '会话': r['会话'], '理由': r['理由']} for r in red]}
    os.makedirs(OUTD, exist_ok=True)
    jp = os.path.join(OUTD, '搜索框二次校验_%s_%s.json' % (zq, t0.strftime('%Y%m%d')))
    json.dump(rep, open(jp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    print('[统计] 校验 %d 个数字｜绿 %d｜黄 %d｜红 %d' % (len(results), len(green), len(yellow), len(red)))
    for r in results:
        if r['判定'] != '绿':
            print('  [%s] %s %s %s ｜ %s ｜ 全文命中 %d' % (r['判定'], r['类型'], r['会话'], r['数字'], r['理由'], r['全文命中数']))
    print('[报告]', jp)
    if red:
        print('[红项] → 调三脑重新决断（不推进流程）')
        sys.exit(3)
    print('[结论] 全部锚点成立，可推进流程')


if __name__ == '__main__':
    main()
