#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""历史错误复现扫描闸（顾超 2026-11-20 17:26 三层硬制规则 · 原子闸唯一实现）

层1 已知错误拦截钩子：错误特征码库.json 里每条已知错误绑定特征+处置方案；
    扫描命中=触发钩子暂停，必须按处置方案匹配放行（--release 留痕）。
层2 产物复现扫描：--scan 对产物全量跑历史错误复现扫描，扫到旧错 exit 1 直接打回。
层3 新错绑码：新错误入库必须 --register 绑定唯一特征码，下次特征匹配直接拦截。

用法：
  python 历史错误复现扫描.py --scan <产物文件...>            # 层2 主用法，exit 0 绿 / exit 1 红
  python 历史错误复现扫描.py --register --code XC-XX --ref E-1xx --kind json|text --check dup_tid|neg_unpaid|int_multiple|paid_no_evid|regex --patterns "r1|r2" --处置 "方案原文"
  python 历史错误复现扫描.py --list
  python 历史错误复现扫描.py --self-test
"""
import json, re, sys, os, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REG_PATH = os.path.join(HERE, '错误特征码库.json')

def load_reg():
    if not os.path.exists(REG_PATH):
        return {"version": 1, "entries": [], "hits_log": []}
    with open(REG_PATH, encoding='utf-8') as f:
        return json.load(f)

def save_reg(reg):
    with open(REG_PATH, 'w', encoding='utf-8') as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)

def walk_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_dicts(v)

def num(v):
    try:
        return float(str(v).replace(',', '').replace('¥', '').strip())
    except Exception:
        return None

# ---------- 内置 JSON 检查（层3 可登记扩展） ----------
def json_checks(reg, obj, src, hits):
    paid_tids = {}
    for d in walk_dicts(obj):
        due = num(d.get('应付')); paid = num(d.get('已付') if '已付' in d else d.get('实付'))
        unp = num(d.get('未付'))
        if unp is not None and unp < 0:
            hits.append(('XC-NEG-UNPAID', 'E-120红灯族', src, f'负未付: {d.get("商家", d)}', '负未付必查到底，找到错闭环五步处置后才许放行'))
        if due and paid and due > 0 and paid >= due * 2 and abs(paid % due) < 0.005:
            hits.append(('XC-INT-MULT', 'E-120红灯族', src, f'实付=应付整数倍: {d.get("商家", d)} 应付{due} 实付{paid}', '按E-120红灯查同图两线翻倍，处置匹配后才放行'))
        st = str(d.get('状态', '') or d.get('判定', ''))
        tid = str(d.get('转账号', '') or d.get('tid', '') or d.get('transferid', '') or '')
        has_evid = any(d.get(k) for k in ('图证键', '图证', '锚', '锚原话', '关键锚', '关键锚原话', '原话锚', '依据'))
        if tid and ('付清' in st or '已付' in st):
            if tid in paid_tids and paid_tids[tid] is not d:
                hits.append(('XC-E120-DUP-TID', 'E-120', src, f'同转账号两处计已付: {tid}', '同笔去重，按转账号唯一键合并，处置后才放行'))
            else:
                paid_tids[tid] = d
        if ('付清' in st or '已付' in st) and (paid or 0) > 0 and not has_evid:
            hits.append(('XC-E126-NOEVID', 'E-126', src, f'付清无图证/锚: {d.get("商家", d)}', '链尾同额图判付清需image_evidence两字段，补证后才放行'))
        if '未付' in st and (unp or 0) > 0 and not has_evid:
            hits.append(('XC-E130-NOANCHOR', 'E-130', src, f'未付判定无锚原话: {d.get("商家", d)}', '判定必附搜证三要素，补搜证后才放行'))

# ---------- 登记式文本 regex 检查 ----------
def text_checks(reg, text, src, hits):
    for e in reg['entries']:
        if e.get('kind') != 'text':
            continue
        for p in e.get('patterns', []):
            try:
                rx = re.compile(p)
            except re.error as ex:
                # 闸门自身缺陷≠绿：非法pattern必须显式报错熔断，禁止静默跳过
                print(f'[闸门异常·熔断] 特征码 {e["code"]} 存在非法正则 {p!r}: {ex}')
                print('  闸门自身缺陷按红处置：请 --register 重登记该特征码（多pattern用 || 分隔），修复后复扫')
                sys.exit(2)
            m = rx.search(text)
            if m:
                # E-128 附加条件：附近无「原话/「」引用」不豁免
                if e['code'] == 'XC-E128-FAKE-AUTH':
                    ctx = text[max(0, m.start()-120):m.end()+120]
                    if '原话' in ctx or '「' in ctx:
                        continue
                hits.append((e['code'], e.get('ref', ''), src, f'命中特征 {p} 上下文: {text[max(0,m.start()-40):m.end()+40]!r}', e.get('处置', '')))
                break

def cmd_scan(args):
    reg = load_reg()
    hits = []
    for f in args.files:
        if not os.path.exists(f):
            print(f'[跳过] 文件不存在: {f}'); continue
        with open(f, encoding='utf-8', errors='replace') as fh:
            content = fh.read()
        if f.lower().endswith('.json'):
            try:
                json_checks(reg, json.loads(content), f, hits)
            except Exception as ex:
                print(f'[警告] JSON 解析失败 {f}: {ex}，仅跑文本特征')
                text_checks(reg, content, f, hits)
        else:
            text_checks(reg, content, f, hits)
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if hits:
        print(f'== 复现扫描 红 · {ts} · 命中 {len(hits)} 条（触发层1拦截钩子，暂停放行）==')
        for i, (code, ref, src, desc, plan) in enumerate(hits, 1):
            print(f'  [{i}] {code} (ref {ref}) @ {os.path.basename(src)}\n      {desc}\n      处置方案: {plan}')
        reg['hits_log'].append({'ts': ts, 'files': args.files, 'hits': [h[0] for h in hits]})
        save_reg(reg)
        print('== 放行条件：逐条匹配上述处置方案并 --release 留痕，未处置不得进入下游 ==')
        sys.exit(1)
    print(f'== 复现扫描 绿 · {ts} · 扫描 {len(args.files)} 个产物 · 已知错误特征 0 命中 ==')
    sys.exit(0)

def cmd_register(args):
    reg = load_reg()
    if any(e['code'] == args.code for e in reg['entries']):
        print(f'[红] 特征码 {args.code} 已存在，唯一性冲突（层3：一个错误一个唯一码）'); sys.exit(1)
    entry = {'code': args.code, 'ref': args.ref, 'kind': args.kind, 'check': args.check,
             # 多pattern用 || 分隔；单pattern内部可安全含 | 正则元字符（修复：旧版按 | 拆分吃掉元字符）
             'patterns': [p for p in (args.patterns or '').split('||') if p],
             '处置': args.处置, 'registered_at': datetime.datetime.now().isoformat(timespec='seconds')}
    for p in entry['patterns']:
        try:
            re.compile(p)
        except re.error as ex:
            print(f'[红] pattern {p!r} 是非法正则: {ex} —— 拒绝入库（防静默恒绿）'); sys.exit(1)
    reg['entries'].append(entry); save_reg(reg)
    print(f'[绿] 特征码 {args.code} 已入库绑定 {args.ref}，下次特征匹配直接拦截')

def cmd_release(args):
    if not args.hit or not args.plan:
        print('[红] --release 必须附 --hit 命中描述 与 --plan 处置方案，拒绝空白留痕'); sys.exit(1)
    reg = load_reg()
    rec = {'ts': datetime.datetime.now().isoformat(timespec='seconds'), 'hit': args.hit, 'plan': args.plan,
           'released_by': args.by}
    reg.setdefault('releases', []).append(rec); save_reg(reg)
    print(f'[绿] 放行留痕：{args.hit} 处置={args.plan}（层1 放行条件已满足留档）')

def cmd_self_test():
    fixture_bad = os.path.join(HERE, '_自测_坏产物.json')
    fixture_good = os.path.join(HERE, '_自测_好产物.json')
    with open(fixture_bad, 'w', encoding='utf-8') as f:
        json.dump({'台账': [{'商家': '测试甲', '应付': 100, '已付': 200, '未付': -100, '状态': '付清'},
                            {'商家': '测试乙', '应付': 50, '已付': 50, '未付': 0, '状态': '付清', '图证键': 'md5xx', '锚': '原话'}]}, f, ensure_ascii=False)
    with open(fixture_good, 'w', encoding='utf-8') as f:
        json.dump({'台账': [{'商家': '测试丙', '应付': 100, '已付': 40, '未付': 60, '状态': '未付', '锚': '原话xx'}]}, f, ensure_ascii=False)
    ok = True
    for fx, expect_red in ((fixture_bad, True), (fixture_good, False)):
        p = os.path.join(HERE, '历史错误复现扫描.py')
        rc = os.system(f'{sys.executable} "{p}" --scan "{fx}" >nul 2>&1' if os.name == 'nt' else f'{sys.executable} "{p}" --scan "{fx}" >/dev/null 2>&1')
        red = (rc != 0)
        tag = '红' if red else '绿'
        want = '红' if expect_red else '绿'
        good = red == expect_red
        ok = ok and good
        print(f'  自测 {os.path.basename(fx)}: 实测{tag} 预期{want} {"✅" if good else "❌"}')
    os.remove(fixture_bad); os.remove(fixture_good)
    print('自测结论：', '闸门能红能绿 ✅' if ok else '闸门异常 ❌ 禁用')
    sys.exit(0 if ok else 1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scan', nargs='+', dest='files')
    ap.add_argument('--register', action='store_true')
    ap.add_argument('--release', action='store_true')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--code'); ap.add_argument('--ref'); ap.add_argument('--kind', default='text')
    ap.add_argument('--check', default='regex'); ap.add_argument('--patterns'); ap.add_argument('--处置')
    ap.add_argument('--hit'); ap.add_argument('--plan'); ap.add_argument('--by', default='主控')
    a = ap.parse_args()
    if a.self_test: cmd_self_test()
    if a.files: cmd_scan(a)
    if a.register: cmd_register(a); return
    if a.release: cmd_release(a); return
    if a.list:
        reg = load_reg()
        for e in reg['entries']:
            print(f"{e['code']}  ref={e.get('ref')}  kind={e['kind']}  check={e.get('check')}  处置={e.get('处置','')[:40]}")
        print(f"共 {len(reg['entries'])} 条特征码")
        return
    ap.print_help()

if __name__ == '__main__':
    main()
