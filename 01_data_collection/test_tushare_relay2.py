# -*- coding: utf-8 -*-
import requests, json

TOKEN = "YOUR_TUSHARE_RELAY_TOKEN"
BASE = "https://t.xiaodefa.top/"

def call(api_name, params=None, fields=""):
    body = {"api_name": api_name, "token": TOKEN, "params": params or {}, "fields": fields}
    try:
        r = requests.post(BASE, json=body, timeout=30)
        return r.status_code, r.json()
    except Exception as e:
        return None, repr(e)

def news_range(start, end, src=""):
    code, d = call("news", {"src": src, "start_date": start, "end_date": end})
    if isinstance(d, dict) and d.get("code") == 0 and d.get("data"):
        items = d["data"]["items"]
        return len(items), items
    return 0, []

print("########## 日期深度探测（每次3天窗口） ##########")
for start, end, label in [
    ("2021-01-01 00:00:00", "2021-01-03 23:59:59", "2021年初"),
    ("2022-06-01 00:00:00", "2022-06-03 23:59:59", "2022年中"),
    ("2023-01-01 00:00:00", "2023-01-03 23:59:59", "2023年初"),
    ("2024-06-01 00:00:00", "2024-06-03 23:59:59", "2024年中"),
    ("2025-06-01 00:00:00", "2025-06-03 23:59:59", "2025年中"),
]:
    n, items = news_range(start, end)
    if n:
        print("  %s: %d条  首条时间=%s" % (label, n, items[0][0]))
    else:
        print("  %s: 0条(无数据)" % label)

print()
print("########## 来源筛选测试 ##########")
for src in ["eastmoney", "sina", "10jqka", "wallstreetcn", "jinrongjie"]:
    code, d = call("news", {"src": src, "start_date": "2026-10-16 00:00:00", "end_date": "2026-10-17 23:59:59"})
    if isinstance(d, dict) and d.get("code") == 0 and d.get("data"):
        items = d["data"]["items"]
        print("  src=%s: code=%s 字段=%s 条数=%d" % (src, d.get("code"), d["data"]["fields"], len(items)))
        if items:
            print("      样例:", items[0][1][:60])
    else:
        print("  src=%s: code=%s msg=%s" % (src, d.get("code") if isinstance(d,dict) else "?", d.get("msg") if isinstance(d,dict) else d))

print()
print("########## 内容性质抽样（2023-01-05 全天） ##########")
n, items = news_range("2023-01-05 00:00:00", "2023-01-05 23:59:59")
print("全天条数:", n)
for it in items[:15]:
    print("  [%s] %s" % (it[0][11:16], it[2][:55]))
