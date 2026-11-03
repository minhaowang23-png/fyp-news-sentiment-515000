#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Carhart 四因子 + 新闻情绪因子 时间序列回归（515000 科技 ETF）

模型:  R_it - Rf = α + β1*MKT + β2*SMB + β3*HML + β4*UMD + β5*Sentiment_{t-1} + ε

说明:
  - 被解释变量: 515000 超额日收益 = ReturnDaily - Nrrdaydt/100
  - 因子: MKT/SMB/HML 用日频三因子；UMD(动量) 用月频四因子表，按月填充到日频
  - 情绪因子滞后一期（Sentiment_{t-1}）
  - 标准误用 Newey-West(HAC)，修正残差自相关

用法:
  python regression.py --sentiment 模型 --start 2021-01-01 --end 2026-10-31
  python regression.py --sentiment 词典法 --start 2023-10-01 --end 2026-10-31

  输出: D:\\mth301回归结果\\<sentiment>_<start>_<end>_回归结果.txt
"""
import os
import argparse
import pandas as pd
import numpy as np
import statsmodels.api as sm

FUND = r'D:\大学（本科）\mth301\FUND_MKT_Quotation.xlsx'
FF3 = r'D:\大学（本科）\mth301\三因子模型指标(日)132201088(仅供西交利物浦大学使用)\STK_MKT_THRFACDAY.xlsx'
FF4 = r'D:\大学（本科）\mth301\STK_MKT_CARHARTFOURFACTORS.xlsx'
RF = r'D:\大学（本科）\mth301\无风险利率文件141014171(仅供西交利物浦大学使用)\TRD_Nrrate.xlsx'
SENT = {
    '模型': r'D:\mth301情绪因子\模型\日度情绪因子_模型.csv',
    '词典法': r'D:\mth301情绪因子\词典法\日度情绪因子_词典法.csv',
}
OUT_DIR = r'D:\mth301回归结果'
# P9714 = 沪深A股+创业板+科创板（515000 科技龙头 ETF 成分横跨主板/创业板/科创板，用全市场因子）
MARKET = 'P9714'


def read_csmar(path):
    """读 CSMAR xlsx：第一行英文列名作表头，跳过中文行和单位行。"""
    return pd.read_excel(path, header=0, skiprows=[1, 2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sentiment', default='模型', choices=['模型', '词典法'])
    ap.add_argument('--market', default=MARKET)
    ap.add_argument('--start', default='2021-01-01')
    ap.add_argument('--end', default='2026-10-31')
    ap.add_argument('--lag', type=int, default=1, help='情绪滞后阶数')
    args = ap.parse_args()

    # 1. 读数据
    fund = read_csmar(FUND)
    fund = fund[fund['Symbol'] == 515000][['TradingDate', 'ReturnDaily', 'ClosePrice']].copy()
    fund['TradingDate'] = pd.to_datetime(fund['TradingDate'])

    ff3 = read_csmar(FF3)
    ff3 = ff3[ff3['MarkettypeID'] == args.market][['TradingDate', 'RiskPremium1', 'SMB1', 'HML1']].copy()
    ff3['TradingDate'] = pd.to_datetime(ff3['TradingDate'])

    ff4 = read_csmar(FF4)
    ff4 = ff4[ff4['MarkettypeID'] == args.market][['TradingMonth', 'UMD1']].copy()
    ff4['TradingMonth'] = ff4['TradingMonth'].astype(str).str.strip()

    rf = read_csmar(RF)[['Clsdt', 'Nrrdaydt']].copy()
    rf['Clsdt'] = pd.to_datetime(rf['Clsdt'])

    sent = pd.read_csv(SENT[args.sentiment])
    sent['date'] = pd.to_datetime(sent['date'])

    # 2. 合并
    df = fund.merge(rf, left_on='TradingDate', right_on='Clsdt', how='left')
    df = df.merge(ff3, on='TradingDate', how='left')
    df['ym'] = df['TradingDate'].dt.strftime('%Y-%m')
    df = df.merge(ff4[['TradingMonth', 'UMD1']], left_on='ym', right_on='TradingMonth', how='left')
    df = df.merge(sent[['date', 'sentiment_mean']], left_on='TradingDate', right_on='date', how='left')

    # 3. 超额收益 + 情绪滞后
    df['excess'] = df['ReturnDaily'] - df['Nrrdaydt'] / 100
    df = df.sort_values('TradingDate').reset_index(drop=True)
    df['sent_lag'] = df['sentiment_mean'].shift(args.lag)

    # 4. 样本区间
    df = df[(df['TradingDate'] >= args.start) & (df['TradingDate'] <= args.end)]
    df = df.dropna(subset=['excess', 'RiskPremium1', 'SMB1', 'HML1', 'UMD1', 'sent_lag'])

    print(f'样本: {args.start} ~ {args.end}，观测数 {len(df)}，情绪源 {args.sentiment}，市场 {args.market}')
    if len(df) < 30:
        print('观测数不足，无法回归')
        return

    # 5. 回归：基准四因子 vs 扩展五因子（Newey-West HAC）
    y = df['excess'].to_numpy()
    X4 = df[['RiskPremium1', 'SMB1', 'HML1', 'UMD1']].to_numpy()
    X5 = df[['RiskPremium1', 'SMB1', 'HML1', 'UMD1', 'sent_lag']].to_numpy()
    X4c = sm.add_constant(X4)
    X5c = sm.add_constant(X5)
    kw = dict(cov_type='HAC', cov_kwds={'maxlags': max(1, int(len(df) ** 0.5))})
    m4 = sm.OLS(y, X4c).fit(**kw)
    m5 = sm.OLS(y, X5c).fit(**kw)

    names4 = ['alpha(常数)', 'MKT', 'SMB', 'HML', 'UMD(动量)']
    names5 = names4 + [f'Sentiment_lag{args.lag}']

    n = len(df)
    k5 = X5c.shape[1]
    dr2 = m5.rsquared - m4.rsquared
    dr2_adj = m5.rsquared_adj - m4.rsquared_adj
    # 增量 F 检验（单约束，HAC 稳健下等价于情绪系数 t 的平方）
    t_sent = m5.tvalues[-1]
    f_inc = t_sent ** 2
    from scipy.stats import f as fdist
    p_inc = fdist.sf(f_inc, 1, n - k5)

    def fmt_coef(m, names):
        out = [f'{"变量":<16}{"系数":>12}{"标准误":>12}{"t值":>10}{"p值":>10}']
        for i, nm in enumerate(names):
            out.append(f'{nm:<16}{m.params[i]:>12.6f}{m.bse[i]:>12.6f}'
                       f'{m.tvalues[i]:>10.3f}{m.pvalues[i]:>10.4f}')
        return out

    lines = []
    lines.append('=' * 70)
    lines.append('Carhart 四因子 vs 四因子+情绪因子 时间序列回归（515000 科技ETF）')
    lines.append(f'样本区间: {args.start} ~ {args.end}   观测数: {n}')
    lines.append(f'情绪源: {args.sentiment}   滞后: {args.lag}期   市场类型: {args.market}')
    lines.append(f'标准误: Newey-West HAC (maxlags={int(n**0.5)})')
    lines.append('=' * 70)

    lines.append('\n【基准模型】Carhart 四因子 (MKT/SMB/HML/UMD)')
    lines += fmt_coef(m4, names4)
    lines.append(f'R² = {m4.rsquared:.4f}   调整R² = {m4.rsquared_adj:.4f}')

    lines.append('\n【扩展模型】四因子 + 情绪因子')
    lines += fmt_coef(m5, names5)
    lines.append(f'R² = {m5.rsquared:.4f}   调整R² = {m5.rsquared_adj:.4f}')

    lines.append('\n【情绪因子的增量贡献（加入前后对比）】')
    lines.append(f'ΔR² = R²(五因子) - R²(四因子) = {dr2:.6f}')
    lines.append(f'Δ调整R² = {dr2_adj:.6f}')
    lines.append(f'增量F检验 = {f_inc:.4f}   p值 = {p_inc:.4f}   （单约束，HAC稳健，等价于情绪系数t²={t_sent:.2f}²）')
    lines.append(f'情绪因子系数 = {m5.params[-1]:.6f}  t = {t_sent:.3f}  p = {m5.pvalues[-1]:.4f}')
    lines.append(f'情绪因子均值 = {df["sent_lag"].mean():.4f}，系数×均值(经济显著性) = {m5.params[-1]*df["sent_lag"].mean():.6f}')
    lines.append('-' * 70)
    lines.append('解读：ΔR² 表示情绪因子在四因子之上额外解释的收益方差比例；'
                 '若增量F检验 p<0.05 则情绪因子有显著增量预测力，否则无。')

    text = '\n'.join(lines)
    print(text)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f'{args.sentiment}_{args.start}_{args.end}_回归结果.txt')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(text + '\n')
    print(f'\n结果已保存: {out_path}')


if __name__ == '__main__':
    main()
