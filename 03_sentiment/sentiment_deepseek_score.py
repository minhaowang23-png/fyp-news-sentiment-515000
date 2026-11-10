#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeepSeek 情绪打分脚本（第三套打分方法，主方法 LLM 打分）

用 DeepSeek API（deepseek-chat，OpenAI 兼容接口）对科技新闻逐条打分。
输出字段与词典法 / FinBERT 对齐，方便三方法横向对比：
  - deepseek_label : positive / neutral / negative（三分类，对应 FinBERT 的 sentiment_label）
  - deepseek_score : 连续情绪得分，范围 [-1, 1]（对应 dict_sentiment / sentiment_score）
  - deepseek_reason: 一句话理由（便于人工核对打分质量）

输入:  D:\\mth301科技新闻筛选\\news_*.jsonl（含 title + content）
输出:  D:\\mth301情绪打分_deepseek\\news_*.jsonl（独立目录，不碰上游数据）

依赖:  requests（pip install requests）
用法:
  设置 API Key（任选其一）:
    1) 环境变量:  set DEEPSEEK_API_KEY=sk-xxxx
    2) 命令行:    --api-key sk-xxxx
  打分:
    python sentiment_deepseek_score.py --api-key sk-xxxx
    python sentiment_deepseek_score.py --api-key sk-xxxx --input D:\\某文件.jsonl --output D:\\某输出.jsonl

特性:
  - 断点续传: 已输出的月份文件会跳过，中断后重跑只处理未完成部分
  - 并发 + 自动重试: 单文件内多线程并发，请求失败指数退避重试
  - 稳健解析: 模型偶发输出非标准 JSON 时，用正则兜底提取
