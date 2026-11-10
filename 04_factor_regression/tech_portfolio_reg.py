# -*- coding: utf-8 -*-
"""
纯科技股大小盘组合 × 情绪因子 Carhart 回归对比
被解释变量: 大盘/中盘/小盘 科技组合等权日收益
情绪因子: 模型法(FinBERT) / 词典法，板块级科技新闻情绪
输出: 12 条回归(2情绪源 × 2区间 × 3组合) 对比表
"""
import os, argparse
import pandas as pd
import numpy as np
import statsmodels.api as sm
from scipy.stats import f as fdist

FF3 = r'D:\大学（本科）\mth301\三因子模型指标(日)132201088(仅供西交利物浦大学使用)\STK_MKT_THRFACDAY.xlsx'
FF4 = r'D:\大学（本科）\mth301\STK_MKT_CARHARTFOURFACTORS.xlsx'
RF = r'D:\大学（本科）\mth301\无风险利率文件141014171(仅供西交利物浦大学使用)\TRD_Nrrate.xlsx'
SENT = {
    '模型': r'D:\mth301情绪因子\模型\日度情绪因子_模型.csv',
    '词典法': r'D:\mth301情绪因子\词典法\日度情绪因子_词典法.csv',
}
PORT = r'D:\mth301小盘对照\科技股组合_等权日收益.csv'
OUT_DIR = r'D:\mth301回归结果'
MARKET = 'P9714'

def read_csmar(path):
    return pd.read_excel(path, header=0, skiprows=[1, 2])

def run_reg(excess, X5, names):
    X5c = sm.add_constant(X5)
    kw = dict(cov_type='HAC', cov_kwds={'maxlags': max(1, int(len(excess) ** 0.5))})
    m = sm.OLS(excess, X5c).fit(**kw)
    return m

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sentiment', default='模型', choices=['模型', '词典法'])
    ap.add_argument('--start', default='2021-01-01')
    ap.add_argument('--end', default='2026-10-31')
    ap.add_argument('--lag', type=int, default=1)
    args = ap.parse_args()

    # 读组合收益
    port = pd.read_csv(PORT, encoding='utf-8-sig')
    port['date'] = pd.to_datetime(port['date'])

    # 读四因子
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

    # 合并
    df = port.merge(rf, left_on='date', right_on='Clsdt', how='left')
    df = df.merge(ff3, left_on='date', right_on='TradingDate', how='left')
    df['ym'] = df['date'].dt.strftime('%Y-%m')
    df = df.merge(ff4[['TradingMonth', 'UMD1']], left_on='ym', right_on='TradingMonth', how='left')
    df = df.merge(sent[['date', 'sentiment_mean']], on='date', how='left')
    df = df.sort_values('date').reset_index(drop=True)
    df['sent_lag'] = df['sentiment_mean'].shift(args.lag)
    df = df[(df['date'] >= args.start) & (df['date'] <= args.end)]

    groups = ['大盘', '中盘', '小盘']
    results = []
    print('=' * 90)
    print(f'纯科技股组合 × 情绪因子 Carhart 回归（{args.sentiment}，{args.start}~{args.end}）')
    print(f'对照: 大盘科技(≥122亿) vs 中盘(47~122亿) vs 小盘(<47亿)，等权组合')
    print('=' * 90)
    for g in groups:
        sub = df.dropna(subset=[g + '_ret', 'RiskPremium1', 'SMB1', 'HML1', 'UMD1', 'sent_lag'])
        # 东财涨跌幅是百分数(2.51=2.51%)，除以100转成小数，与CSMAR ReturnDaily(0.0251)同口径
        y = (sub[g + '_ret'].to_numpy() - sub['Nrrdaydt'].to_numpy()) / 100
        X4 = sub[['RiskPremium1', 'SMB1', 'HML1', 'UMD1']].to_numpy()
        X5 = sub[['RiskPremium1', 'SMB1', 'HML1', 'UMD1', 'sent_lag']].to_numpy()
        m4 = run_reg(y, X4, None)
        m5 = run_reg(y, X5, None)
        dr2 = m5.rsquared - m4.rsquared
        t_sent = m5.tvalues[-1]
        p_sent = m5.pvalues[-1]
        n = len(y)
        k5 = X5.shape[1] + 1
        f_inc = t_sent ** 2
        p_inc = fdist.sf(f_inc, 1, n - k5)
        results.append(dict(g=g, n=n, coef=m5.params[-1], t=t_sent, p=p_sent,
                            r2_4=m4.rsquared, r2_5=m5.rsquared, dr2=dr2, f_inc=f_inc, p_inc=p_inc))
        print(f'\n[{g}科技组合] 观测 {n}')
        print(f'  情绪系数 β5 = {m5.params[-1]:+.6f}  t = {t_sent:+.3f}  p = {p_sent:.4f}  '
              f'{"**显著**" if p_sent < 0.05 else "不显著"}')
        print(f'  R²(四因子)={m4.rsquared:.4f}  R²(五因子)={m5.rsquared:.4f}  ΔR²={dr2:.6f}  增量p={p_inc:.4f}')

    print('\n' + '=' * 90)
    print('对比汇总表')
    print('=' * 90)
    print(f'{"组合":<8}{"观测":>6}{"β5":>12}{"t":>9}{"p":>9}{"R²(四)":>10}{"R²(五)":>10}{"ΔR²":>10}{"增量p":>9}')
    for r in results:
        star = ' *' if r['p'] < 0.05 else ''
        print(f'{r["g"]:<8}{r["n"]:>6}{r["coef"]:>+12.6f}{r["t"]:>+9.3f}{r["p"]:>9.4f}'
              f'{r["r2_4"]:>10.4f}{r["r2_5"]:>10.4f}{r["dr2"]:>10.6f}{r["p_inc"]:>9.4f}{star}')
    print('\n* = p<0.05')

    # 保存 CSV
    os.makedirs(OUT_DIR, exist_ok=True)
    out_csv = os.path.join(OUT_DIR, f'科技组合_{args.sentiment}_{args.start}_{args.end}_对比.csv')
    pd.DataFrame(results).to_csv(out_csv, index=False, encoding='utf-8-sig')
    print(f'\n已保存: {out_csv}')

if __name__ == '__main__':
    main()
