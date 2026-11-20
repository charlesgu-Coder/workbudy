#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能常驻满血校验闸（顾超 2026-11-20 17:28 令 · 原子闸唯一实现）

死规则：五Agent 启动第一动作跑本闸 ——
  ① 缓存命中（技能清单已核+读库指纹与当前库一致）→ 自动就位，零问询，常驻满血，禁止二次重复问询；
  ② 指纹漂移（记忆库文件变了）→ 只报漂移差量，Agent 只补读变化部分；
  ③ 缺技能 → 输出缺口清单触发补装，装完 --mark 常驻满血。

用法：
  python 技能常驻满血校验.py --check 萃取A骨架          # 启动第一动作，exit 0 就位 / exit 1 有缺口
  python 技能常驻满血校验.py --seed 萃取A骨架 --skills "抓取:已装,分片:未装(内置替代)" --缺口 "分片"   # 首次校验后落缓存
  python 技能常驻满血校验.py --mark 萃取A骨架 --skills "抓取:已装,分片:已装" --缺口 ""                # 补装完成后常驻满血
  python 技能常驻满血校验.py --status                  # 五Agent 满血状态总览
"""
import json, os, sys, hashlib, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, '满血缓存')
LIB = {
    '错误经验本': r'D:/Obsidian/顾超记忆库/wiki/entities/05-错误经验本.md',
    '错误经验总闸': r'D:/Obsidian/顾超记忆库/开工必读_错误规避总闸.md',
    '决策与铁律': r'D:/Obsidian/顾超记忆库/wiki/concepts/01-决策与铁律.md',
    '三层硬制规则': r'D:/Obsidian/顾超记忆库/三层硬制规则_错误拦截互审.md',
}

def fp(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()[:16]

def lib_fps():
    out = {}
    for name, p in LIB.items():
        out[name] = fp(p) if os.path.exists(p) else 'MISSING'
    return out

def cache_path(agent):
    return os.path.join(CACHE_DIR, f'{agent}.json')

def load_cache(agent):
    p = cache_path(agent)
    if not os.path.exists(p):
        return None
    with open(p, encoding='utf-8') as f:
        return json.load(f)

def save_cache(agent, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_path(agent), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

def cmd_check(a):
    c = load_cache(a.agent)
    cur = lib_fps()
    if c is None:
        print(f'[缺缓存] {a.agent} 首次启动：需完成一次满血校验（技能清单+读库回执）后 --seed 落缓存')
        sys.exit(1)
    drift = {k: (c['lib_fps'].get(k), v) for k, v in cur.items() if c['lib_fps'].get(k) != v}
    missing = c.get('缺口') or []
    if c.get('状态') == '满血' and not drift and not missing:
        print(f'[常驻满血·零问询] {a.agent} 缓存命中（校验于 {c["cached_at"]}），库指纹无漂移，直接开工')
        sys.exit(0)
    if drift:
        print(f'[指纹漂移] {a.agent} 以下记忆库文件已变化，只需补读差量并 --seed 更新缓存：')
        for k, (old, new) in drift.items():
            print(f'  {k}: {old} → {new}')
    if missing:
        print(f'[缺技能] {a.agent} 缺口未补齐：{missing}，触发补装流程，装完 --mark')
    sys.exit(1)

def cmd_seed_or_mark(a):
    cur = lib_fps()
    data = {'agent': a.agent, '状态': '满血' if not (a.缺口 or '').strip() else '缺口在案',
            'skills': a.skills or '', '缺口': [x for x in (a.缺口 or '').split('|') if x.strip()],
            'lib_fps': cur, 'cached_at': datetime.datetime.now().isoformat(timespec='seconds')}
    save_cache(a.agent, data)
    tag = '常驻满血缓存已落' if data['状态'] == '满血' else '缓存已落(缺口在案)'
    print(f'[绿] {a.agent} {tag}：skills={data["skills"]} 缺口={data["缺口"] or "无"} 指纹已快照')

def cmd_status(_):
    os.makedirs(CACHE_DIR, exist_ok=True)
    cur = lib_fps()
    for fn in sorted(os.listdir(CACHE_DIR)):
        if not fn.endswith('.json'):
            continue
        c = load_cache(fn[:-5])
        drift = any(c['lib_fps'].get(k) != v for k, v in cur.items())
        tag = '常驻满血' if c.get('状态') == '满血' and not drift else ('指纹漂移需补读' if drift else '缺口在案')
        print(f"{c['agent']:<14} {tag:<10} skills={c.get('skills','')} 缺口={c.get('缺口') or '无'} @ {c['cached_at']}")
    if not os.listdir(CACHE_DIR):
        print('（缓存空，五Agent 均未落常驻满血缓存）')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check'); ap.add_argument('--seed', dest='agent')
    ap.add_argument('--mark', nargs='+', dest='mark_agents')
    ap.add_argument('--skills'); ap.add_argument('--缺口', default='')
    ap.add_argument('--status', action='store_true')
    a = ap.parse_args()
    if a.check:
        a.agent = a.check; cmd_check(a)
    elif a.mark_agents:
        for ag in a.mark_agents:
            a.agent = ag; cmd_seed_or_mark(a)
    elif a.agent:
        cmd_seed_or_mark(a)
    elif a.status:
        cmd_status(a)
    else:
        ap.print_help()

if __name__ == '__main__':
    main()
