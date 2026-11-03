# -*- coding: utf-8 -*-
import json, time, requests
from datetime import datetime

def random_number_str(n):
    import random
    return ''.join(str(random.randint(0, 9)) for _ in range(n))

def timestamp_str():
    return str(int(time.time() * 1000))

headers = {
    'Accept': '*/*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://kuaixun.eastmoney.com/',
    'Sec-Fetch-Dest': 'script',
    'Sec-Fetch-Mode': 'no-cors',
    'Sec-Fetch-Site': 'same-site',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

def fetch_page(col_id, page):
    url = f'https://newsapi.eastmoney.com/kuaixun/v1/getlist_{col_id}_ajaxResult_50_{page}_.html'
    params = {'r': '0.2' + random_number_str(16), '_': timestamp_str()}
    r = requests.get(url, params=params, headers=headers, timeout=15)
    text = r.text
    json_str = text.replace('var ajaxResult=', '')
    return json.loads(json_str)

def test_col(col_id, name, max_pages=80):
    print("=" * 60)
    print("东方财富快讯  栏目id=%s (%s)" % (col_id, name))
    all_dates = []
    for page in range(1, max_pages + 1):
        try:
            data = fetch_page(col_id, page)
            items = data.get('LivesList') or []
            if not items:
                print("  第%d页: 0条 -> 到头" % page)
                break
            dates = []
            for it in items:
                st = it.get('showtime')
                if st:
                    try:
                        dates.append(datetime.strptime(str(st)[:19], "%Y-%m-%d %H:%M:%S"))
                    except Exception:
                        pass
            all_dates.extend(dates)
            if page % 10 == 1 or page == 1:
                if dates:
                    print("  第%d页: %d条  范围 %s ~ %s" % (page, len(dates), min(dates).strftime("%Y-%m-%d"), max(dates).strftime("%Y-%m-%d")))
            if page >= 2 and page % 20 == 0:
                print("      ... 已翻到第%d页, 当前最早 %s" % (page, min(all_dates).strftime("%Y-%m-%d")))
            time.sleep(0.3)
        except Exception as e:
            print("  第%d页 出错: %s" % (page, repr(e)[:150]))
            break
    if all_dates:
        print("  >>> 合计 %d 条, 可追溯到最早: %s" % (len(all_dates), min(all_dates).strftime("%Y-%m-%d %H:%M")))
    else:
        print("  >>> 无数据")
    return all_dates

print("当前时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
test_col(102, "全球财经快讯(原代码)", 80)

# 顺带测一个更快的深度：直接请求大页码看是否被拒绝/为空
print()
print("=== 深页码探测(102) ===")
for p in [100, 500, 1000]:
    try:
        d = fetch_page(102, p)
        items = d.get('LivesList') or []
        mn = mx = None
        for it in items:
            st = it.get('showtime')
            if st:
                if mn is None: mn = st
                mx = st
        print("  页%d: %d条  范围 %s ~ %s" % (p, len(items), mn, mx))
    except Exception as e:
        print("  页%d 出错: %s" % (p, repr(e)[:150]))
    time.sleep(0.3)
print("DONE")
