# -*- coding: utf-8 -*-
"""
小盘科技组合对照：创业板指(399006) + 科创50(000688) 的情绪因子 Carhart 回归

目的：与 515000（大盘科技龙头）形成"大小盘 / 难套利程度"对照，
      检验"新闻情绪因子对难套利的中小盘科技指数是否预测力更强"（Baker-Wurgler 2007 假说）。

标的：
  - 515000  华宝中证科技龙头ETF（大盘科技龙头，主研究标的，CSMAR 基金行情）
  - 399006  创业板指（中小盘成长科技，对照1，东财免费接口）
  - 000688  科创50（科创板硬科技，对照2，东财免费接口）

方法：与 regression.py 完全一致的 Carhart 四因子 + 情绪因子时间序列回归，
      新-西 HAC 标准误，输出四因子 vs 五因子 ΔR² 增量检验。

用法：
  python smallcap_control.py                      # 模型法(主方法) 3年+5年
  python smallcap_control.py --sentiment 词典法    # 词典法(稳健性)
"""
import os
import json
import argparse
import urllib.request
import pandas as pd
import numpy as np
import statsmodels.api as sm
from scipy.stats import f as fdist

FF3 = r'D:\大学（本科）\mth301\三因子模型指标(日)132201088(仅供西交利物浦大学使用)\STK_MKT_THRFACDAY.xlsx'
FF4 = r'D:\大学（本科）\mth301\STK_MKT_CARHARTFOURFACTORS.xlsx'
RF = r'D:\大学（本科）\mth301\无风险利率文件141014171(仅供西交利物浦大学使用)\TRD_Nrrate.xlsx'
FUND = r'D:\大学（本科）\mth301\FUND_MKT_Quotation.xlsx'
SENT = {
    '模型': r'D:\mth301情绪因子\模型\日度情绪因子_模型.csv',
    '词典法': r'D:\mth301情绪因子\词典法\日度情绪因子_词典法.csv',
}
OUT_DIR = r'D:\mth301回归结果'
DATA_DIR = r'D:\mth301小盘对照'
MARKET = 'P9714'  # 沪深A股+创业板+科创板 全市场因子

# 东财 secid 规则：深市指数=0.xxxxxx，沪市指数=1.xxxxxx
INDEXES = {
    '创业板指': '0.399006',
    '科创50': '1.000688',
}


def read_csmar(path):
    """读 CSMAR xlsx：第一行英文列名作表头，跳过中文行和单位行。"""
    return pd.read_excel(path, header=0, skiprows=[1, 2])


def fetch_index_eastmoney(secid, name, beg='20210101', end='20261104'):
    """从东方财富免费接口拉取指数日度收盘价，计算日度收益。"""
    url = (f"http://push2his.eastmoney.com/api/qt/stock/kline/get"
           f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
           f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
           f"&klt=101&fqt=1&beg={beg}&end={end}")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.loads(r.read().decode('utf-8'))
    klines = payload['data']['klines']
    rows = []
    for k in klines:
        p = k.split(',')
        rows.append((p[0], float(p[2])))  # date, close
    df = pd.DataFrame(rows, columns=['TradingDate', 'ClosePrice'])
    df['TradingDate'] = pd.to_datetime(df['TradingDate'])
    df['ReturnDaily'] = df['ClosePrice'].pct_change()
    print(f'  [{name}] 东财接口获取 {len(df)} 个交易日：{df["TradingDate"].min().date()} ~ {df["TradingDate"].max().date()}')
    return df


def load_common():
    """加载四因子、无风险利率、情绪因子（所有标的共用）。"""
    ff3 = read_csmar(FF3)
    ff3 = ff3[ff3['MarkettypeID'] == MARKET][['TradingDate', 'RiskPremium1', 'SMB1', 'HML1']].copy()
    ff3['TradingDate'] = pd.to_datetime(ff3['TradingDate'])

    ff4 = read_csmar(FF4)
    ff4 = ff4[ff4['MarkettypeID'] == MARKET][['TradingMonth', 'UMD1']].copy()
    ff4['TradingMonth'] = ff4['TradingMonth'].astype(str).str.strip()

    rf = read_csmar(RF)[['Clsdt', 'Nrrdaydt']].copy()
    rf['Clsdt'] = pd.to_datetime(rf['Clsdt'])

    sent = pd.read_csv(SENT[args.sentiment])
    sent['date'] = pd.to_datetime(sent['date'])
    return ff3, ff4, rf, sent


def build_df(returns, ff3, ff4, rf, sent, lag=1):
    """把标的日度收益与因子/情绪合并，构造超额收益与滞后情绪。"""
    df = returns.merge(rf, left_on='TradingDate', right_on='Clsdt', how='left')
    df = df.merge(ff3, on='TradingDate', how='left')
    df['ym'] = df['TradingDate'].dt.strftime('%Y-%m')
    df = df.merge(ff4[['TradingMonth', 'UMD1']], left_on='ym', right_on='TradingMonth', how='left')
    df = df.merge(sent[['date', 'sentiment_mean']], left_on='TradingDate', right_on='date', how='left')
    df['excess'] = df['ReturnDaily'] - df['Nrrdaydt'] / 100
    df = df.sort_values('TradingDate').reset_index(drop=True)
    df['sent_lag'] = df['sentiment_mean'].shift(lag)
    return df


