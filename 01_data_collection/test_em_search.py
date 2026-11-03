# -*- coding: utf-8 -*-
import json, time, requests, urllib.parse

def search_em(keyword, page=1, sort="time"):
    # 东财搜索接口 (jsonp)
    url = "https://search-api-web.eastmoney.com/search/jsonp"
    param = {
        "uid": "",
        "keyword": keyword,
        "type": ["cmsArticleWebOld"],
        "client": "web",
        "clientType": "web",
        "clientVersion": "curr",
        "param": {
            "cmsArticleWebOld": {
                "searchScope": "default",
                "sort": sort,
                "pageIndex": page,
                "pageSize": 10,
                "preTag": "",
                "postTag": ""
            }
        }
    }
    params = {
        "cb": "jQuery351_%d" % int(time.time()*1000),
        "param": json.dumps(param, ensure_ascii=False),
        "_": str(int(time.time()*1000)),
    }
    r = requests.get(url, params=params, headers={"User-Agent":"Mozilla/5.0","Referer":"https://so.eastmoney.com/"}, timeout=20)
    txt = r.text
    # 去掉 jsonp 回调
    if txt.startswith("jQuery"):
        i = txt.find("(")
        txt = txt[i+1: txt.rfind(")")]
    return json.loads(txt)

print("=== 基础搜索: 半导体 ===")
try:
    d = search_em("半导体", page=1, sort="time")
    print("顶层keys:", list(d.keys()) if isinstance(d, dict) else type(d))
    print(json.dumps(d, ensure_ascii=False)[:800])
except Exception as e:
    import traceback; traceback.print_exc()