"""
import os
import sys
import json
import glob
import time
import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ---- 默认路径 ----
IN_DIR = r'D:\mth301科技新闻筛选'
OUT_DIR = r'D:\mth301情绪打分_deepseek'
API_URL = 'https://api.deepseek.com/chat/completions'
MODEL = 'deepseek-chat'
MAX_WORKERS = 16          # 并发线程数（可调）
MAX_RETRY = 3             # 每条请求最大重试次数
MAX_LEN = 1500            # 内容截断长度（docs 已约定 1500 字）

SYSTEM_PROMPT = '''你是一名中文金融新闻情绪分析专家，任务是基于给定新闻文本，判断它对被报道主体（科技公司/标的，或行业整体）的股价情绪倾向。

判断规则：
1. 情绪主体：优先判断新闻中被报道的具体公司/标的；若描述的是行业整体，则判断行业层面情绪。
2. 以正文为准，标题仅作参考（标题与正文矛盾时以正文为主）。
3. 中性标准：只有纯事实陈述、不含任何利好或利空倾向时才判 neutral；只要有任何方向性倾向，就给出非零 score。
4. 分数锚点（务必按此尺度打分）：
   +0.8 ~ +1.0  重大利好（业绩大增、重大突破、获大单）
   +0.4 ~ +0.7  明显利好（上涨、增长、合作）
   +0.1 ~ +0.3  轻微利好
   0            中性
   -0.1 ~ -0.3  轻微利空
   -0.4 ~ -0.7  明显利空（下跌、亏损、减持）
   -0.8 ~ -1.0  重大利空（暴雷、退市、重大诉讼）

只输出一个 JSON 对象，不要输出任何其他文字、不要用代码块包裹，格式如下：
{"label":"positive|neutral|negative","score":-1到1之间的小数,"reason":"一句话判断依据(不超过30字，需具体可验证，如'净利增长20%'，不要只写'利好')"}

示例：
输入：新闻标题：某科技公司一季度净利润同比增长20.6%
输出：{"label":"positive","score":0.7,"reason":"净利同比增长20.6%，业绩明显改善"}'''


def parse_response(text):
    """稳健解析模型输出，提取 (label, score, reason)。"""
    text = (text or '').strip()
    # 优先尝试整体 JSON
    try:
        o = json.loads(text)
        return _norm(o)
    except Exception:
        pass
    # 尝试截取第一个 {...} 块
    m = re.search(r'\{.*?\}', text, re.S)
    if m:
        try:
            o = json.loads(m.group(0))
            return _norm(o)
        except Exception:
            pass
    # 正则兜底
    label = re.search(r'(positive|neutral|negative)', text, re.I)
    score = re.search(r'score["\']?\s*[:：]\s*["\']?(-?\d+(?:\.\d+)?)', text, re.I)
    reason = re.search(r'reason["\']?\s*[:：]\s*["\']([^"\']{1,60})', text, re.I)
    if label:
        return _norm({'label': label.group(1).lower(),
                      'score': float(score.group(1)) if score else 0.0,
                      'reason': reason.group(1) if reason else ''})
    return None


def _norm(o):
    label = str(o.get('label', '')).lower()
    if label not in ('positive', 'neutral', 'negative'):
        label = 'neutral'
    try:
        score = float(o.get('score', 0.0))
    except Exception:
        score = 0.0
    score = max(-1.0, min(1.0, score))
    return label, score, str(o.get('reason', ''))[:60]


def call_deepseek(api_key, title, content, idx=None):
    """单条调用 DeepSeek，返回 (label, score, reason) 或 None。"""
    text = f'新闻标题：{title}\n新闻内容：{content[:MAX_LEN]}'
    payload = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': text},
        ],
        'temperature': 0.0,          # 0 = 更确定、可复现
        'max_tokens': 128,
        'stream': False,
    }
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    last_err = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            r = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            if r.status_code == 200:
                msg = r.json()['choices'][0]['message']['content']
                parsed = parse_response(msg)
                if parsed:
                    return parsed
                last_err = f'解析失败: {msg[:80]!r}'
            else:
                last_err = f'HTTP {r.status_code}: {r.text[:120]}'
        except Exception as e:
            last_err = str(e)
        time.sleep(2 ** attempt)     # 指数退避: 2s, 4s, 8s
    return None


def score_file(api_key, in_path, out_path):
    """对单个 jsonl 文件逐条打分，写结果。"""
    # 读入全部记录
    records = []
    with open(in_path, encoding='utf-8') as fin:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            o = json.loads(line)
            records.append(o)

    # 并发打分，保持原顺序
    results = [None] * len(records)

    def work(i):
        o = records[i]
        parsed = call_deepseek(api_key, o.get('title') or '', o.get('content') or '', i)
        return i, parsed

    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = [ex.submit(work, i) for i in range(len(records))]
        for fut in as_completed(futs):
            i, parsed = fut.result()
            results[i] = parsed
            done += 1
            if done % 100 == 0:
                print(f'    已处理 {done}/{len(records)}', flush=True)

    # 写回
    fail = 0
    with open(out_path, 'w', encoding='utf-8') as fout:
        for i, o in enumerate(records):
            parsed = results[i]
            if parsed:
                label, score, reason = parsed
                o['deepseek_label'] = label
                o['deepseek_score'] = score
                o['deepseek_reason'] = reason
            else:
                o['deepseek_label'] = None
                o['deepseek_score'] = None
                o['deepseek_reason'] = 'ERROR'
                fail += 1
            fout.write(json.dumps(o, ensure_ascii=False) + '\n')
    return len(records), fail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--api-key', default=os.environ.get('DEEPSEEK_API_KEY', ''))
    ap.add_argument('--input', default='', help='单个输入文件；留空则处理 IN_DIR 下全部月份文件')
    ap.add_argument('--output', default='', help='单个输出文件（配合 --input 使用）')
    args = ap.parse_args()

    if not args.api_key:
        print('缺少 DeepSeek API Key。请用 --api-key sk-xxxx 或设置环境变量 DEEPSEEK_API_KEY')
        sys.exit(1)

    t0 = time.time()

    if args.input:
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        n, fail = score_file(args.api_key, args.input, args.output)
        print(f'完成 {n} 条，失败 {fail} 条，耗时 {time.time()-t0:.0f}s')
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(IN_DIR, 'news_*.jsonl')))
    print(f'待处理 {len(files)} 个月份文件，model={MODEL}，并发={MAX_WORKERS}')
    total = 0
    for i, f in enumerate(files, 1):
        base = os.path.basename(f)
        out = os.path.join(OUT_DIR, base)
        if os.path.exists(out):
            print(f'[{i}/{len(files)}] 跳过已完成的 {base}')
            continue
        print(f'[{i}/{len(files)}] 处理 {base} ...', flush=True)
        n, fail = score_file(args.api_key, f, out)
        total += n
        print(f'  完成 {n} 条，失败 {fail} 条，累计 {total}，'
              f'耗时 {time.time()-t0:.0f}s', flush=True)

    print(f'全部完成，总条数 {total}，总耗时 {time.time()-t0:.0f}s')


if __name__ == '__main__':
    main()
