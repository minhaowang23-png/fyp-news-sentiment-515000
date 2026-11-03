# -*- coding: utf-8 -*-
"""
================================================================
科技板块财经新闻下载脚本（可行性测试版）
================================================================
本脚本与正式下载脚本逻辑完全相同，仅将下载时间范围缩短为
2021-10-01 ~ 2021-11-30（约两个月），用于快速验证代码可行性。

【数据来源】
    本脚本通过 Tushare 的「新闻快讯」接口（api_name="news"）获取财经新闻。
    官方 Tushare 该接口需要付费积分才能调用，这里经第三方中转服务
    t.xiaodefa.top 开放了此接口的访问能力。

【数据内容】
    7x24 全球财经快讯（聚合多家媒体源），每条记录包含三个字段：
        - datetime : 发布时间（精确到秒）
        - title    : 新闻标题
        - content  : 新闻正文 / 摘要

【下载范围（测试版）】
    2021-10-01 00:00:00  ~  2021-11-30 23:59:59（约两个月）

【输出格式】
    按月份切分的 JSONL 文件：news_YYYY-MM.jsonl
    每行一条 JSON 记录，例如：
        {"datetime": "2021-10-05 09:30:00", "title": "...", "content": "..."}
    输出目录由下方 OUT_DIR 指定（测试版使用独立目录，避免与正式数据混淆）。

【核心机制】
    1. 断点续传：_progress.txt 记录所有已完成日期；中断后重跑会自动跳过。
    2. 递归分页：单次接口最多返回 1500 条，若某时段结果达到上限，则把
       时间窗二分后递归请求，保证不漏数据。
    3. 限速与重试：每次请求前轻限速，失败时温和退避重试，避免触发服务端
       限流；遇到空结果会额外重试 3 次，防止网络抖动导致「漏天」。
    4. 去重：同一天内按 (datetime, title) 去重。
    5. 单例锁：通过原子锁文件防止多个进程同时下载造成数据重复。

【运行方式】
    python 下载新闻数据代码-测试版.py
    依赖：requests（pip install requests）
================================================================
"""
import requests, json, os, time
from datetime import datetime, timedelta

# ---------------------------- 配置区 ----------------------------
TOKEN = "YOUR_TUSHARE_RELAY_TOKEN"  # 中转服务访问凭证
BASE = "https://t.xiaodefa.top/"                                   # 中转服务地址

OUT_DIR = r"C:\Users\98097\Desktop\科技新闻数据_测试2021"            # 输出目录（测试用独立目录）
PROGRESS_FILE = os.path.join(OUT_DIR, "_progress.txt")              # 断点续传记录文件

START = datetime(2021, 10, 1, 0, 0, 0)       # 下载起始时间
END   = datetime(2021, 11, 30, 23, 59, 59)   # 下载结束时间

CAP   = 1500   # 单次接口返回条数上限（服务端限制）
SLEEP = 0.25   # 每天处理完后的间隔秒数
# ----------------------------------------------------------------

def fmt(dt):
    """把 datetime 转成接口需要的时间字符串格式。"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def call(start, end, retries=4):
    """调用一次新闻接口，返回 [datetime, content, title] 列表。失败自动重试。"""
    body = {
        "api_name": "news",
        "token": TOKEN,
        "params": {
            "src": "",                                  # 空 = 聚合所有来源
            "start_date": fmt(start),
            "end_date": fmt(end),
        },
        "fields": "",
    }
    for attempt in range(retries):
        time.sleep(0.15)                                # 请求前轻限速
        try:
            r = requests.post(BASE, json=body, timeout=25)
            d = r.json()
            if d.get("code") == 0 and d.get("data"):
                return d["data"]["items"]               # list of [datetime, content, title]
            if d.get("code") != 0:
                # 限流 / 错误 -> 温和退避（起步 3 秒，避免疯狂重试加重限流）
                time.sleep(min(3 * (2 ** attempt), 30))
                continue
            return []
        except Exception:
            time.sleep(min(3 * (2 ** attempt), 30))
    return []


def fetch_all(start, end, depth=0):
    """递归分页：结果达到 1500 条上限则二分时间窗继续，保证不遗漏。"""
    items = call(start, end)
    if len(items) < CAP:
        return items
    # 达到上限，二分时间窗递归
    mid = start + (end - start) / 2
    left = fetch_all(start, mid, depth + 1)
    right = fetch_all(mid, end, depth + 1)
    return left + right


def load_progress():
    """读取已完成日期集合（用于断点续传）。"""
    done = set()
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    done.add(line)
    return done


def save_day(day_str, items):
    """把某一天的数据追加写入对应月份的 JSONL 文件。"""
    month = day_str[:7]
    path = os.path.join(OUT_DIR, "news_%s.jsonl" % month)
    with open(path, "a", encoding="utf-8") as f:
        for it in items:
            rec = {"datetime": it[0], "content": it[1], "title": it[2]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


LOCK_FILE = os.path.join(OUT_DIR, "_lock.pid")


def acquire_lock():
    """单例锁（原子创建）：防止多个下载进程同时写同一批文件。"""
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def main():
    os.makedirs(OUT_DIR, exist_ok=True)  # 先确保输出目录存在，再创建锁文件
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
        # 已完成的天直接跳过（断点续传）
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
            # 同一天内按 (datetime, title) 去重
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
            print("[%s] 已处理 %d 天, 累计 %d 条" % (
                datetime.now().strftime("%H:%M:%S"), day_count, item_count), flush=True)

        d += timedelta(days=1)
        time.sleep(SLEEP)

    print("DONE: %d 天, %d 条" % (day_count, item_count))
    try:
        os.remove(LOCK_FILE)
    except Exception:
        pass


if __name__ == "__main__":
    main()
