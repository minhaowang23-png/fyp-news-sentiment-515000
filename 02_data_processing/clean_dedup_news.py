# -*- coding: utf-8 -*-
"""
新闻数据 · 去重 + 去噪脚本
============================
输入目录: D:\\大学（本科）\\mth301\\mth301财经新闻数据   （只读，绝不改动源数据）
输出目录: D:\\mth301财经新闻数据_去重去噪                （独立存放）

数据来源: Tushare 7x24 全球财经快讯（字段: datetime / content / title）

处理流程（对应论文"数据清洗"环节的前两步）:
1) 去噪
   - 文本规范化: HTML 实体解码、去 URL、去真正的 HTML 标签、去控制字符、
     全角空格/多余空白归一化
   - 过滤规则（删除整条）:
     a. 清洗后 content 为空
     b. 清洗后 content 长度 < 5 字（纯垃圾/无信息量）
     c. 清洗后 content 不含任何中文字母数字（纯标点/纯符号/纯数字）
2) 去重（精确去重）
   - 以"归一化后的 title + content"拼接、去掉所有空白后计算 MD5
   - 全局（跨全部月份）保留首次出现的记录，后续重复一律删除
   - 说明: 7x24 快讯为高频短文本，近似去重(SimHash)会误删"相似但信息不同"的实时
     快讯（如"沪指涨超1%"与"沪指涨超1.5%"），故本环节只做精确去重。

产出:
   - news_YYYY-MM.jsonl       逐月清洗后数据（结构与源一致: datetime/title/content）
   - _去重去噪统计.csv         逐月 + 总计的过滤漏斗
   - _去重去噪报告.md          供论文引用的清洗说明与统计
"""
from __future__ import annotations

import csv
import glob
import hashlib
import html as html_lib
import json
import os
import re
import sys
import time

INPUT_DIR = r"D:\大学（本科）\mth301\mth301财经新闻数据"
OUTPUT_DIR = r"D:\mth301财经新闻数据_去重去噪"

MIN_CONTENT_LEN = 5  # 清洗后正文最短保留长度（字符）

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
# 只匹配真正的 HTML 标签（以字母或 / 开头），不误伤《通知》这种中文书名号里的尖括号
_HTML_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")
_WS_RE = re.compile(r"[ \t\r\n\f\v\u3000\xa0]+")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CJK_ALNUM_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


def normalize(text: str) -> str:
    """文本规范化：实体解码 → 去URL → 去HTML标签 → 去控制字符 → 空白归一化。"""
    if not text:
        return ""
    t = html_lib.unescape(text or "")
    t = _URL_RE.sub(" ", t)
    t = _HTML_TAG_RE.sub(" ", t)
    t = _CTRL_RE.sub(" ", t)
    t = _WS_RE.sub(" ", t)
    return t.strip()


def is_noise(content: str) -> bool:
    """判断清洗后的正文是否为噪声（应删除）。"""
    if not content:
        return True
    if len(content) < MIN_CONTENT_LEN:
        return True
    if not _CJK_ALNUM_RE.search(content):  # 不含任何中文/字母/数字 => 纯符号
        return True
    return False


def dedup_key(title: str, content: str) -> int:
    """精确去重键：归一化 title+content 去掉所有空白后取 MD5（转 128 位整数）。"""
    s = re.sub(r"\s+", "", (title or "") + (content or ""))
    return int.from_bytes(hashlib.md5(s.encode("utf-8")).digest(), "big")


