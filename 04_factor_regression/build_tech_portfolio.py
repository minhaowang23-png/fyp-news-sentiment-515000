# -*- coding: utf-8 -*-
"""
构建纯科技股（TMT 硬科技）大小盘组合：
1. 读 a股全量_含行业.csv，筛科技行业 + 剔除 ST
2. 按总市值三分位分 大盘/中盘/小盘 三组
3. 拉每只科技股 5 年日线（断点续传，缓存 kline/）
4. 合成等权组合日收益（每日成分股涨跌幅算术平均）
"""
import csv, json, os, time, urllib.request
import pandas as pd
import numpy as np

UNIVERSE = r'D:\mth301小盘对照\a股全量_含行业.csv'
KLINE_DIR = r'D:\mth301小盘对照\kline'
OUT_DIR = r'D:\mth301小盘对照'
BEG, END = '20210101', '20261031'

TECH_INDUSTRIES = ['半导体', '软件开发', 'IT服务Ⅱ', '光学光电子', '消费电子',
                   '通信设备', '计算机设备', '元件', '军工电子Ⅱ', '通信服务',
                   '电子化学品Ⅱ', '其他电子Ⅱ']

PROXY = urllib.request.ProxyHandler({})
opener = urllib.request.build_opener(PROXY)
opener.addheaders = [('User-Agent', 'Mozilla/5.0')]

def secid(code):
    return ('1.' if code.startswith(('6', '9')) else '0.') + code

def fetch_kline(code):
    """返回 DataFrame[date, ret]，断点续传"""
    cache = os.path.join(KLINE_DIR, code + '.csv')
    if os.path.exists(cache):
        try:
            df = pd.read_csv(cache)
            if len(df) > 100:
                return df
        except Exception:
            pass
    url = (f'http://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid(code)}'
           f'&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f53,f59&klt=101&fqt=1'
           f'&beg={BEG}&end={END}')
    for _ in range(3):
        try:
            data = json.loads(opener.open(url, timeout=20).read().decode('utf-8', 'ignore'))
            klines = (data.get('data') or {}).get('klines') or []
            rows = []
            for k in klines:
                p = k.split(',')
                rows.append([p[0], float(p[2])])  # date, pct_chg
            df = pd.DataFrame(rows, columns=['date', 'ret'])
            df.to_csv(cache, index=False)
            return df
        except Exception as e:
            time.sleep(0.5)
    return pd.DataFrame(columns=['date', 'ret'])

def main():
    # 1. 读全量，筛科技股
    uni = pd.read_csv(UNIVERSE, encoding='utf-8-sig')
    uni['code'] = uni['code'].astype(str).str.zfill(6)
    uni['mktcap'] = pd.to_numeric(uni['mktcap'], errors='coerce').fillna(0)
    uni = uni[uni['industry'].isin(TECH_INDUSTRIES)].copy()
    uni = uni[~uni['name'].str.contains('ST|退', na=False)].copy()
    uni = uni[uni['mktcap'] > 0].copy()
    uni = uni.sort_values('mktcap', ascending=False).reset_index(drop=True)
    n = len(uni)
    print(f'科技股池（TMT硬科技，剔除ST）: {n} 只')

    # 2. 三分位分档
    q1, q2 = uni['mktcap'].quantile([1/3, 2/3])
    def bucket(cap):
        if cap >= q2: return '大盘'
        if cap >= q1: return '中盘'
        return '小盘'
    uni['bucket'] = uni['mktcap'].apply(bucket)
    print(f'分档阈值: 大盘≥{q2/1e8:.0f}亿, 中盘 {q1/1e8:.0f}~{q2/1e8:.0f}亿, 小盘<{q1/1e8:.0f}亿')
    for b in ['大盘', '中盘', '小盘']:
        sub = uni[uni['bucket'] == b]
        print(f'  {b}: {len(sub)} 只, 市值 {sub.mktcap.min()/1e8:.0f}~{sub.mktcap.max()/1e8:.0f} 亿, '
              f'中位数 {sub.mktcap.median()/1e8:.0f} 亿')

    # 3. 拉K线
    os.makedirs(KLINE_DIR, exist_ok=True)
    print(f'\n开始拉取 {n} 只股票日线（断点续传）...')
    rets = {}  # bucket -> dict[date -> list of ret]
    t0 = time.time()
    for i, (_, r) in enumerate(uni.iterrows()):
        df = fetch_kline(r['code'])
        if df.empty:
            continue
        df = df[(df['date'] >= '2021-01-01') & (df['date'] <= '2026-10-31')]
        b = r['bucket']
        d = rets.setdefault(b, {})
        for _, k in df.iterrows():
            d.setdefault(k['date'], []).append(k['ret'])
        if (i + 1) % 100 == 0:
            el = time.time() - t0
            print(f'  进度 {i+1}/{n}, 耗时 {el:.0f}s, 均速 {(i+1)/el:.2f} 只/s')

    # 4. 合成等权组合日收益
    print('\n合成等权组合日收益...')
    all_dates = sorted({d for b in rets.values() for d in b.keys()})
    rows = {'date': all_dates}
    for b in ['大盘', '中盘', '小盘']:
        d = rets.get(b, {})
        vals = [np.mean(d.get(dt, [])) if d.get(dt) else np.nan for dt in all_dates]
        rows[b + '_ret'] = vals
        print(f'  {b}: 覆盖交易日 {sum(1 for v in vals if not np.isnan(v))} 天, '
              f'日均成分股数 {np.nanmean([len(d.get(dt, [])) for dt in all_dates]):.1f}')
    out = pd.DataFrame(rows)
    outpath = os.path.join(OUT_DIR, '科技股组合_等权日收益.csv')
    out.to_csv(outpath, index=False, encoding='utf-8-sig')
    print(f'已保存: {outpath}')

if __name__ == '__main__':
    main()