def run_reg(df, name, start, end):
    """对单个标的、单个区间跑 Carhart 四因子 vs 五因子回归，返回结果 dict。"""
    sub = df[(df['TradingDate'] >= start) & (df['TradingDate'] <= end)]
    sub = sub.dropna(subset=['excess', 'RiskPremium1', 'SMB1', 'HML1', 'UMD1', 'sent_lag'])
    n = len(sub)
    if n < 30:
        return None
    y = sub['excess'].to_numpy()
    X4 = sub[['RiskPremium1', 'SMB1', 'HML1', 'UMD1']].to_numpy()
    X5 = sub[['RiskPremium1', 'SMB1', 'HML1', 'UMD1', 'sent_lag']].to_numpy()
    kw = dict(cov_type='HAC', cov_kwds={'maxlags': max(1, int(n ** 0.5))})
    m4 = sm.OLS(y, sm.add_constant(X4)).fit(**kw)
    m5 = sm.OLS(y, sm.add_constant(X5)).fit(**kw)
    dr2 = m5.rsquared - m4.rsquared
    t_sent = m5.tvalues[-1]
    p_inc = fdist.sf(t_sent ** 2, 1, n - X5.shape[1] - 1)
    return {
        'name': name, 'start': start, 'end': end, 'n': n,
        'sent_coef': m5.params[-1], 'sent_t': t_sent, 'sent_p': m5.pvalues[-1],
        'r2_4': m4.rsquared, 'r2_5': m5.rsquared, 'dr2': dr2,
        'f_inc': t_sent ** 2, 'p_inc': p_inc,
    }


def fmt_block(res, label):
    lines = [f'\n【{label}】{res["name"]}  {res["start"]} ~ {res["end"]}  n={res["n"]}']
    lines.append(f'  情绪系数 β5 = {res["sent_coef"]:+.6f}   t = {res["sent_t"]:+.3f}   p = {res["sent_p"]:.4f}')
    lines.append(f'  R²(四因子) = {res["r2_4"]:.4f}   R²(五因子) = {res["r2_5"]:.4f}   ΔR² = {res["dr2"]:.6f}   增量F p = {res["p_inc"]:.4f}')
    lines.append(f'  显著: {"是" if res["sent_p"] < 0.05 else "否" if res["sent_p"] < 0.10 else "否(不显著)"}')
    return '\n'.join(lines)


def main():
    global args
    ap = argparse.ArgumentParser()
    ap.add_argument('--sentiment', default='模型', choices=['模型', '词典法'])
    ap.add_argument('--lag', type=int, default=1)
    args = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)

    ff3, ff4, rf, sent = load_common()
    print(f'情绪源: {args.sentiment}   滞后: {args.lag}期   市场因子: {MARKET}\n')

    # ---- 三个标的的日度收益序列 ----
    # 1) 515000（CSMAR 基金行情）
    fund = read_csmar(FUND)
    fund = fund[fund['Symbol'] == 515000][['TradingDate', 'ReturnDaily']].copy()
    fund['TradingDate'] = pd.to_datetime(fund['TradingDate'])

    # 2) 东财指数
    index_dfs = {}
    for name, secid in INDEXES.items():
        idx = fetch_index_eastmoney(secid, name)
        idx.to_csv(os.path.join(DATA_DIR, f'{name}_日度行情.csv'), index=False, encoding='utf-8-sig')
        index_dfs[name] = idx

    # ---- 跑回归 ----
    targets = {'515000(科技龙头ETF)': fund}
    targets.update(index_dfs)

    results = []
    blocks = []
    for name, ret in targets.items():
        df = build_df(ret, ff3, ff4, rf, sent, lag=args.lag)
        for start, end, tag in [('2023-10-01', '2026-10-31', '3年主样本'),
                                ('2021-01-01', '2026-10-31', '5年扩展样本')]:
            res = run_reg(df, name, start, end)
            if res:
                results.append(res)
                blocks.append(fmt_block(res, tag))

    # ---- 输出对比汇总 ----
    header = '\n'.join([
        '=' * 74,
        f'小盘科技组合对照：新闻情绪因子 Carhart 回归（{args.sentiment}，滞后{args.lag}期）',
        f'对照标的: 515000(大盘科技龙头) vs 创业板指(中小盘成长) vs 科创50(硬科技)',
        '=' * 74,
    ])
    table_lines = [header, '\n【对比汇总表】']
    table_lines.append(f'{"标的":<20}{"样本":<6}{"情绪β5":>10}{"t值":>8}{"p值":>9}{"R²(4f)":>9}{"R²(5f)":>9}{"ΔR²":>10}{"增量p":>8}{"显著":>6}')
    for r in results:
        tag = '5年' if r['start'].startswith('2021') else '3年'
        sig = '显著*' if r['sent_p'] < 0.05 else ('边际' if r['sent_p'] < 0.10 else '不显著')
        table_lines.append(f'{r["name"]:<20}{tag:<6}{r["sent_coef"]:>+10.5f}{r["sent_t"]:>+8.2f}{r["sent_p"]:>9.4f}'
                           f'{r["r2_4"]:>9.4f}{r["r2_5"]:>9.4f}{r["dr2"]:>+10.6f}{r["p_inc"]:>8.4f}{sig:>6}')

    full = '\n'.join(blocks) + '\n\n' + '\n'.join(table_lines)
    print(full)

    out_path = os.path.join(OUT_DIR, f'小盘对照_{args.sentiment}_对比汇总.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(full + '\n')
    print(f'\n结果已保存: {out_path}')

    # 同时输出 CSV 便于制图
    csv_path = os.path.join(OUT_DIR, f'小盘对照_{args.sentiment}_对比汇总.csv')
    pd.DataFrame(results).to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f'CSV 已保存: {csv_path}')


if __name__ == '__main__':
    main()
