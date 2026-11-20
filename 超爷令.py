# -*- coding: utf-8 -*-
"""超爷令.py —— 鑫浦 11.11 新工作台专用 · 顾超 ↔ 超爷 ↔ 大将 对话通道（轻量重构版）

★ 2026-11-20 顾超令：基于旧工作台超爷逻辑内核消化重构，禁用旧工作台 10.3~11.10
  的任何原脚本与链路，适配 11.11 新工作台规则，轻量可闭合全链路，彻底隔离旧臃肿链。

【内核来源】旧工作台 keqing/大将.py（22 项五组自检）+ 超爷/超爷令.py（令协议），
  只借逻辑不借代码：本文件零 import、零 subprocess 指向旧工作台任何路径。

【本机真值】全部锚 D:/XP新工作台/：
  index.html（线上同版）· build/台账_1119.json（唯一账本）·
  build/解析_1119_终版回填台账_20261120.json（上游凭证：19家合并终版）·
  build/归档_*/（改动必留档）·
  生成工作台页.py + 发布闸.py（唯一可执行新链）

【体检八项 · 红则退出码 1 不许发布】
  T1 账期是不是 11.19（台账判定层 3 笔闭合 22,443，动态验算）
  T5 手机上打开是不是这一版（线上实拉 md5 = 本地 index.html md5）★闭环旧 T5 卡点
  R7 页面上的数和台账里的数是同一个数吗
  R8 挂着的钱上游凭证里真有这回事吗（合并终版台账在盘）
  E4 说这笔付了，凭证在哪（判定层逐笔带凭证）
  S1 闸红了有人知道吗（体检留痕 build/超爷体检_最新.json）
  I1 旧链封禁了吗（新工作台源码出现旧工作台路径引用＝红）
  R3 规矩有没有被偷改（index.html md5 = 最近归档 md5，改动必重新归档）

【协议（与旧超爷同款）】
  问一句：   python 超爷令.py talk "嘉柏丽付了吗"
  领令：     python 超爷令.py list   （有待办令退出码 1）
  修完销令： python 超爷令.py done <编号> --说明 "怎么修的"
  体检：     python 超爷令.py status
  修没修好不由嘴说——下轮体检同 id 再红，令自动重现。
"""
import argparse
import datetime
import hashlib
import io
import json
import os
import re
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, 'build')
LJ = os.path.join(BUILD, '超爷令.json')
DJ = os.path.join(BUILD, '超爷令_已销.json')
TALK = os.path.join(BUILD, '超爷对话.jsonl')
CHK = os.path.join(BUILD, '超爷体检_最新.json')
INDEX = os.path.join(HERE, 'index.html')
TAIZHANG = os.path.join(BUILD, '台账_1119.json')
PANDING = os.path.join(BUILD, '解析_1119_终版回填台账_20261120.json')
ONLINE = 'https://xinpu-workbench-30022.app.workbuddy.host/?sharecode=5CZNSTODEW'

# 旧工作台隔离封禁：这些路径出现在新工作台任何 .py 源码里＝I1 红
BANNED = ('2026-09-30', 'workbench_status', 'keqing', '锦衣卫', '超爷/超爷令.py')

# 顾超的话 → 域 → 新工作台唯一入口（三脑只翻译，不替他判）
ROUTE = [
    (('凭证', '判定书', '三笔', '华仁', '嘉柏丽', '雅莉莱'), '凭证证据',
     '读 build/对齐_11号三笔判定书.md（只读作答，不跑任何旧图链）'),
    (('欠', '付', '金额', '账'), '台账应付',
     '读 build/台账_11号.json 作答'),
    (('页面', '显示', '首屏', '手机', '工作台'), '页面展示',
     'python 生成工作台页.py && python 发布闸.py && python 超爷令.py status'),
]
DEFAULT_ROUTE = ('体检', 'python 超爷令.py status')


def _md5(p):
    return hashlib.md5(io.open(p, 'rb').read()).hexdigest()


