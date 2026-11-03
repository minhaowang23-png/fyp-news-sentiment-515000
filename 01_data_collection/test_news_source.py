# -*- coding: utf-8 -*-
import time, requests, traceback
from datetime import datetime

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.sina.com.cn/",
}

def test_sina(lid, name, max_pages=25):
    print("=" * 60)
    print("新浪滚动新闻  lid=%s (%s)" % (lid, name))
    base = "https://feed.mix.sina.com.cn/api/roll/get"
    all_dates = []
    last_count = 0
    for page in range(1, max_pages + 1):
        params = {"pageid": "153", "lid": lid, "k": "", "num": 50, "page": page, "r": str(time.time())}
        try:
            r = requests.get(base, params=params, headers=headers, timeout=15)
            data = r.json()
            code = data.get("result", {}).get("status", {}).get("code")
            items = data.get("result", {}).get("data", [])
            if code != 0 or not items:
                print("  第%d页: code=%s, 条数=0 -> 到头了" % (page, code))
                break
            dates = []
            for it in items:
                ctime = it.get("ctime")
                try:
                    dt = datetime.fromtimestamp(int(ctime))
                    dates.append(dt)
                except Exception:
                    pass
            if dates:
                all_dates.extend(dates)
                print("  第%d页: %d条  范围 %s ~ %s" % (page, len(dates), min(dates).strftime("%Y-%m-%d"), max(dates).strftime("%Y-%m-%d")))
            last_count = len(items)
            time.sleep(0.4)
        except Exception as e:
            print("  第%d页 出错: %s" % (page, e))
            break
    if all_dates:
        print("  >>> 合计 %d 条, 可追溯到的最早日期: %s" % (len(all_dates), min(all_dates).strftime("%Y-%m-%d")))
    else:
        print("  >>> 未取到任何数据")
    return all_dates

print("当前时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
test_sina(2516, "财经", 25)
test_sina(2517, "股票", 25)

print("=" * 60)
print("akshare 东财个股新闻 (stock_news_em)")
try:
    import akshare as ak
    for sym in ["515000", "600519"]:
        try:
            df = ak.stock_news_em(symbol=sym)
            if df is not None and not df.empty:
                col = "发布时间" if "发布时间" in df.columns else df.columns[0]
                print("  %s: %d 条, 列=%s, 时间范围 %s ~ %s" % (
                    sym, len(df), list(df.columns)[:4],
                    df[col].min(), df[col].max()))
            else:
                print("  %s: 空" % sym)
        except Exception as e:
            print("  %s 出错: %s" % (sym, repr(e)[:200]))
except Exception as e:
    traceback.print_exc()
print("DONE")
