#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
词典法情绪打分（稳健性检验用）
用姜富伟等(2021)《媒体文本情绪与股票回报预测》的 CFSD 中文金融情感词典，
对科技新闻做 jieba 分词 + 查词典打分。

情绪得分 = (积极词数 - 消极词数) / (积极词数 + 消极词数)，范围 [-1, 1]
   +1 强正面，-1 强负面，0 中性（正负词均为 0 时记 0）。

输入:  D:\\mth301科技新闻筛选\\news_*.jsonl
输出:  D:\\mth301情绪打分_词典法\\news_*.jsonl （独立目录，不碰上游数据）

依赖:  jieba, pandas, openpyxl
"""
import os
import json
import glob
import time

import jieba
import pandas as pd

DICT_PATH = r'C:\Users\98097\WorkBuddy\2026-10-05-16-36-21\cfsd_dictionary.xlsx'
IN_DIR = r'D:\mth301科技新闻筛选'
OUT_DIR = r'D:\mth301情绪打分_词典法'


def load_dict(path):
    """读取词典，返回 (积极词集合, 消极词集合)。"""
    dfs = pd.read_excel(path, sheet_name=None)
    pos = set()
    neg = set()
    if 'positive' in dfs:
        pos = set(dfs['positive'].iloc[:, 0].dropna().astype(str).str.strip())
        pos.discard('Positive Word')
        pos.discard('')
    if 'negative' in dfs:
        neg = set(dfs['negative'].iloc[:, 0].dropna().astype(str).str.strip())
        neg.discard('Negative Word')
        neg.discard('')
    return pos, neg


def score(text, pos_words, neg_words):
    """对单条文本做词典法打分，返回 (情绪得分, 积极词数, 消极词数)。"""
    words = jieba.lcut(text)
    p = 0
    n = 0
    for w in words:
        if w in pos_words:
            p += 1
        elif w in neg_words:
            n += 1
    if p + n == 0:
        return 0.0, p, n
    return round((p - n) / (p + n), 6), p, n


def main():
    t0 = time.time()
    pos_words, neg_words = load_dict(DICT_PATH)
    print(f'词典加载完成：积极词 {len(pos_words)}，消极词 {len(neg_words)}')

    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(IN_DIR, 'news_*.jsonl')))
    print(f'待处理 {len(files)} 个月份文件')

    total = 0
    for i, f in enumerate(files, 1):
        base = os.path.basename(f)
        out = os.path.join(OUT_DIR, base)
        with open(f, encoding='utf-8') as fin, \
             open(out, 'w', encoding='utf-8') as fout:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                text = (o.get('title') or '') + '\n' + (o.get('content') or '')
                s, p, n = score(text, pos_words, neg_words)
                o['dict_sentiment'] = s
                o['dict_pos'] = p
                o['dict_neg'] = n
                fout.write(json.dumps(o, ensure_ascii=False) + '\n')
                total += 1
        print(f'[{i}/{len(files)}] 完成 {base}，累计 {total} 条，'
              f'耗时 {time.time() - t0:.0f}s')

    print(f'全部完成，总条数 {total}，总耗时 {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
