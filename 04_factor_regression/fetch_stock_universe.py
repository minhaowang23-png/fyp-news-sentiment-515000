# -*- coding: utf-8 -*-
"""拉取全部 A 股（代码+名称+行业+总市值），保存本地，并打印行业分布"""
import json, urllib.request, csv
from collections import Counter

PROXY = urllib.request.ProxyHandler({})
opener = urllib.request.build_opener(PROXY)
opener.addheaders = [('User-Agent', 'Mozilla/5.0')]

OUT = r'D:\mth301小盘对照\a股全量_含行业.csv'

def fetch_all():
    rows = []
    fs = 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23'
    for pn in range(1, 200):
        url = (f'http://push2.eastmoney.com/api/qt/clist/get?pn={pn}&pz=100&po=1'
               f'&np=1&fltt=2&invt=2&fid=f20&fs={fs}&fields=f12,f14,f100,f20')
        try:
            data = json.loads(opener.open(url, timeout=30).read().decode('utf-8', 'ignore'))
        except Exception as e:
            print(f'pn={pn} 失败: {e}'); break
        diff = (data.get('data') or {}).get('diff') or []
        if not diff:
            break
        for d in diff:
            rows.append([d['f12'], d['f14'], d.get('f100') or '', d.get('f20') or 0])
    return rows

rows = fetch_all()
print(f'拉取股票数: {len(rows)}')

import os
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['code', 'name', 'industry', 'mktcap'])
    w.writerows(rows)
print(f'已保存: {OUT}')

ind = Counter(r[2] for r in rows)
print(f'\n行业总数: {len(ind)}')
print('\n=== 行业分布（按股票数）===')
for name, c in ind.most_common():
    print(f'  {name:<14} {c:>4}')
