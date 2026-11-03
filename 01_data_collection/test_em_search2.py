# -*- coding: utf-8 -*-
import json, time, requests

def search_em(keyword, page=1, sort="time", extra_inner=None):
    url = "https://search-api-web.eastmoney.com/search/jsonp"
    inner = {
        "searchScope": "default",
        "sort": sort,
        "pageIndex": page,
        "pageSize": 10,
        "preTag": "",
        "postTag": ""
    }
    if extra_inner:
        inner.update(extra_inner)
    param = {
        "uid": "", "keyword": keyword,
        "type": ["cmsArticleWebOld"],
        "client": "web", "clientType": "web", "clientVersion": "curr",
        "param": {"cmsArticleWebOld": inner}
    }
    params = {"cb": "jQuery351_%d" % int(time.time()*1000),
              "param": json.dumps(param, ensure_ascii=False),
              "_": str(int(time.time()*1000))}
    r = requests.get(url, params=params, headers={"User-Agent":"Mozilla/5.0","Referer":"https://so.eastmoney.com/"}, timeout=20)
    txt = r.text
    if txt.startswith("jQuery"):
        i = txt.find("("); txt = txt[i+1: txt.rfind(")")]
    return json.loads(txt)

def show(res, label):
    d = res
    if d.get("code") != 0:
        print("  [%s] code=%s msg=%s" % (label, d.get("code"), d.get("msg")))
        return
    items = d.get("result", {}).get("cmsArticleWebOld", [])
    if not items:
        print("  [%s] 0条" % label); return
    dates = [it.get("date") for it in items]
    print("  [%s] %d条 日期 %s ~ %s  hitsTotal=%s" % (
        label, len(items), dates[-1][:10], dates[0][:10], d.get("hitsTotal")))
    print("      示例:", items[0]["title"][:30], "|", dates[0])

print("=== 尝试日期过滤，目标 2025 全年 ===")
# 变体A: startTime/endTime
show(search_em("半导体", extra_inner={"startTime":"2025-01-01 00:00:00","endTime":"2025-12-31 23:59:59"}), "A start/endTime")
# 变体B: beginTime/endTime
show(search_em("半导体", extra_inner={"beginTime":"2025-01-01","endTime":"2025-12-31"}), "B begin/endTime")
# 变体C: 无日期，纯 sort=time 深翻看是否到2025（page=50）
show(search_em("半导体", page=50, sort="time"), "C 无日期 page=50")
show(search_em("半导体", page=200, sort="time"), "C 无日期 page=200")
