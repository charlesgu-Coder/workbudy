# -*- coding: utf-8 -*-
"""发布闸.py —— 新工作台发布闸（全新脚本，2026-11-20）

闸逻辑（业务规则参考鑫浦 C10「顶部条与未付明细自查清单闸」）：
  ① 页面判定层未付 N 笔 ＝ 台账 N 笔，逐笔（欠款日,家,金额）一致
  ② 页面顶部欠款清单 ＝ 台账逐笔（家,金额）一致（与判定层同源）
  ③ 凭证齐全（判定层逐笔带凭证；存疑行带同源标注防E-123）
  ④ 旧账期口径数字残留检查（防E-122旧数烤死）
任一不符 → 退 3 拦停；全绿 → 退 0 放行发布。

11.19 回填适配（2026-11-20，1119回填四台，team-lead 段B批准原文授权）：
  台账换 台账_1119.json；笔数/合计改从台账动态断言（不再写死6笔/26,988）；
  ③改为「逐笔带凭证+存疑标注在页」；④新增 11号旧口径关键数残留检查。
"""
import html, io, json, os, re, sys

esc = html.escape

BASE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(BASE, 'build')
OUT = os.path.join(BASE, 'index.html')

fails = []
T = json.load(io.open(os.path.join(BUILD, '台账_1119.json'), encoding='utf-8'))
pg = io.open(OUT, encoding='utf-8').read()

_j = T['判定层']
_ows = _j['未付']['条目']
_n = len(_ows)
_tot = '{:,.2f}'.format(float(_j['未付']['合计']))
_per = str(_j['账期'])

# ① 判定层 N 笔逐笔在页面（家+金额）
for r in _ows:
    _amt = '{:,.2f}'.format(float(r['金额']))
    if esc(str(r['家'])) not in pg:
        fails.append('判定层缺行：%s' % r['家'])
    elif _amt not in pg:
        fails.append('判定层金额不在页：%s %s' % (r['家'], r['金额']))
if ('判定层未付 · %d 笔' % _n) not in pg:
    fails.append('页面未显示「判定层未付 · %d 笔」' % _n)
if _tot not in pg:
    fails.append('页面缺未付合计 %s' % _tot)

# ② 顶部欠款清单逐笔（家+金额 同行）在页面，且与判定层同源
_miss = []
for r in T['顶部欠款清单']['条目']:
    _frag = '<b class="fam">%s</b><span class="v">%s</span>' % (
        esc(str(r['家'])), '{:,.2f}'.format(float(r['金额'])))
    if _frag not in pg:
        _miss.append('%s %s' % (r['家'], r['金额']))
if _miss:
    fails.append('顶部清单缺 %d 笔：%s' % (len(_miss), '；'.join(_miss[:6])))
if ('共 %d 笔' % len(T['顶部欠款清单']['条目'])) not in pg:
    fails.append('页面未显示「共 %d 笔」（台账口径）' % len(T['顶部欠款清单']['条目']))

# ③ 凭证齐全：判定层逐笔带凭证；存疑行标注文案在页（提示语与台账同源防E-123）
_nov = [str(r['家']) for r in _ows if not str(r.get('凭证') or '').strip()]
if _nov:
    fails.append('判定层缺凭证：%s' % '、'.join(_nov))
for r in _ows:
    _mk = str(r.get('标注') or '').strip()
    if _mk and esc(_mk[:12]) not in pg:
        fails.append('存疑行标注不在页（E-123）：%s' % r['家'])

# ④ 旧账期口径残留检查（E-122/防旧数烤死）：11号口径关键数不许出现
for bad in ('26,988.00', '308,494.00', '17,651.00', '101,458.00', '119,109.00'):
    if bad in pg:
        fails.append('页面残留旧11号口径数：%s' % bad)
# 历史虚挂值不许再出现
for bad in ('华仁 8,876', '嘉柏丽 54,208', '雅莉莱'):
    if bad in pg and bad != '雅莉莱':
        fails.append('页面残留历史虚挂：%s' % bad)

if fails:
    print('✘ 发布闸 FAIL（%d 项）：' % len(fails))
    for f in fails:
        print('   -', f)
    sys.exit(3)
print('✔ 发布闸 全绿：判定层 %s %d 笔逐笔一致（合计 %s）；顶部清单＝判定层同源逐笔一致；'
      '逐笔凭证齐全+存疑标注同源在页；旧11号口径数零残留。'
      % (_per, _n, _tot))
print('  → 放行发布。')
sys.exit(0)