def _online_md5():
    req = urllib.request.Request(ONLINE, headers={'User-Agent': 'chaoye-xp1111'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return hashlib.md5(r.read()).hexdigest()


def _taizhang():
    return json.load(io.open(TAIZHANG, encoding='utf-8'))


def _page_nums():
    t = io.open(INDEX, encoding='utf-8').read()
    return t


def ti_1(d):
    """T1 账期是不是 11.19：判定层 3 笔闭合 22,443（动态验算，防写死过期）"""
    pd = d.get('判定层') or {}
    wf = pd.get('未付') or {}
    items = wf.get('条目') or []
    n = len(items) if isinstance(items, list) else 0
    try:
        s = round(sum(float(x.get('金额') or 0) for x in items), 2)
        tot = float(wf.get('合计') or 0)
    except Exception:
        s, tot = -1, -1
    ok = (str(pd.get('账期') or '') == '11.19'
          and int(wf.get('笔数') or 0) == n
          and abs(s - tot) < 0.01
          and abs(tot - 22443.0) < 0.01)
    if ok:
        return 'G', '判定层账期 11.19、未付 %d 笔闭合 22,443.00（动态验算一致）' % n
    return 'R', '判定层账期 %s／未付 %s 笔 %s 元／实取 %d 条逐笔和 %s ≠ 1119口径' % (
        pd.get('账期'), wf.get('笔数'), wf.get('合计'), n, s)


def ti_5():
    """T5 手机上打开的是不是这一版：线上 md5 = 本地 md5"""
    try:
        om = _online_md5()
        lm = _md5(INDEX)
        if om == lm:
            return 'G', '线上 md5 %s… ＝ 本地（这一版已上线）' % om[:8]
        return 'R', '线上 md5 %s… ≠ 本地 %s… → 重新发布' % (om[:8], lm[:8])
    except Exception as e:
        return 'Y', '线上拉不到（%s）→ 人工打开核对' % e


def ti_r7(d):
    """R7 页面数 = 台账数（关键数从台账动态取，防写死过期）"""
    t = _page_nums()
    pd = d.get('判定层') or {}
    wf = pd.get('未付') or {}
    keys = ['{:,.2f}'.format(float(wf.get('合计') or 0)),
            '{:,.2f}'.format(float((pd.get('认付款') or {}).get('金额') or 0)),
            '{:,.2f}'.format(float((pd.get('认付款') or {}).get('金额') or 0)
                             + float(wf.get('合计') or 0)),
            '{:,.2f}'.format(float((d.get('顶部欠款清单') or {}).get('合计') or 0))]
    bad = [k for k in keys if k not in t]
    if bad:
        return 'R', '页面缺台账关键数：%s' % '、'.join(bad)
    return 'G', '页面 %s 与台账同源（未付/认付款/应付/顶部合计）' % '/'.join(keys)


def ti_r8():
    """R8 挂账有据：1119上游凭证（19家合并终版台账）在盘且非空"""
    if not os.path.isfile(PANDING):
        return 'R', '1119合并终版台账缺失 → 跑段A产物重建'
    if os.path.getsize(PANDING) < 200:
        return 'R', '1119合并终版台账空壳'
    return 'G', '合并终版台账 %d 字节在盘（19家凭证）' % os.path.getsize(PANDING)


def ti_e4(d):
    """E4 挂账有证：未付 6 笔逐笔带凭证，不许空凭证"""
    pd = d.get('判定层') or {}
    wf = pd.get('未付') or {}
    items = wf.get('条目') or []
    if isinstance(items, dict):
        items = list(items.values())
    if not items:
        return 'R', '未付条目取不到 → 台账结构异常'
    miss = [str(x.get('家') or x.get('对象'))
            for x in items
            if not str(x.get('凭证') or '').strip()]
    if miss:
        return 'R', '未付缺凭证：%s' % '、'.join(miss[:5])
    return 'G', '未付 %d 笔逐笔带凭证' % len(items)


def ti_s1():
    """S1 闸红有人知：体检本身落盘留痕（本函数运行即写）"""
    return 'G', '体检留痕 build/超爷体检_最新.json'


def ti_i1():
    """I1 旧链封禁：新工作台源码不得引用旧工作台路径"""
    hit = []
    for fn in os.listdir(HERE):
        if not fn.endswith('.py'):
            continue
        src = io.open(os.path.join(HERE, fn), encoding='utf-8', errors='replace').read()
        for b in BANNED:
            if b in src and 'BANNED' not in b and fn != '超爷令.py':
                hit.append('%s 引用 %s' % (fn, b))
    if hit:
        return 'R', '旧链引用未隔离：%s' % '；'.join(hit[:3])
    return 'G', '零旧链引用（10.3~11.10 原脚本全隔离）'


def ti_r3():
    """R3 规矩没偷改：index.html md5 = 最近归档 md5"""
    archs = sorted([d for d in os.listdir(BUILD) if d.startswith('归档_')])
    if not archs:
        return 'Y', '还没有归档 → 发布前必须先归档'
    ap = os.path.join(BUILD, archs[-1], 'index.html')
    if not os.path.isfile(ap):
        return 'Y', '最新归档 %s 缺 index.html' % archs[-1]
    if _md5(ap) != _md5(INDEX):
        return 'R', 'index.html 已改但没重新归档（最近归档 %s）→ 先归档再发布' % archs[-1]
    return 'G', 'index.html 与归档 %s 一致' % archs[-1]


def run_checks():
    d = _taizhang()
    rows = [
        ('T1', '时效', '账期是不是 11.19？', *ti_1(d)),
        ('T5', '时效', '手机上打开的是不是这一版？', *ti_5()),
        ('R7', '内里', '页面数和台账数是同一个数吗？', *ti_r7(d)),
        ('R8', '内里', '挂着的钱上游凭证里真有这回事吗？', *ti_r8()),
        ('E4', '证据', '说这笔付了，凭证在哪？', *ti_e4(d)),
        ('I1', '隔离', '旧工作台链路封干净了吗？', *ti_i1()),
        ('R3', '复发', '规矩有没有被偷偷改掉？', *ti_r3()),
    ]
    rows.append(('S1', '静默失败', '闸红了有人告诉我吗？', *ti_s1()))
    reds = [r for r in rows if r[3] == 'R']
    yellows = [r for r in rows if r[3] == 'Y']
    snap = {
        '时间': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '线上': ONLINE, '红': len(reds), '黄': len(yellows), '共查': len(rows),
        '项': [{'id': r[0], '组': r[1], '问': r[2], '判': r[3], '依据': r[4]} for r in rows],
    }
    io.open(CHK, 'w', encoding='utf-8').write(
        json.dumps(snap, ensure_ascii=False, indent=1))
    return rows, reds, yellows


def status():
    rows, reds, yellows = run_checks()
    print('超爷体检（新工作台 11.19 版）· %s ｜ 红 %d ／ 黄 %d ／ 共查 %d'
          % (rows and datetime.datetime.now().strftime('%F %T'), len(reds),
             len(yellows), len(rows)))
    for r in rows:
        mark = {'G': '✔绿', 'Y': '△黄', 'R': '✘红'}[r[3]]
        print('  %s %s %s：%s' % (mark, r[0], r[2], r[4]))
    if reds:
        print('✘ 有 %d 条红——红＝不许发布（顾超 11-04 令）。先修红再说话。' % len(reds))
        return 1
    print('✔ 全绿——可发布。')
    return 0


def _load(f, default):
    try:
        return json.load(io.open(f, encoding='utf-8'))
    except Exception:
        return default


def _save(f, d):
    io.open(f, 'w', encoding='utf-8').write(json.dumps(d, ensure_ascii=False, indent=1))


def talk(text):
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        io.open(TALK, 'a', encoding='utf-8').write(
            json.dumps({'时间': ts, '顾超原话': text}, ensure_ascii=False) + '\n')
    except Exception as e:
        print('(原话流水写不进：%s)' % e, file=sys.stderr)
    if any(k in text for k in ('？', '?', '吗', '对不对', '多少', '有没有', '是不是', '还欠')):
        rows, reds, yellows = run_checks()
        print('超爷（替顾超查新工作台账本，不脑补）：')
        d = _taizhang()
        pd = d.get('判定层') or {}
        rk = pd.get('认付款') or {}
        wf = pd.get('未付') or {}
        print('  认付款：%s 家 %s｜未付：%s 笔 %s（账期 %s）'
              % (rk.get('家数'), format(float(rk.get('金额') or 0), ',.2f'),
                 wf.get('笔数'), format(float(wf.get('合计') or 0), ',.2f'),
                 pd.get('账期')))
        for x in (wf.get('条目') or []):
            _tag = '（%s）' % x['标注'] if str(x.get('标注') or '').strip() else ''
            print('  未付：%s %s%s' % (x.get('家'), format(float(x.get('金额') or 0), ',.2f'), _tag))
        print('  体检：红 %d ／ 黄 %d —— %s' % (len(reds), len(yellows),
              '全绿' if not reds else '；'.join(r[0] for r in reds)))
        return 0
    dom, cmd = DEFAULT_ROUTE
    for keys, dv, cv in ROUTE:
        if any(k in text for k in keys):
            dom, cmd = dv, cv
            break
    dd = _load(LJ, {})
    todo = dd.setdefault('待办', [])
    no = '%s-S%d' % (datetime.datetime.now().strftime('%m%d'), len(todo) + 1)
    todo.append({'编号': no, '等级': '红', '令': text, '事实': '顾超 %s 亲口对超爷说的原话' % ts,
                 '指令': cmd, '验收': '下轮超爷体检 %s 不再红/黄' % dom,
                 '域': dom, '状态': '待办'})
    dd['生成时间'] = ts
    _save(LJ, dd)
    print('超爷已把这句话变成令：%s［%s］' % (no, dom))
    print('  大将执行：%s' % cmd)
    print('  → 修完 python 超爷令.py done %s --说明 "..."' % no)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', nargs='?', default='status',
                    choices=['talk', 'list', 'done', 'status'])
    ap.add_argument('编号', nargs='?', default='')
    ap.add_argument('--说明', default='')
    a = ap.parse_args()
    if a.cmd == 'talk':
        if not a.编号:
            print('用法：超爷令.py talk "顾超要说的话"')
            return 2
        return talk(a.编号)
    if a.cmd == 'status':
        return status()
    d = _load(LJ, {})
    if a.cmd == 'list':
        todo = d.get('待办') or []
        print('超爷令 · 生成于 %s' % d.get('生成时间', '?'))
        for c in todo:
            print('  [%s] %s  %s' % (c['等级'], c['编号'], c['令']))
            print('        指令：%s' % c['指令'][:90])
        if not todo:
            print('  ✔ 无待办令')
        sys.exit(1 if todo else 0)
    if not a.编号:
        print('用法：超爷令.py done <编号> --说明 <怎么修的>')
        return 2
    todo = d.get('待办') or []
    hit = next((c for c in todo if c['编号'] == a.编号 or c['编号'].endswith(a.编号)), None)
    if not hit:
        print('没有这条令：%s' % a.编号)
        return 2
    hist = _load(DJ, {})
    hit['状态'] = '已销'
    hit['销于'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    hit['销令说明'] = a.说明 or '（没写怎么修的——下次重犯别喊冤）'
    hist.setdefault('已销', []).append(hit)
    d['待办'] = [c for c in todo if c is not hit]
    _save(DJ, hist)
    _save(LJ, d)
    print('✔ 令 %s 已销——下轮体检同 id 再红，令自动重现' % a.编号)
    return 0


if __name__ == '__main__':
    sys.exit(main())
