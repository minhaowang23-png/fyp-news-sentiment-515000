# -*- coding: utf-8 -*-
import time, requests
from datetime import datetime

def fetch(page, pageSize=20):
    headers = {
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'origin': 'https://www.jrwei.com',
        'referer': 'https://www.jrwei.com/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    params = {
        'page': str(page),
        'pageSize': str(pageSize),
        'token': 'YOUR_JRWEI_TOKEN',
        'tokenCode': 'YOUR_JRWEI_TOKEN_CODE',
    }
    r = requests.get('https://kuaixun.jrjr.com:4338/get.php', params=params, headers=headers, timeout=20)
    return r

print("=== 第1页 ===")
try:
    r = fetch(1)
    print("HTTP", r.status_code)
    d = r.json()
    print("顶层keys:", list(d.keys()) if isinstance(d, dict) else type(d))
    data = d.get('data') if isinstance(d, dict) else None
    if data:
        print("第1页条数:", len(data))
        print("字段:", list(data[0].keys()))
        # 时间字段
        ts = [it.get('PUBLISHTIME') for it in data]
        print("PUBLISHTIME 样例:", ts[0], "~", ts[-1])
    else:
        print("无 data 字段, 原始:", str(d)[:500])
except Exception as e:
    import traceback; traceback.print_exc()

print()
print("=== 分页深度探测 ===")
def get_range(page):
    r = fetch(page)
    d = r.json()
    data = d.get('data') or []
    if not data:
        return None, None, None
    ts = [str(it.get('PUBLISHTIME')) for it in data if it.get('PUBLISHTIME')]
    return len(data), ts[-1], ts[0]

for p in [1, 2, 5, 10, 20, 50, 100, 200]:
    try:
        n, mn, mx = get_range(p)
        if n is None:
            print("  页%d: 0条(到头)" % p); continue
        print("  页%d: %d条  范围 %s ~ %s" % (p, n, mn[:19] if mn else mn, mx[:19] if mx else mx))
    except Exception as e:
        print("  页%d 出错: %s" % (p, repr(e)[:120]))
    time.sleep(0.4)
print("DONE")
