# -*- coding: utf-8 -*-
"""
科技新闻全量下载脚本（基于 Tushare 第三方中转 t.xiaodefa.top）
- 时间范围：2023-01-01 00:00:00 ~ 2026-10-17 23:59:59
- 来源：src=""（默认聚合 7x24 快讯，含全文 content）
- 输出：桌面 0-科技新闻数据/news_YYYY-MM.jsonl（按月），每行 {datetime, title, content}
- 特性：断点续传、按天递归分页(1500条/次上限)、限速、重试、去重
"""
import requests, json, os, time, sys, subprocess
from datetime import datetime, timedelta

TOKEN = "f26a5f9e7d0e0c045a7eee1bbb11c402ffd4458f357995f7c7a9dc67"
BASE = "https://t.xiaodefa.top/"
OUT_DIR = r"D:\mth301财经新闻数据"
PROGRESS_FILE = os.path.join(OUT_DIR, "_progress.txt")

START = datetime(2021, 1, 1, 0, 0, 0)
END = datetime(2022, 12, 31, 23, 59, 59)
CAP = 1500  # 单次上限
SLEEP = 0.25

def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def call(start, end, retries=4):
    body = {"api_name": "news", "token": TOKEN,
            "params": {"src": "", "start_date": fmt(start), "end_date": fmt(end)}, "fields": ""}
    for attempt in range(retries):
        time.sleep(0.15)  # 每次请求前轻限速
        try:
            r = requests.post(BASE, json=body, timeout=25)
            d = r.json()
            if d.get("code") == 0 and d.get("data"):
                return d["data"]["items"]  # list of [datetime, content, title]
            if d.get("code") != 0:
                # 限流/错误 -> 温和退避（起步3s，避免疯狂重试触发更狠限流）
                time.sleep(min(3 * (2 ** attempt), 30))
                continue
            return []
        except Exception as e:
            time.sleep(min(3 * (2 ** attempt), 30))
    return []

def fetch_all(start, end, depth=0):
    """递归分页：结果达到上限则二分时间窗继续，保证不遗漏。"""
    items = call(start, end)
    if len(items) < CAP:
        return items
    # 达到上限，二分
    mid = start + (end - start) / 2
    left = fetch_all(start, mid, depth + 1)
    right = fetch_all(mid, end, depth + 1)
    return left + right

def load_progress():
    done = set()
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    done.add(line)
    return done

def save_day(day_str, items):
    month = day_str[:7]
    path = os.path.join(OUT_DIR, "news_%s.jsonl" % month)
    with open(path, "a", encoding="utf-8") as f:
        for it in items:
            rec = {"datetime": it[0], "content": it[1], "title": it[2]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

LOCK_FILE = os.path.join(OUT_DIR, "_lock.pid")

def acquire_lock():
    """单例锁（原子 O_EXCL）：谁先创建锁谁跑，另一个立即退出。"""
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False

def main():
    if not acquire_lock():
        print("[SKIP] 已有下载进程在运行，本进程退出", flush=True)
        return
    done = load_progress()
    d = START
    total_days = (END - START).days + 1
    day_count = 0
    item_count = 0
    while d <= END:
        day_str = d.strftime("%Y-%m-%d")
        if day_str in done:
            d += timedelta(days=1)
            continue
        day_end = datetime(d.year, d.month, d.day, 23, 59, 59)
        if day_end > END:
            day_end = END
        items = fetch_all(d, day_end)
        # 空结果重试：网络抖动会导致静默空，避免漏天
        _retry = 0
        while len(items) == 0 and _retry < 3:
            time.sleep(3)
            items = fetch_all(d, day_end)
            _retry += 1
        if items:
            # 去重(同一天内按 datetime+title)
            seen = set()
            uniq = []
            for it in items:
                k = (it[0], it[2])
                if k not in seen:
                    seen.add(k)
                    uniq.append(it)
            save_day(day_str, uniq)
            item_count += len(uniq)
            # 有数据才记录进度
            with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
                f.write(day_str + "\n")
        else:
            print("[WARN] %s 无数据，暂不标记完成，下次重试" % day_str, flush=True)
        day_count += 1
        if day_count % 20 == 0:
            print("[%s] 已处理 %d 天, 累计 %d 条" % (datetime.now().strftime("%H:%M:%S"), day_count, item_count), flush=True)
        d += timedelta(days=1)
        time.sleep(SLEEP)
    print("DONE: %d 天, %d 条" % (day_count, item_count))
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass

if __name__ == "__main__":
    main()
