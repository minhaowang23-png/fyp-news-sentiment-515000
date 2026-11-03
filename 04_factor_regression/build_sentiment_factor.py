#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日度情绪因子构建：把逐条新闻的情绪得分按交易日聚合为日度情绪因子。

输入:  打分结果 jsonl（每条含 datetime + 情绪得分字段）
输出:  日度情绪因子 CSV（date, sentiment_mean, news_count, sentiment_std, pos_ratio, neg_ratio）

用法:
  python build_sentiment_factor.py --source 模型   # 用 sentiment_score 字段
  python build_sentiment_factor.py --source 词典法  # 用 dict_sentiment 字段

  默认输入/输出目录见下方常量，可改。
"""
import os
import json
import glob
import argparse
import pandas as pd

BASE = {
    '模型': (r'D:\mth301情绪打分_模型', 'sentiment_score', 'sentiment_label'),
    '词典法': (r'D:\mth301情绪打分_词典法', 'dict_sentiment', None),
}
OUT_DIR = r'D:\mth301情绪因子'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', default='模型', choices=['模型', '词典法'])
    args = ap.parse_args()

    in_dir, score_field, label_field = BASE[args.source]
    out_dir = os.path.join(OUT_DIR, args.source)
    os.makedirs(out_dir, exist_ok=True)

    files = sorted(glob.glob(os.path.join(in_dir, 'news_*.jsonl')))
    print(f'来源: {args.source}，得分字段 {score_field}，共 {len(files)} 个月份')

    rows = []
    for i, f in enumerate(files, 1):
        with open(f, encoding='utf-8') as fin:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                dt = o.get('datetime', '')
                sc = o.get(score_field)
                if not dt or sc is None:
                    continue
                rows.append((dt[:10], float(sc), o.get(label_field) if label_field else None))
        if i % 10 == 0:
            print(f'已读 {i}/{len(files)} 月')

    df = pd.DataFrame(rows, columns=['date', 'score', 'label'])
    print(f'共 {len(df)} 条有效记录，覆盖 {df["date"].nunique()} 个自然日')

    # 按日聚合
    g = df.groupby('date')
    out = pd.DataFrame({
        'sentiment_mean': g['score'].mean(),
        'news_count': g['score'].count(),
        'sentiment_std': g['score'].std(),
    })
    if label_field:
        out['pos_ratio'] = g.apply(lambda x: (x['label'].astype(str).str.lower() == 'positive').mean())
        out['neg_ratio'] = g.apply(lambda x: (x['label'].astype(str).str.lower() == 'negative').mean())
    out = out.reset_index()
    out['date'] = pd.to_datetime(out['date'])
    out = out.sort_values('date').reset_index(drop=True)

    out_path = os.path.join(out_dir, f'日度情绪因子_{args.source}.csv')
    out.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f'日度情绪因子已保存: {out_path}')
    print(f'共 {len(out)} 个自然日，日均新闻 {out["news_count"].mean():.1f} 条')
    print(out[['date', 'sentiment_mean', 'news_count']].head(8).to_string(index=False))
    print(out[['date', 'sentiment_mean', 'news_count']].tail(3).to_string(index=False))


if __name__ == '__main__':
    main()
