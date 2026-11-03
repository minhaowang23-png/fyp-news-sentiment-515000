#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载中文金融情感模型并冒烟测试打分效果。"""
import os
os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL = 'bardsai/finance-sentiment-zh-base'


def main():
    print('下载模型:', MODEL)
    tokenizer = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model.eval().to(device)
    print('设备:', device)
    print('id2label:', model.config.id2label)
    print('label2id:', model.config.label2id)

    tests = [
        '公司业绩大幅增长，净利润同比翻倍，股价大涨',
        '公司爆雷，业绩亏损严重，股价暴跌',
        '公司发布公告，董事会召开会议',
        '芯片需求旺盛，半导体行业景气度持续提升',
        '美联储加息预期升温，市场承压',
    ]
    print('\n=== 冒烟测试 ===')
    for t in tests:
        enc = tokenizer(t, return_tensors='pt', truncation=True, max_length=256)
        enc = {k: v.to(device) for k, v in enc.items()}
        with torch.no_grad():
            probs = torch.softmax(model(**enc).logits, dim=-1)[0].cpu().numpy()
        print(f'  "{t[:20]}" -> {dict(zip(model.config.id2label.values(), [round(float(p), 3) for p in probs]))}')


if __name__ == '__main__':
    main()
