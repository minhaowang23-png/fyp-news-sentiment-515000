#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主方法情绪打分：用 bardsai/finance-sentiment-zh-base（中文金融情感 BERT）对科技新闻打分。

情绪得分 = P(positive) - P(negative)，范围 [-1, 1]。
每条新闻输出：sentiment_label（positive/neutral/negative）、
              sentiment_score（连续得分）、p_pos / p_neg / p_neu（三类概率）。

输入:  D:\\mth301科技新闻筛选\\news_*.jsonl
输出:  D:\\mth301情绪打分_模型\\news_*.jsonl （独立目录，不碰上游数据）

断点续传：已输出完成的月份文件会跳过，中断后重跑只处理未完成部分。

依赖:  torch, transformers
模型下载（可选镜像）:  HF_ENDPOINT=https://hf-mirror.com python sentiment_model_score.py
"""
import os
import json
import glob
import time
import sys

MODEL_NAME = 'bardsai/finance-sentiment-zh-base'
BATCH_SIZE = 128
MAX_LEN = 256
IN_DIR = r'D:\mth301科技新闻筛选'
OUT_DIR = r'D:\mth301情绪打分_模型'

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


def get_sentiment_ids(model):
    """从 label2id 动态确定 positive/negative 对应的下标，健壮处理多种命名。"""
    label2id = dict(model.config.label2id)
    id2label = dict(model.config.id2label)
    print('模型标签映射 id2label:', id2label)
    pos_id = neg_id = None
    for label, idx in label2id.items():
        low = str(label).lower()
        if 'pos' in low and pos_id is None:
            pos_id = idx
        elif 'neg' in low and neg_id is None:
            neg_id = idx
    # 兜底：若 id2label 里直接是 positive/negative
    for idx, label in id2label.items():
        low = str(label).lower()
        if 'pos' in low and pos_id is None:
            pos_id = idx
        elif 'neg' in low and neg_id is None:
            neg_id = idx
    if pos_id is None or neg_id is None:
        # 最后的约定兜底：0=negative, 2=positive, 1=neutral（多数金融模型顺序）
        print('警告：无法从标签名确定正负，采用约定 0=negative 2=positive')
        pos_id, neg_id = 2, 0
    return pos_id, neg_id, id2label


def main():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f'使用设备: {device}')
    if device == 'cuda':
        print(f'GPU: {torch.cuda.get_device_name(0)}')

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval().to(device)

    pos_id, neg_id, id2label = get_sentiment_ids(model)

    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(IN_DIR, 'news_*.jsonl')))
    print(f'待处理 {len(files)} 个月份文件，batch_size={BATCH_SIZE}')

    total = 0
    t0 = time.time()
    for i, f in enumerate(files, 1):
        base = os.path.basename(f)
        out = os.path.join(OUT_DIR, base)
        if os.path.exists(out):
            # 断点续传：跳过已完成文件
            print(f'[{i}/{len(files)}] 跳过已完成的 {base}')
            continue

        # 先读入该月所有文本
        records = []
        with open(f, encoding='utf-8') as fin:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                text = (o.get('title') or '') + '\n' + (o.get('content') or '')
                records.append((o, text))

        # 批量打分
        with open(out, 'w', encoding='utf-8') as fout:
            for s in range(0, len(records), BATCH_SIZE):
                chunk = records[s:s + BATCH_SIZE]
                texts = [t for _, t in chunk]
                enc = tokenizer(
                    texts, return_tensors='pt', padding=True,
                    truncation=True, max_length=MAX_LEN,
                )
                enc = {k: v.to(device) for k, v in enc.items()}
                with torch.no_grad():
                    logits = model(**enc).logits
                    probs = torch.softmax(logits, dim=-1).cpu().numpy()

                for (o, _), p in zip(chunk, probs):
                    score = float(p[pos_id] - p[neg_id])
                    label_id = int(p.argmax())
                    o['sentiment_label'] = str(id2label.get(label_id, label_id))
                    o['sentiment_score'] = round(score, 6)
                    o['p_pos'] = round(float(p[pos_id]), 6)
                    o['p_neg'] = round(float(p[neg_id]), 6)
                    o['p_neu'] = round(float(1 - p[pos_id] - p[neg_id]), 6)
                    fout.write(json.dumps(o, ensure_ascii=False) + '\n')
                    total += 1

        print(f'[{i}/{len(files)}] 完成 {base}，累计 {total} 条，'
              f'耗时 {time.time() - t0:.0f}s', flush=True)

    print(f'全部完成，总条数 {total}，总耗时 {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
