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

def show(api_name, params, fields=""):
    code, d = call(api_name, params, fields)
    print("=" * 60)
    print("api=%s params=%s" % (api_name, params))
    print("http=%s" % code)
    if isinstance(d, dict):
        print("返回keys:", list(d.keys()))
        print("code=%s msg=%s" % (d.get("code"), d.get("msg")))
        data = d.get("data")
        if data:
            flds = data.get("fields", [])
            items = data.get("items", [])
            print("字段:", flds)
            print("条数:", len(items))
            if items:
                print("样例1:", items[0])
                print("样例末:", items[-1])
        else:
            print("原始:", json.dumps(d, ensure_ascii=False)[:300])
    else:
        print("原始:", str(d)[:300])
    print()

# 1. 认证检查
show("stock_basic", {"list_status": "L"}, "ts_code,symbol,name")

# 2. 新闻接口 - 近期
show("news", {"src": "", "start_date": "2026-10-01 00:00:00", "end_date": "2026-10-17 23:59:59"})

# 3. 新闻接口 - 2023 年初（历史测试）
show("news", {"src": "", "start_date": "2023-01-01 00:00:00", "end_date": "2023-01-05 23:59:59"})
