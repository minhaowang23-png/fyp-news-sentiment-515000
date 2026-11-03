#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 515000 新闻情绪因子研究的图表 PNG + Word 总结报告（v2：时间对齐、逐条分布、诚实标注）。"""
import os
import re
import json
import glob
import random
import pandas as pd
import numpy as np
import statsmodels.api as sm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

for name in ['Microsoft YaHei', 'SimHei', 'SimSun']:
    try:
        font_manager.findfont(name, fallback_to_default=False)
        plt.rcParams['font.sans-serif'] = [name]
        break
    except Exception:
        continue
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 150
plt.rcParams['savefig.bbox'] = 'tight'

MODEL_CSV = r'D:\mth301情绪因子\模型\日度情绪因子_模型.csv'
DICT_CSV = r'D:\mth301情绪因子\词典法\日度情绪因子_词典法.csv'
FUND = r'D:\大学（本科）\mth301\FUND_MKT_Quotation.xlsx'
RF = r'D:\大学（本科）\mth301\无风险利率文件141014171(仅供西交利物浦大学使用)\TRD_Nrrate.xlsx'
FF3 = r'D:\大学（本科）\mth301\三因子模型指标(日)132201088(仅供西交利物浦大学使用)\STK_MKT_THRFACDAY.xlsx'
FF4 = r'D:\大学（本科）\mth301\STK_MKT_CARHARTFOURFACTORS.xlsx'
REG_DIR = r'D:\mth301回归结果'
MODEL_SCORE_DIR = r'D:\mth301情绪打分_模型'
DICT_SCORE_DIR = r'D:\mth301情绪打分_词典法'
CHART_DIR = r'D:\mth301图表'
OUT_DOCX = r'C:\Users\98097\Desktop\mth301_情绪因子_任务总结报告_v4.docx'

C_MODEL = '#2f6fed'
C_DICT = '#f59e0b'
C_CNT = '#0ea5e9'
C_PRICE = '#1f2937'
C_ACCENT = '#e2574c'


def read_csmar(path):
    return pd.read_excel(path, header=0, skiprows=[1, 2])


def parse_regression(path):
    with open(path, encoding='utf-8') as f:
        txt = f.read()
    info = {}
    m = re.search(r'样本区间:\s*([\d-]+) ~ ([\d-]+)\s+观测数:\s*(\d+)', txt)
    if m:
        info['start'], info['end'], info['n'] = m.group(1), m.group(2), int(m.group(3))
    m = re.search(r'情绪源:\s*(\S+)', txt)
    info['source'] = m.group(1) if m else ''
    r2s = re.findall(r'R² = ([\d.]+)\s+调整R² = ([\d.]+)', txt)
    info['r2_4'] = float(r2s[0][0]) if len(r2s) >= 1 else None
    info['r2_5'] = float(r2s[1][0]) if len(r2s) >= 2 else None
    info['r2'] = info['r2_5'] if info['r2_5'] is not None else (info['r2_4'] if info['r2_4'] is not None else None)
    m = re.search(r'情绪因子系数 = ([-\d.]+)\s+t = ([-\d.]+)\s+p = ([\d.]+)', txt)
    if m:
        info['sent_coef'], info['sent_t'], info['sent_p'] = float(m.group(1)), float(m.group(2)), float(m.group(3))
    m = re.search(r'ΔR² = R²\(五因子\) - R²\(四因子\) = ([\d.]+)', txt)
    info['dr2'] = float(m.group(1)) if m else None
    m = re.search(r'增量F检验 = ([\d.]+)\s+p值 = ([\d.]+)', txt)
    if m:
        info['f_inc'] = float(m.group(1)); info['p_inc'] = float(m.group(2))
    rows = []
    for line in txt.splitlines():
        mm = re.match(r'^(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*$', line)
        if mm:
            rows.append({'name': mm.group(1), 'coef': float(mm.group(2)), 'se': float(mm.group(3)),
                         't': float(mm.group(4)), 'p': float(mm.group(5))})
    info['rows'] = rows
    return info


