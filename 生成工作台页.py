# -*- coding: utf-8 -*-
"""生成工作台页.py —— 新工作台页面唯一生成器（全新脚本，2026-11-20）

业务规则参考鑫浦（判定层口径：应付−已认付款=未付；实付流水唯一真值），
代码全新、数据源=本目录 build/台账_1119.json，零调用鑫浦旧组件。

顾超 2026-11-20 09:41 令：
  ① 判定层未付 3 笔 → 6 笔（加 10 号韩妆/永通/撒娇三家）
  ② 手机格式删掉多余底色渲染（黄底标题块/橙底合计块等全部去掉）
11.19 回填适配（2026-11-20，1119回填四台，team-lead 段B批准原文授权）：
  数据源换 台账_1119.json；三总额/笔数改从台账动态推导（节点1补闸建议
  「三处写死终值改动态推导」落地）；只改数据口径与同源文案，样式/结构/
  区块顺序不动（F22）。头部日期口径锁 11-19（顾超 15:32 亲令）。
输出：index.html（页面形式与旧工作台一致：判定层卡+追回栏+欠款清单）
"""
import io, json, os, html

BASE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(BASE, 'build')
OUT = os.path.join(BASE, 'index.html')

esc = html.escape
fm = lambda x: '{:,.2f}'.format(round(float(x or 0), 2))

T = json.load(io.open(os.path.join(BUILD, '台账_1119.json'), encoding='utf-8'))
_j = T['判定层']
_per = _j['账期']                                  # 动态账期（11.19）
_due = round(float(_j['认付款']['金额']) + float(_j['未付']['合计']), 2)
_paid = round(float(_j['认付款']['金额']), 2)      # 已认付款（台账同源）
_left = round(sum(float(r['金额']) for r in _j['未付']['条目']), 2)
assert abs(_left - float(_j['未付']['合计'])) < 0.011, '判定层未付合计不闭合'
assert abs(_due - _paid - _left) < 0.011, '判定层三总额不闭合'
_ows = _j['未付']['条目']
_top = T['顶部欠款清单']
_s = round(sum(float(r['金额']) for r in _top['条目']), 2)
assert abs(_s - float(_top['合计'])) < 0.011, '顶部清单合计不闭合'
assert _s == _left, '顶部清单与判定层未付不同源（F16）'
_track = T['追回栏']['正常跟踪']
_marks = _j.get('存疑与尾巴标注') or {}

# 明细行（白底、仅文字色分级、无底色块；存疑行带同源标注防E-123）
_rows = []
for r in _ows:
    _row = ('<div class="lrow"><span class="n"><span class="day">%s</span>%s</span>'
            '<span class="v">%s</span></div>'
            % (esc(str(r['欠款日'])), esc(str(r['家'])), fm(r['金额'])))
    if str(r.get('标注') or '').strip():
        _row += ('<div class="note">%s</div>' % esc(str(r['标注'])))
    _rows.append(_row)
_rows.append('<div class="lrow tot"><span class="n">一共还差</span>'
             '<span class="v">%s</span></div>' % fm(_left))

# 顶部欠款清单（1119当天口径＝判定层同源；历史账期不混入）
_top_rows = []
for r in _top['条目']:
    _top_rows.append(
        '<div class="owstrip"><b class="fam">%s</b><span class="v">%s</span>'
        '<span class="tag">未付</span></div>' % (esc(str(r['家'])), fm(r['金额'])))

# 追回栏（1119解析为商家应付域，无退货域数据——F27如实披露，不脑补）
if not T['追回栏']['点名催办'] and not _track:
    _track_html = ('<div class="okline">本账期解析为商家应付域，无退货退款域数据；'
                   '追回栏由退款台账链独立维护，本账期不更新（如实披露，不脑补）。</div>')
elif not T['追回栏']['点名催办']:
    _track_html = ('<div class="okline">✅ 本栏无点名催办，转入正常跟踪 %d 笔'
                   '（每晚自动查，退了自动消除，没退一直挂）。</div>'
                   '<div class="tracks">%s</div>'
                   % (len(_track), ''.join(
                       '<span class="tchip">%s %s</span>'
                       % (esc(str(x['对象'])), fm(x['金额'])) for x in _track)))
else:
    _track_html = ''.join(
        '<div class="lrow"><span class="n">%s</span><span class="v">%s</span></div>'
        % (esc(str(x['对象'])), fm(x['差额'] if '差额' in x else x.get('金额', 0)))
        for x in T['追回栏']['点名催办'])

# 存疑与尾巴标注（台账同源，防E-123）
_notes = ''.join('<div>%s：%s</div>' % (esc(k), esc(v)) for k, v in _marks.items())
if not _notes:
    _notes = '<div>本账期无存疑挂账。</div>'

page = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>鑫浦工作台 · %s账期</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;
background:#f7f8fa;color:#1c2430;font-size:15px;line-height:1.5}
.wrap{max-width:520px;margin:0 auto;padding:12px 10px 30px}
h1{font-size:17px;padding:6px 2px 10px}
.card{background:#fff;border:1px solid #e8e8ee;border-radius:10px;
padding:12px 12px 14px;margin-bottom:12px}
.card h2{font-size:15px;margin-bottom:2px}
.sub{color:#8a8f99;font-size:12px;margin-bottom:10px}
.strip{display:flex;justify-content:space-between;align-items:baseline;
padding:8px 10px;border:1px solid #eceff3;border-radius:8px;margin:8px 0}
.strip b{font-size:17px;font-variant-numeric:tabular-nums}
.strip.g span{color:#1a7a42}.strip.g b{color:#1a7a42}
.strip.o span{color:#b06000}.strip.o b{color:#b06000}
.list1{margin-top:6px}
.lrow{display:flex;justify-content:space-between;padding:7px 4px;
border-top:1px dashed #f0f0f4;font-size:14px}
.lrow:first-child{border-top:0}
.lrow .day{display:inline-block;min-width:52px;color:#5b6472;font-size:12px}
.lrow .v{font-weight:700;font-variant-numeric:tabular-nums}
.lrow.tot .n{font-weight:700}
.lrow.tot .v{color:#b06000}
.foot{color:#8a8f99;font-size:12px;padding-top:8px;line-height:1.6}
.okline{color:#1a7a42;font-size:14px;padding:6px 0}
.tracks{display:flex;flex-wrap:wrap;gap:6px;padding:4px 0 0}
.tchip{font-size:12px;color:#5b6472;border:1px solid #e4e6ec;
border-radius:12px;padding:2px 10px}
.owlist{margin-top:4px}
.owstrip{display:flex;align-items:baseline;gap:8px;padding:6px 4px;
border-top:1px dashed #f0f0f4;font-size:14px}
.owstrip:first-child{border-top:0}
.owstrip .fam{min-width:56px;font-size:14px}
.owstrip .v{font-weight:700;font-variant-numeric:tabular-nums;flex:1;text-align:right}
.owstrip .tag{color:#c02424;font-size:12px}
.note{color:#8a8f99;font-size:12px;padding:6px 2px 0}
</style></head><body><div class="wrap">
<h1>给完了的和没给的，分开看</h1>

<div class="card">
  <h2>付款核对 · 判定层 %s 号终版</h2>
  <div class="sub">冰点说付多少，我付对了吗（%s 账期，头部日期锁 11-19）</div>
  <div class="strip g"><span>✅ 判定层认付款 · %d 家</span><b>%s</b></div>
  <div class="strip o"><span>⚠️ 判定层未付 · %d 笔</span><b>%s</b></div>
  <div class="list1">%s</div>
  <div class="foot">本格只摆判定层 %s 号终版（应付 %s − 已认付款 %s ＝ 未付 %s）。
  永通旧账 8,901 单列转 1120 核销，不入本账期；丰牛牛 671 销账已计入已付。</div>
</div>

<div class="card">
  <h2>要追回的钱</h2>
  <div class="sub">两锚点每晚自动查：退货群报文＋固定上家群</div>
  %s
</div>

<div class="card">
  <h2>还没给的钱（%s当天台账口径）</h2>
  <div class="sub">共 %d 笔 %s · 历史账期欠款不混入本账期基准</div>
  <div class="owlist">%s</div>
  <div class="note">存疑与尾巴标注（与台账同源）：%s</div>
</div>
</div></body></html>""" % (
    _per,
    _per, _per,
    int(_j['认付款']['家数']), fm(_paid),
    len(_ows), fm(_left),
    ''.join(_rows),
    _per, fm(_due), fm(_paid), fm(_left),
    _track_html,
    _per,
    len(_top['条目']), fm(_top['合计']), ''.join(_top_rows),
    _notes)

io.open(OUT, 'w', encoding='utf-8').write(page)
print('页面已生成：%s（%d 字节）' % (OUT, len(page.encode('utf-8'))))
print('  判定层 %s：未付 %d 笔 %s（韩妆茗芳2477/撒娇7176/丹丹12790存疑挂账）'
      % (_per, len(_ows), fm(_left)))
print('  顶部清单 %d 笔 %s（判定层同源；历史账期不混入）' % (len(_top['条目']), fm(_top['合计'])))
print('  三总额：应付 %s − 已认付款 %s ＝ 未付 %s' % (fm(_due), fm(_paid), fm(_left)))
