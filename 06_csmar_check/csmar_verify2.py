# -*- coding: utf-8 -*-
import os, time
import pandas as pd

MTH = None
for drv in ['D:/', 'C:/']:
    try:
        for e in os.listdir(drv):
            if '大学' in e:
                c = os.path.join(drv, e, 'mth301')
                if os.path.isdir(c):
                    MTH = c; break
    except Exception:
        pass
    if MTH: break
OUT = os.path.join(MTH, '_extract')

def find_entry(sub):
    for e in os.listdir(MTH):
        if sub in e:
            return e
    return None

def read_clean(path, usecols=None):
    raw = pd.read_excel(path, header=None, usecols=usecols)
    en = raw.iloc[0].tolist()          # 英文列名
    data = raw.iloc[3:].copy()         # 跳过 英文/中文/没有单位 三行
    data.columns = en
    return data

print('################ 因子类(小文件) ################')
factor_files = {
    'Carhart四因子(月)': os.path.join(OUT, 'STK_MKT_CARHARTFOURFACTORS.xlsx'),
    '三因子(日)': os.path.join(MTH, find_entry('132201088'), 'STK_MKT_THRFACDAY.xlsx'),
    '三因子(周)': os.path.join(OUT, 'STK_MKT_THRFACWEEK.xlsx'),
    '三因子(月)': os.path.join(OUT, 'STK_MKT_THRFACMONTH.xlsx'),
    '动量(月)': os.path.join(MTH, find_entry('134712866'), 'STK_MKT_MOMENTUM.xlsx'),
    '无风险利率': os.path.join(MTH, find_entry('141014171'), 'TRD_Nrrate.xlsx'),
    '基金日行情': os.path.join(OUT, 'FUND_MKT_Quotation.xlsx'),
}
for name, p in factor_files.items():
    if not os.path.exists(p):
        print(name, '缺失'); continue
    t0 = time.time()
    df = read_clean(p)
    # 识别日期列
    datecol = None
    for c in df.columns:
        if any(k in str(c) for k in ['Date', 'Month', 'Clsdt', 'Nrr']):
            datecol = c; break
    if datecol is None:
        datecol = df.columns[0]
    # 仅保留日期为数值/字符串日期的行
    d = df[df[datecol].astype(str).str.match(r'^\d{4}')]
    print('【%s】 行数=%d  列=%s' % (name, len(d), list(df.columns)[:6]))
    print('   日期列=%s  范围=%s ~ %s' % (datecol, d[datecol].min(), d[datecol].max()))
    if 'MarkettypeID' in df.columns:
        print('   MarkettypeID取值:', sorted(d['MarkettypeID'].astype(str).unique())[:12])
    if 'Symbol' in df.columns:
        print('   Symbol唯一数=%d 含515000=%s' % (d['Symbol'].nunique(), (d['Symbol'].astype(str)=='515000').any()))
    print('   耗时%.1fs' % (time.time()-t0))

print()
print('################ 文本/投资者情绪(股吧) 时间覆盖 ################')
text_ids = ['133910906','134026159','134118365','134119581','134233081','134407777']
inv_ids  = ['132553233','132855889','133110401','133503093','133636952','133638967']

def sent_info(path, label):
    t0 = time.time()
    raw = pd.read_excel(path, header=None, usecols=[0,1])  # PostDate, Stockcode
    en = raw.iloc[0].tolist()
    data = raw.iloc[3:].copy(); data.columns = en
    d = data[data[en[0]].astype(str).str.match(r'^\d{4}-\d{2}-\d{2}')]
    mn, mx = d[en[0]].min(), d[en[0]].max()
    sc = d[en[1]].astype(str)
    nsc = sc.nunique()
    etf = sc[sc.str.startswith('51')].nunique()
    print('【%s】 行数=%d 日期 %s~%s 股票数=%d 51开头=%d 含515000=%s 耗时%.1fs'
          % (label, len(d), mn, mx, nsc, etf, (sc=='515000').any(), time.time()-t0))

for tid in text_ids:
    fe = find_entry(tid)
    sent_info(os.path.join(MTH, fe, 'XQ_TextSentimentSta.xlsx'), '文本情绪'+tid)
for iid in inv_ids:
    fe = find_entry(iid)
    sent_info(os.path.join(MTH, fe, 'XQ_InvestorSentimentSta.xlsx'), '投资者情绪'+iid)

print('\n=== DONE ===')