def main() -> None:
    t0 = time.time()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(INPUT_DIR, "news_*.jsonl")))
    if not files:
        print(f"[错误] 输入目录无 news_*.jsonl 文件: {INPUT_DIR}")
        sys.exit(1)

    seen: set[int] = set()
    stats: list[tuple[str, int, int, int, int]] = []
    total_raw = total_noise = total_dup = total_keep = 0

    for fp in files:
        name = os.path.basename(fp)
        raw = noise = dup = keep = 0
        out_path = os.path.join(OUTPUT_DIR, name)
        with open(fp, encoding="utf-8") as fin, \
             open(out_path, "w", encoding="utf-8") as fout:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                raw += 1
                try:
                    o = json.loads(line)
                except Exception:
                    noise += 1
                    continue
                title = normalize(o.get("title") or "")
                content = normalize(o.get("content") or "")
                if is_noise(content):
                    noise += 1
                    continue
                key = dedup_key(title, content)
                if key in seen:
                    dup += 1
                    continue
                seen.add(key)
                keep += 1
                fout.write(json.dumps(
                    {"datetime": o.get("datetime", ""),
                     "title": title,
                     "content": content},
                    ensure_ascii=False) + "\n")
        stats.append((name, raw, noise, dup, keep))
        total_raw += raw
        total_noise += noise
        total_dup += dup
        total_keep += keep
        print(f"{name}: 原始 {raw}  去噪删 {noise}  去重删 {dup}  保留 {keep}", flush=True)

    # ---- 统计报告 ----
    csv_path = os.path.join(OUTPUT_DIR, "_去重去噪统计.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["月份", "原始条数", "去噪删除", "去重删除", "保留条数"])
        for name, raw, noise, dup, keep in stats:
            w.writerow([name, raw, noise, dup, keep])
        w.writerow(["总计", total_raw, total_noise, total_dup, total_keep])

    md_path = os.path.join(OUTPUT_DIR, "_去重去噪报告.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 新闻数据 · 去重去噪报告\n\n")
        f.write(f"- 输入目录: `{INPUT_DIR}`\n")
        f.write(f"- 输出目录: `{OUTPUT_DIR}`\n")
        f.write(f"- 数据来源: Tushare 7x24 全球财经快讯\n\n")
        f.write("## 过滤漏斗\n\n")
        f.write("| 阶段 | 条数 | 备注 |\n|---|---|---|\n")
        f.write(f"| 原始数据 | {total_raw:,} | 70 个月 jsonl |\n")
        f.write(f"| 去噪后 | {total_raw - total_noise:,} | 删 {total_noise:,} 条（空/超短/纯符号） |\n")
        f.write(f"| 去重后 | {total_keep:,} | 删 {total_dup:,} 条（精确重复） |\n\n")
        f.write("## 去噪规则\n\n")
        f.write("1. 文本规范化：HTML 实体解码、去 URL、去 HTML 标签、去控制字符、空白归一化。\n")
        f.write("2. 删除清洗后 content 为空的记录。\n")
        f.write(f"3. 删除清洗后 content 长度 < {MIN_CONTENT_LEN} 字的记录。\n")
        f.write("4. 删除清洗后不含任何中文/字母/数字（纯标点/符号/数字）的记录。\n\n")
        f.write("## 去重规则\n\n")
        f.write("- 精确去重：归一化后的 title+content 去空白后取 MD5，全局（跨月份）保留首次出现记录。\n")
        f.write("- 说明：7x24 快讯为高频短文本，未采用近似去重(SimHash)，避免误删相似但信息不同的实时快讯。\n")

    print("\n==================== 汇总 ====================", flush=True)
    print(f"原始 {total_raw:,} 条", flush=True)
    print(f"去噪删除 {total_noise:,} 条", flush=True)
    print(f"去重删除 {total_dup:,} 条", flush=True)
    print(f"最终保留 {total_keep:,} 条", flush=True)
    print(f"保留率 {total_keep / total_raw * 100:.2f}%", flush=True)
    print(f"耗时 {time.time() - t0:.1f} 秒", flush=True)
    print(f"输出目录: {OUTPUT_DIR}", flush=True)
    print(f"统计: {csv_path}", flush=True)
    print(f"报告: {md_path}", flush=True)


if __name__ == "__main__":
    main()
