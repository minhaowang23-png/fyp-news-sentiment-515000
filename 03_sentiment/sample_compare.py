#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
随机抽样 + 三方法打分对比表生成

从词典法 / FinBERT / DeepSeek 三套打分结果中，随机抽取 N 条新闻，
合并成一张"三方法打分对照表"，导出到桌面（xlsx + csv），供人工核对打分质量。

两阶段用法:
  阶段1 抽样（生成待 DeepSeek 打分的清单）:
    python sample_compare.py --step sample --n 100
    -> 输出 D:\\mth301情绪因子\\抽样100条_待deepseek打分.jsonl

  阶段2 DeepSeek 打分（用另一脚本对上面清单打分）:
    python sentiment_deepseek_score.py --api-key sk-xxxx \
        --input D:\\mth301情绪因子\\抽样100条_待deepseek打分.jsonl \
        --output D:\\mth301情绪因子\\抽样100条_已deepseek打分.jsonl

  阶段3 合并导出（生成三方法对照表到桌面）:
    python sample_compare.py --step merge --n 100

依赖:  pandas, openpyxl
"""
import os
import json
import glob
import random
import argparse

import pandas as pd

DICT_DIR = r'D:\mth301情绪打分_词典法'
FIN_DIR = r'D:\mth301情绪打分_模型'
TMP_DIR = r'D:\mth301情绪因子'
DESKTOP = os.path.join(os.path.expanduser('~'), 'Desktop')
SEED = 42                       # 固定随机种子，保证抽样可复现
CONTENT_MAX = 120               # 导出时内容截断字数（表格太长不好看）


def load_scored(method):
    """加载某套打分结果，返回 {key: record}，key = datetime|title|content。"""
    d = {}
    in_dir = DICT_DIR if method == 'dict' else FIN_DIR
    for f in glob.glob(os.path.join(in_dir, 'news_*.jsonl')):
        with open(f, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                key = f"{o.get('datetime','')}|{o.get('title','')}|{o.get('content','')[:200]}"
                d[key] = o
    return d


def sample_step(n):
    print('加载词典法打分结果 ...')
    dct = load_scored('dict')
    print(f'  词典法共 {len(dct)} 条')
    print('加载 FinBERT 打分结果 ...')
    fin = load_scored('fin')
    print(f'  FinBERT 共 {len(fin)} 条')

    # 取两方法交集（理论上完全一致，因为同源）
    keys = [k for k in dct if k in fin]
    print(f'两方法交集 {len(keys)} 条')

    random.seed(SEED)
    sampled = random.sample(keys, n)

    rows = []
    for k in sampled:
        o = dict(dct[k])          # 词典法记录（含 dict_sentiment 等）
        f = fin[k]                # FinBERT 记录（含 sentiment_score 等）
        o['sentiment_label'] = f.get('sentiment_label')
        o['sentiment_score'] = f.get('sentiment_score')
        o['p_pos'] = f.get('p_pos')
        o['p_neg'] = f.get('p_neg')
        o['p_neu'] = f.get('p_neu')
        rows.append(o)

    os.makedirs(TMP_DIR, exist_ok=True)
    out = os.path.join(TMP_DIR, f'抽样{n}条_待deepseek打分.jsonl')
    with open(out, 'w', encoding='utf-8') as fo:
        for o in rows:
            fo.write(json.dumps(o, ensure_ascii=False) + '\n')
    print(f'已抽样 {len(rows)} 条 -> {out}')
    print('下一步: 用 sentiment_deepseek_score.py 对该文件打分')


def merge_step(n):
    in_file = os.path.join(TMP_DIR, f'抽样{n}条_已deepseek打分.jsonl')
    if not os.path.exists(in_file):
        print(f'找不到 DeepSeek 打分结果: {in_file}')
        print('请先运行: python sentiment_deepseek_score.py --api-key sk-xxxx '
              f'--input {os.path.join(TMP_DIR, f"抽样{n}条_待deepseek打分.jsonl")} '
              f'--output {in_file}')
        return

    rows = []
    with open(in_file, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    data = []
    for i, o in enumerate(rows, 1):
        data.append({
            '序号': i,
            '日期': (o.get('datetime') or '')[:10],
            '标题': (o.get('title') or '')[:60],
            '内容(截断)': (o.get('content') or '').replace('\n', ' ')[:CONTENT_MAX],
            '词典法得分(-1~1)': o.get('dict_sentiment'),
            '词典法正面词数': o.get('dict_pos'),
            '词典法负面词数': o.get('dict_neg'),
            'FinBERT标签': o.get('sentiment_label'),
            'FinBERT得分(-1~1)': o.get('sentiment_score'),
            'FinBERT正面概率': o.get('p_pos'),
            'FinBERT负面概率': o.get('p_neg'),
            'FinBERT中性概率': o.get('p_neu'),
            'DeepSeek标签': o.get('deepseek_label'),
            'DeepSeek得分(-1~1)': o.get('deepseek_score'),
            'DeepSeek理由': o.get('deepseek_reason'),
        })

    df = pd.DataFrame(data)

    xlsx_path = os.path.join(DESKTOP, f'随机抽样{n}条_三方法打分对比.xlsx')
    csv_path = os.path.join(DESKTOP, f'随机抽样{n}条_三方法打分对比.csv')
    df.to_excel(xlsx_path, index=False)
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')

    print(f'已导出 {len(df)} 条对比结果:')
    print(f'  {xlsx_path}')
    print(f'  {csv_path}')

    # 简单一致性统计
    def sign(x):
        if x is None:
            return None
        x = float(x)
        if x > 0.05:
            return '+'
        if x < -0.05:
            return '-'
        return '0'
    df['_d'] = df['词典法得分(-1~1)'].map(sign)
    df['_f'] = df['FinBERT得分(-1~1)'].map(sign)
    df['_s'] = df['DeepSeek得分(-1~1)'].map(sign)
    agree_df_fin = (df['_d'] == df['_f']).mean()
    agree_df_ds = (df['_d'] == df['_s']).mean()
    agree_fin_ds = (df['_f'] == df['_s']).mean()
    print(f'\n方向一致性(正/负/中性符号一致比例):')
    print(f'  词典法 vs FinBERT : {agree_df_fin:.1%}')
    print(f'  词典法 vs DeepSeek: {agree_df_ds:.1%}')
    print(f'  FinBERT vs DeepSeek: {agree_fin_ds:.1%}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--step', default='sample', choices=['sample', 'merge'])
    ap.add_argument('--n', type=int, default=100, help='抽样条数')
    args = ap.parse_args()

    if args.step == 'sample':
        sample_step(args.n)
    else:
        merge_step(args.n)


if __name__ == '__main__':
    main()