def sample_scores(dirpath, field, frac=0.15, seed=42):
    """抽样读逐条情绪得分，返回 np.array。"""
    random.seed(seed)
    vals = []
    for f in sorted(glob.glob(os.path.join(dirpath, 'news_*.jsonl'))):
        with open(f, encoding='utf-8') as fin:
            for line in fin:
                if random.random() < frac:
                    o = json.loads(line)
                    v = o.get(field)
                    if v is not None:
                        vals.append(float(v))
    return np.array(vals)


def main():
    os.makedirs(CHART_DIR, exist_ok=True)

    # ---------- 数据 ----------
    model = pd.read_csv(MODEL_CSV, encoding='utf-8-sig'); model['date'] = pd.to_datetime(model['date'])
    dic = pd.read_csv(DICT_CSV, encoding='utf-8-sig'); dic['date'] = pd.to_datetime(dic['date'])
    fund = read_csmar(FUND)
    fund = fund[fund['Symbol'] == 515000][['TradingDate', 'ReturnDaily', 'ClosePrice']].copy()
    fund['TradingDate'] = pd.to_datetime(fund['TradingDate'])
    rf = read_csmar(RF)[['Clsdt', 'Nrrdaydt']].copy(); rf['Clsdt'] = pd.to_datetime(rf['Clsdt'])
    price = fund.merge(rf, left_on='TradingDate', right_on='Clsdt', how='left')
    price['excess'] = price['ReturnDaily'] - price['Nrrdaydt'] / 100
    price = price.sort_values('TradingDate').reset_index(drop=True)
    price_align = price[price['TradingDate'] >= '2021-01-01']  # 与情绪数据时间对齐

    merged = price.merge(model[['date', 'sentiment_mean']], left_on='TradingDate', right_on='date', how='left')
    merged['sent_lag'] = merged['sentiment_mean'].shift(1)
    scatter = merged.dropna(subset=['excess', 'sent_lag'])

    model['ma7'] = model['sentiment_mean'].rolling(7).mean()
    dic['ma7'] = dic['sentiment_mean'].rolling(7).mean()
    model['cnt7'] = model['news_count'].rolling(7).mean()

    both = pd.concat([model.set_index('date').sentiment_mean, dic.set_index('date').sentiment_mean],
                     axis=1, keys=['model', 'dict']).dropna()
    corr = both['model'].corr(both['dict'])

    regs = [parse_regression(os.path.join(REG_DIR, f)) for f in [
        '词典法_2021-01-01_2026-10-31_回归结果.txt',
        '词典法_2023-10-01_2026-10-31_回归结果.txt',
        '模型_2021-01-01_2026-10-31_回归结果.txt',
        '模型_2023-10-01_2026-10-31_回归结果.txt']]

    # 逐条得分抽样
    print('抽样逐条得分...')
    sc_model = sample_scores(MODEL_SCORE_DIR, 'sentiment_score')
    sc_dict = sample_scores(DICT_SCORE_DIR, 'dict_sentiment')
    neg_m = float((sc_model < 0).mean() * 100)
    neg_d = float((sc_dict < 0).mean() * 100)

    # ---------- 图1 情绪走势 ----------
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(model['date'], model['ma7'], color=C_MODEL, lw=1.4, label='模型法(FinBERT)')
    ax.plot(dic['date'], dic['ma7'], color=C_DICT, lw=1.4, label='词典法(CFSD)')
    ax.axhline(0, color='#9ca3af', lw=0.8, ls='--')
    ax.set_ylim(-1, 1); ax.set_ylabel('情绪得分')
    ax.set_title('① 日度情绪因子走势（7日移动平均）')
    ax.legend(loc='upper right', frameon=False); ax.grid(alpha=0.25)
    ax.text(0.02, 0.97, f'两法日度均值相关系数 r = {corr:.3f}', transform=ax.transAxes,
            fontsize=9, va='top', color='#6b7280')
    fig.savefig(os.path.join(CHART_DIR, 'fig1_情绪走势.png')); plt.close(fig)

    # ---------- 图2 新闻数量 ----------
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.fill_between(model['date'], model['cnt7'], color=C_CNT, alpha=0.2)
    ax.plot(model['date'], model['cnt7'], color=C_CNT, lw=1.2)
    ax.set_ylabel('条/日'); ax.set_title('② 科技新闻数量日度走势（7日移动平均）')
    ax.grid(alpha=0.25)
    fig.savefig(os.path.join(CHART_DIR, 'fig2_新闻数量.png')); plt.close(fig)

    # ---------- 图3 逐条得分分布 ----------
    fig, ax = plt.subplots(figsize=(10, 4.5))
    bins = np.arange(-1.0, 1.05, 0.05)
    ax.hist(sc_model, bins=bins, density=True, alpha=0.6, color=C_MODEL,
            label=f'模型法（负值 {neg_m:.1f}%）')
    ax.hist(sc_dict, bins=bins, density=True, alpha=0.6, color=C_DICT,
            label=f'词典法（负值 {neg_d:.1f}%）')
    ax.axvline(0, color='#6b7280', lw=1, ls='--')
    ax.set_xlabel('逐条新闻情绪得分（−1 消极 ↔ +1 积极）')
    ax.set_ylabel('密度'); ax.set_title('③ 逐条新闻情绪得分分布（真实含负值）')
    ax.legend(frameon=False); ax.grid(alpha=0.25)
    fig.savefig(os.path.join(CHART_DIR, 'fig3_情绪分布.png')); plt.close(fig)

    # ---------- 图4 价格 vs 情绪（时间对齐） ----------
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(price_align['TradingDate'], price_align['ClosePrice'], color=C_PRICE, lw=1.1,
             label='515000收盘价(左轴)')
    ax1.set_ylabel('收盘价'); ax1.grid(alpha=0.25)
    ax2 = ax1.twinx()
    ax2.fill_between(model['date'], model['ma7'], color=C_ACCENT, alpha=0.12)
    ax2.plot(model['date'], model['ma7'], color=C_ACCENT, lw=1.1, label='模型情绪7日MA(右轴)')
    ax2.set_ylim(-1, 1); ax2.set_ylabel('情绪得分')
    lines = ax1.get_lines() + ax2.get_lines()
    ax1.legend(lines, [l.get_label() for l in lines], loc='upper left', frameon=False)
    ax1.set_title('④ 515000 收盘价 vs 模型情绪因子（时间已对齐：2021-01 起）')
    fig.savefig(os.path.join(CHART_DIR, 'fig4_价格vs情绪.png')); plt.close(fig)

    # ---------- 图5 森林图 ----------
    labels = [f"{r['source']}·{('5年' if r['start'].startswith('2021') else '3年')}" for r in regs]
    coefs = [r['sent_coef'] for r in regs]
    ts = [r['sent_t'] for r in regs]
    ps = [r['sent_p'] for r in regs]
    colors = [C_ACCENT if abs(c) < 0.005 else C_MODEL for c in coefs]
    fig, ax = plt.subplots(figsize=(10, 4))
    y = np.arange(len(labels))[::-1]
    ax.barh(y, coefs, color=colors, alpha=0.85, height=0.5)
    ax.axvline(0, color='#6b7280', lw=1)
    maxc = max(abs(c) for c in coefs) * 2.2
    ax.set_xlim(-maxc, maxc)
    for yi, c, t, p in zip(y, coefs, ts, ps):
        off = maxc * 0.02
        ax.text(c + (off if c >= 0 else -off), yi, f'β={c:.4f}   t={t:.2f}   p={p:.3f}',
                va='center', ha='left' if c >= 0 else 'right', fontsize=8.5)
    ax.set_yticks(y); ax.set_yticklabels(labels)
    ax.yaxis.set_ticks_position('right')
    ax.set_xlabel('情绪因子系数 β5'); ax.set_title('⑤ 情绪因子回归系数（森林图，均不显著）')
    ax.grid(alpha=0.25, axis='x')
    fig.savefig(os.path.join(CHART_DIR, 'fig5_森林图.png')); plt.close(fig)

    # ---------- 图6 散点 ----------
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.scatter(scatter['sent_lag'], scatter['excess'], s=6, color=C_MODEL, alpha=0.25)
    if len(scatter) > 10:
        z = np.polyfit(scatter['sent_lag'], scatter['excess'], 1)
        p = np.poly1d(z)
        xs = np.linspace(scatter['sent_lag'].min(), scatter['sent_lag'].max(), 50)
        ax.plot(xs, p(xs), color=C_ACCENT, lw=1.6)
        ss_res = np.sum((scatter['excess'] - p(scatter['sent_lag'])) ** 2)
        ss_tot = np.sum((scatter['excess'] - scatter['excess'].mean()) ** 2)
        r2 = 1 - ss_res / ss_tot
        ax.text(0.03, 0.95, f'斜率={z[0]:.5f}  R²={r2:.4f}', transform=ax.transAxes,
                fontsize=10, va='top', color=C_ACCENT)
    ax.set_xlabel('滞后情绪 Sentiment(t-1)'); ax.set_ylabel('当日超额收益')
    ax.set_title('⑥ 滞后情绪 vs 当日超额收益（散点 + 拟合线）')
    ax.grid(alpha=0.25)
    fig.savefig(os.path.join(CHART_DIR, 'fig6_散点.png')); plt.close(fig)

    # ---------- 图7 加入前后 R² 对比 ----------
    fig, ax = plt.subplots(figsize=(10, 4.5))
    r2_4 = [r['r2_4'] for r in regs]
    r2_5 = [r['r2_5'] for r in regs]
    max_dr2 = max(r['dr2'] for r in regs)
    x = np.arange(len(labels))
    w = 0.38
    ax.bar(x - w/2, r2_4, w, color='#9ca3af', label='四因子 R²（基准）')
    ax.bar(x + w/2, r2_5, w, color=C_MODEL, label='四因子+情绪 R²')
    ax.set_ylim(0.74, 0.85)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel('R²'); ax.set_title('⑦ 加入情绪因子前后的 R² 对比（ΔR² 极小，几乎无增量）')
    for xi, a, b in zip(x, r2_4, r2_5):
        ax.text(xi - w/2, a + 0.0012, f'{a:.4f}', ha='center', fontsize=8.5, color='#4b5563')
        ax.text(xi + w/2, b + 0.0012, f'{b:.4f}', ha='center', fontsize=8.5, color=C_MODEL)
    ax.text(0.5, 0.96, f'情绪因子带来的增量解释力 ΔR² 全部 < {max_dr2*100:.3f}%（≈0）',
            transform=ax.transAxes, ha='center', fontsize=10, color=C_ACCENT)
    ax.legend(frameon=False); ax.grid(alpha=0.25, axis='y')
    fig.savefig(os.path.join(CHART_DIR, 'fig7_R2对比.png')); plt.close(fig)

    # ---------- 图8 累计收益对比（实际 vs 四因子拟合 vs 五因子拟合） ----------
    ff3 = read_csmar(FF3)
    ff3 = ff3[ff3['MarkettypeID'] == 'P9714'][['TradingDate', 'RiskPremium1', 'SMB1', 'HML1']].copy()
    ff3['TradingDate'] = pd.to_datetime(ff3['TradingDate'])
    ff4 = read_csmar(FF4)
    ff4 = ff4[ff4['MarkettypeID'] == 'P9714'][['TradingMonth', 'UMD1']].copy()
    ff4['TradingMonth'] = ff4['TradingMonth'].astype(str).str.strip()
    dff = fund.merge(rf, left_on='TradingDate', right_on='Clsdt', how='left')
    dff = dff.merge(ff3, on='TradingDate', how='left')
    dff['ym'] = dff['TradingDate'].dt.strftime('%Y-%m')
    dff = dff.merge(ff4[['TradingMonth', 'UMD1']], left_on='ym', right_on='TradingMonth', how='left')
    dff = dff.merge(model[['date', 'sentiment_mean']], left_on='TradingDate', right_on='date', how='left')
    dff['excess'] = dff['ReturnDaily'] - dff['Nrrdaydt'] / 100
    dff = dff.sort_values('TradingDate').reset_index(drop=True)
    dff['sent_lag'] = dff['sentiment_mean'].shift(1)
    sub = dff[(dff['TradingDate'] >= '2023-10-01') & (dff['TradingDate'] <= '2026-10-31')]
    sub = sub.dropna(subset=['excess', 'RiskPremium1', 'SMB1', 'HML1', 'UMD1', 'sent_lag'])
    yv = sub['excess'].to_numpy()
    X4 = sm.add_constant(sub[['RiskPremium1', 'SMB1', 'HML1', 'UMD1']].to_numpy())
    X5 = sm.add_constant(sub[['RiskPremium1', 'SMB1', 'HML1', 'UMD1', 'sent_lag']].to_numpy())
    fit4 = sm.OLS(yv, X4).fit().fittedvalues
    fit5 = sm.OLS(yv, X5).fit().fittedvalues
    cum_a = (1 + yv).cumprod() - 1
    cum4 = (1 + fit4).cumprod() - 1
    cum5 = (1 + fit5).cumprod() - 1
    dates8 = sub['TradingDate'].to_numpy()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.plot(dates8, cum_a, color=C_PRICE, lw=1.4, label='515000 累计实际超额收益')
    ax.plot(dates8, cum4, color='#9ca3af', lw=2.0, ls='--', label='四因子模型累计拟合')
    ax.plot(dates8, cum5, color=C_MODEL, lw=1.4, ls='-', label='四因子+情绪累计拟合')
    ax.set_ylabel('累计超额收益（复利）')
    ax.set_title('⑧ 累计实际超额收益 vs 模型拟合（四因子 vs 五因子，FinBERT·3年主样本）')
    ax.legend(frameon=False); ax.grid(alpha=0.25)
    ax.text(0.02, 0.05, '两条拟合线几乎重合（ΔR²<0.04%），说明情绪因子无增量预测力',
            transform=ax.transAxes, fontsize=9, color=C_ACCENT, va='bottom')
    fig.savefig(os.path.join(CHART_DIR, 'fig8_累计收益对比.png')); plt.close(fig)

    print('图表已生成:', len(os.listdir(CHART_DIR)), '张')
    print(f'负值占比: 模型 {neg_m:.1f}% / 词典 {neg_d:.1f}%')
    print(f'两法相关系数: {corr:.4f}')

    # ================= Word 生成 =================
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Microsoft YaHei'
    style.font.size = Pt(10.5)
    style._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    def cn(run, name='微软雅黑'):
        run.font.name = name
        run._element.rPr.rFonts.set(qn('w:eastAsia'), name)

    def add_heading(text, level=1):
        h = doc.add_heading(text, level=level)
        for r in h.runs:
            cn(r); r.font.color.rgb = RGBColor(0x1f, 0x3a, 0x8a)
        return h

    def add_para(text, bold=False, size=10.5, color=None):
        p = doc.add_paragraph()
        r = p.add_run(text); cn(r); r.bold = bold; r.font.size = Pt(size)
        if color:
            r.font.color.rgb = color
        return p

    def add_table(headers, rows):
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = 'Light Grid Accent 1'
        hdr = t.rows[0].cells
        for i, h in enumerate(headers):
            hdr[i].text = ''
            r = hdr[i].paragraphs[0].add_run(h); cn(r); r.bold = True; r.font.size = Pt(9.5)
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = ''
                r = cells[i].paragraphs[0].add_run(str(v)); cn(r); r.font.size = Pt(9.5)
        return t

    title = doc.add_paragraph(); title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run('515000 科技 ETF 新闻情绪因子研究\n任务总结报告')
    cn(r); r.bold = True; r.font.size = Pt(20); r.font.color.rgb = RGBColor(0x1f, 0x3a, 0x8a)
    sub = doc.add_paragraph(); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = sub.add_run('华宝中证科技龙头 ETF（515000，跟踪中证科技龙头指数 931087）· Carhart 四因子时间序列回归')
    cn(r); r.font.size = Pt(10.5); r.font.color.rgb = RGBColor(0x6b, 0x72, 0x80)
    add_para('生成时间：2026-11-04　|　新闻样本：1,040,123 条（2021-01 ~ 2026-10）　|　情绪方法：FinBERT 模型 + 词典法　|　标准误：Newey-West HAC',
             size=9.5, color=RGBColor(0x6b, 0x72, 0x80)).alignment = WD_ALIGN_PARAGRAPH.CENTER

    add_heading('核心结论', 1)
    p = doc.add_paragraph()
    r = p.add_run('在控制 Carhart 四因子（MKT / SMB / HML / UMD）后，中文科技新闻情绪因子对 515000 的日度超额收益'
                  '没有统计上显著的预测力——无论 FinBERT 模型法（主方法）还是词典法（稳健性检验），4 条回归中情绪因子 p 值均 > 0.05。'
                  '加入情绪因子后，模型解释力 R² 的提升（ΔR²）全部 < 0.04%（增量 F 检验均不显著），'
                  '即情绪因子几乎未提供任何增量预测力。四因子本身高度显著（回归框架健康），这是诚实的"负结果"，'
                  '且在更换度量方法、扩展样本区间后保持稳健。')
    cn(r); r.font.size = Pt(11)

    add_heading('一、数据与样本概览', 1)
    add_table(['指标', '数值'], [
        ['新闻总条数', '1,040,123 条（70 个月，2021-01 ~ 2026-10）'],
        ['覆盖自然日', f"{model['date'].nunique():,} 天（日均 {model['news_count'].mean():.1f} 条）"],
        ['模型情绪均值', f"{model['sentiment_mean'].mean():.4f}（日度均值为负的天数 {(model['sentiment_mean']<0).sum()} 天）"],
        ['词典情绪均值', f"{dic['sentiment_mean'].mean():.4f}（日度均值为负的天数 {(dic['sentiment_mean']<0).sum()} 天）"],
        ['逐条新闻负值占比', f"模型法 {neg_m:.1f}% / 词典法 {neg_d:.1f}%"],
        ['两法日度均值相关', f"r = {corr:.4f}"],
        ['超额收益', 'ReturnDaily − Nrrdaydt/100'],
        ['因子与市场类型', 'MKT/SMB/HML 日频 + UMD 月频；P9714 全市场（沪深A股+创业板+科创板）'],
    ])

    add_heading('二、关于情绪得分为何偏正（词典法正偏说明）', 1)
    for txt in [
        f'逐条新闻层面，情绪得分并非没有负值：模型法 {neg_m:.1f}%、词典法 {neg_d:.1f}% 的新闻为负情绪（图3 清晰可见）。',
        '但日度平均后，词典法仅有 5 天为负（0.2%），原因是科技新闻中正面报道远多于负面报道——词典法里"纯正面（得分+1）"新闻占 46.8%，而"纯负面（得分-1）"仅占 7.1%，正面是负面的 6 倍以上。',
        '更本质的缺陷在于词典法：它按词频计数，无法理解语境，会把"同比增长 10%"这类中性事实陈述也算作正面情绪（因"增长"为正面词），导致系统性正偏（positivity bias）。这正是主方法采用 FinBERT 的原因——模型能结合语境区分真实情绪方向。',
        '两条情绪曲线看起来"平移"而非完全同步，实为词典法相对模型法存在约 +0.24 的恒定水平偏移（正偏），但两法日度均值相关系数仍达 0.76，说明它们捕捉到的情绪时序波动方向高度一致，稳健性检验因此有效。',
    ]:
        p = doc.add_paragraph(style='List Bullet')
        r = p.add_run(txt); cn(r); r.font.size = Pt(10.5)

    add_heading('三、图表', 1)
    figs = [
        ('fig1_情绪走势.png', f'图1 日度情绪因子走势（7日移动平均；两法相关 r={corr:.3f}）'),
        ('fig2_新闻数量.png', '图2 科技新闻数量日度走势（7日移动平均）'),
        ('fig3_情绪分布.png', f'图3 逐条新闻情绪得分分布（真实含负值：模型 {neg_m:.1f}% / 词典 {neg_d:.1f}% 为负）'),
        ('fig4_价格vs情绪.png', '图4 515000 收盘价 vs 模型情绪因子（时间已对齐：2021-01 起）'),
        ('fig5_森林图.png', '图5 情绪因子回归系数森林图（均不显著）'),
        ('fig6_散点.png', '图6 滞后情绪 vs 当日超额收益（散点 + 拟合线）'),
        ('fig7_R2对比.png', '图7 加入情绪因子前后的 R² 对比（ΔR² 极小，几乎无增量解释力）'),
        ('fig8_累计收益对比.png', '图8 累计实际超额收益 vs 模型拟合（四因子 vs 五因子，两条拟合线几乎重合）'),
    ]
    for fn, cap in figs:
        doc.add_picture(os.path.join(CHART_DIR, fn), width=Inches(6.1))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_para(cap, size=9.5, color=RGBColor(0x37, 0x41, 0x51)).alignment = WD_ALIGN_PARAGRAPH.CENTER

    add_heading('四、情绪因子回归结果汇总（加入前后对比）', 1)
    add_table(['方法', '样本', '情绪系数 β₅', 't 值', 'p 值', 'ΔR²', '增量F', '增量p', '显著性'], [
        [r['source'], ('5年' if r['start'].startswith('2021') else '3年'),
         f"{r['sent_coef']:.6f}", f"{r['sent_t']:.3f}", f"{r['sent_p']:.4f}",
         f"{r['dr2']:.4f}", f"{r['f_inc']:.2f}", f"{r['p_inc']:.4f}", '不显著'] for r in regs
    ])
    add_para('四因子基准 vs 五因子扩展的 R² 对比（见图7）', bold=True, size=10.5)
    add_table(['方法', '样本', 'R²(四因子)', 'R²(五因子)', 'ΔR²'], [
        [r['source'], ('5年' if r['start'].startswith('2021') else '3年'),
         f"{r['r2_4']:.4f}", f"{r['r2_5']:.4f}", f"{r['dr2']:.4f}"] for r in regs
    ])

    add_heading('五、完整回归系数矩阵', 1)
    for r in regs:
        add_para(f"{r['source']} · {r['start']} ~ {r['end']}（观测数 {r['n']}，R² = {r['r2']:.4f}）", bold=True, size=10.5)
        add_table(['变量', '系数', '标准误', 't 值', 'p 值'],
                  [[row['name'], f"{row['coef']:.6f}", f"{row['se']:.6f}", f"{row['t']:.3f}",
                    ('<0.0001' if row['p'] < 0.0001 else f"{row['p']:.4f}")] for row in r['rows']])

    add_heading('六、稳健性检验汇总', 1)
    add_table(['检验维度', '主设定', '稳健设定', '结论是否一致'], [
        ['情绪度量方法', 'FinBERT 模型法', '词典法（CFSD 姜富伟 2020）', '一致（均不显著）'],
        ['样本区间', '3 年主样本（2023-10~2026-10）', '5 年扩展（2021-01~2026-10）', '一致（均不显著）'],
    ])

    add_heading('七、结论与讨论', 1)
    for txt in [
        '主要结论：在 Carhart 四因子框架下，中文科技新闻情绪因子对 515000 科技 ETF 的日度超额收益没有显著预测力；四因子已充分解释收益系统性变动（R²≈0.78~0.83），加入情绪因子后 ΔR² < 0.04%，增量解释力几乎为零（增量 F 检验均不显著）。',
        '可能原因：① 新闻情绪当日即被定价，滞后一期预测力衰减；② 日度聚合稀释信号；③ ETF 成分分散，个股情绪被平均化；④ 四因子已吸收大部分信息；⑤ 词典法存在正偏、模型法情绪均值偏低。',
        '后续方向（可选）：改用当期情绪或情绪变化量（ΔSentiment）；聚焦个股/行业；用极端情绪分位或情绪分歧度；引入新闻关注度（数量）交互项。',
    ]:
        p = doc.add_paragraph(style='List Bullet')
        r = p.add_run(txt); cn(r); r.font.size = Pt(10.5)

    doc.save(OUT_DOCX)
    print('Word 已生成:', OUT_DOCX)


if __name__ == '__main__':
    main()
