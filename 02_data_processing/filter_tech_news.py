# -*- coding: utf-8 -*-
"""
科技新闻 · 关键词筛选脚本
============================
输入目录: D:\\mth301财经新闻数据_去重去噪        (去重去噪后数据，只读)
输出目录: D:\\mth301科技新闻筛选                  (独立存放，不影响其他数据)
词表:     本目录 tech_keywords.py (L1 概念词 + L2 公司名)

筛选规则:
  - 匹配范围: 标题 + 正文(用户已确认)
  - 命中 L1 核心赛道概念词 或 L2 科技龙头公司名 -> 判定为科技新闻，保留
  - L3 泛科技词(如"科技""创新")不参与筛选判定(过弱，易误伤)

英文/数字缩写边界(AI / 5G / GPU / 800G / MLCC ...):
  匹配时要求前后不是字母或数字，避免 "MAIN" 误中 "AI"、"15G" 误中 "5G"。

产出:
  - news_YYYY-MM.jsonl        逐月科技新闻(字段: datetime/title/content/hit_keywords/hit_categories)
  - _筛选统计.csv              逐月 + 总计命中漏斗
  - _筛选报告.md               供论文引用的筛选说明与类目分布
  - _抽样检查.jsonl            每月首条命中样例，供人工复核关键词是否合理
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tech_keywords import TECH_KEYWORDS, TECH_COMPANIES

INPUT_DIR = r"D:\mth301财经新闻数据_去重去噪"
OUTPUT_DIR = r"D:\mth301科技新闻筛选"

_EN_RE = re.compile(r"[A-Za-z]")


def _is_en(kw: str) -> bool:
    return bool(_EN_RE.search(kw))


def _compile(kw: str) -> re.Pattern:
    if _is_en(kw):
        # 含英文/数字：词边界 + 大小写不敏感
        return re.compile(r"(?<![A-Za-z0-9])" + re.escape(kw) + r"(?![A-Za-z0-9])", re.IGNORECASE)
    return re.compile(re.escape(kw))


def build_matchers():
    """构建 (类目, 关键词, 正则) 列表 + 快速预筛正则。"""
    matchers: list[tuple[str, str, re.Pattern]] = []
    cn_words: list[str] = []
    en_words: list[str] = []
    for cat, kws in TECH_KEYWORDS.items():
        for kw in kws:
            matchers.append((cat, kw, _compile(kw)))
            (en_words if _is_en(kw) else cn_words).append(kw)
    for name in TECH_COMPANIES:
        matchers.append(("公司", name, _compile(name)))
        (en_words if _is_en(name) else cn_words).append(name)

    parts = []
    if cn_words:
        parts.append("(?:" + "|".join(re.escape(k) for k in cn_words) + ")")
    if en_words:
        parts.append(r"(?<![A-Za-z0-9])(?:" + "|".join(re.escape(k) for k in en_words) + r")(?![A-Za-z0-9])")
    prescreen = re.compile("|".join(parts), re.IGNORECASE) if parts else None
    return matchers, prescreen


def match_hits(text: str, matchers) -> tuple[list[str], list[str]]:
    """逐词判定命中，返回 (命中类目去重列表, 命中关键词去重列表)。"""
    cats: list[str] = []
    kws: list[str] = []
    for cat, kw, rx in matchers:
        if rx.search(text):
            if cat not in cats:
                cats.append(cat)
            kws.append(kw)
    return cats, kws


def main() -> None:
    t0 = time.time()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(INPUT_DIR, "news_*.jsonl")))
    if not files:
        print(f"[错误] 输入目录无 news_*.jsonl: {INPUT_DIR}")
        sys.exit(1)

    matchers, prescreen = build_matchers()
    print(f"关键词匹配器: L1概念词 {len(TECH_KEYWORDS)} 类 / 总匹配器 {len(matchers)} 个", flush=True)

    stats: list[tuple[str, int, int]] = []
    cat_counter: Counter = Counter()
    kw_counter: Counter = Counter()
    total_in = total_hit = 0
    sample_path = os.path.join(OUTPUT_DIR, "_抽样检查.jsonl")
    sample_written = 0

    with open(sample_path, "w", encoding="utf-8") as sample_f:
        for fp in files:
            name = os.path.basename(fp)
            n_in = n_hit = 0
            out_path = os.path.join(OUTPUT_DIR, name)
            with open(fp, encoding="utf-8") as fin, \
                 open(out_path, "w", encoding="utf-8") as fout:
                for line in fin:
                    line = line.strip()
                    if not line:
                        continue
                    n_in += 1
                    o = json.loads(line)
                    title = o.get("title", "")
                    content = o.get("content", "")
                    text = title + "\n" + content
                    if prescreen is None or prescreen.search(text):
                        cats, kws = match_hits(text, matchers)
                        if cats:  # 命中 L1 或 L2
                            n_hit += 1
                            cat_counter.update(cats)
                            kw_counter.update(kws)
                            fout.write(json.dumps({
                                "datetime": o.get("datetime", ""),
                                "title": title,
                                "content": content,
                                "hit_keywords": kws,
                                "hit_categories": cats,
                            }, ensure_ascii=False) + "\n")
                            if sample_written < 30:
                                sample_f.write(json.dumps({
                                    "month": name, "title": title,
                                    "hit_keywords": kws, "hit_categories": cats,
                                }, ensure_ascii=False) + "\n")
                                sample_written += 1
            stats.append((name, n_in, n_hit))
            total_in += n_in
            total_hit += n_hit
            rate = n_hit / n_in * 100 if n_in else 0
            print(f"{name}: 输入 {n_in}  命中 {n_hit}  ({rate:.1f}%)", flush=True)

    # ---- 统计 ----
    csv_path = os.path.join(OUTPUT_DIR, "_筛选统计.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["月份", "输入条数", "科技新闻条数", "命中率"])
        for name, n_in, n_hit in stats:
            w.writerow([name, n_in, n_hit, f"{n_hit / n_in * 100:.2f}%" if n_in else "0%"])
        w.writerow(["总计", total_in, total_hit, f"{total_hit / total_in * 100:.2f}%" if total_in else "0%"])

    md_path = os.path.join(OUTPUT_DIR, "_筛选报告.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 科技新闻 · 关键词筛选报告\n\n")
        f.write(f"- 输入目录: `{INPUT_DIR}`\n")
        f.write(f"- 输出目录: `{OUTPUT_DIR}`\n")
        f.write(f"- 标的: 515000 华宝中证科技龙头ETF（中证科技龙头指数 931087）\n\n")
        f.write("## 筛选漏斗\n\n")
        f.write("| 阶段 | 条数 |\n|---|---|\n")
        f.write(f"| 去重去噪后输入 | {total_in:,} |\n")
        f.write(f"| 科技新闻(命中L1/L2) | {total_hit:,} |\n")
        f.write(f"| 命中率 | {total_hit / total_in * 100:.2f}% |\n\n")
        f.write("## 类目命中分布（一条新闻可命中多类）\n\n")
        f.write("| 类目 | 命中条数 |\n|---|---|\n")
        for cat, c in cat_counter.most_common():
            f.write(f"| {cat} | {c:,} |\n")
        f.write("\n## Top 30 关键词命中次数\n\n")
        f.write("| 关键词 | 次数 |\n|---|---|\n")
        for kw, c in kw_counter.most_common(30):
            f.write(f"| {kw} | {c:,} |\n")
        f.write("\n## 说明\n\n")
        f.write("- 匹配范围: 标题 + 正文；命中 L1 概念词或 L2 公司名即判定为科技新闻。\n")
        f.write("- 英文/数字缩写采用词边界匹配，避免误伤。\n")
        f.write("- 请人工抽查 `_抽样检查.jsonl`，确认关键词是否合理。\n")

    print("\n==================== 汇总 ====================", flush=True)
    print(f"输入 {total_in:,} 条，命中科技新闻 {total_hit:,} 条（{total_hit / total_in * 100:.2f}%）", flush=True)
    print(f"耗时 {time.time() - t0:.1f} 秒", flush=True)
    print(f"输出目录: {OUTPUT_DIR}", flush=True)
    print(f"统计: {csv_path}", flush=True)
    print(f"报告: {md_path}", flush=True)
    print(f"抽样: {sample_path}", flush=True)


if __name__ == "__main__":
    main()
