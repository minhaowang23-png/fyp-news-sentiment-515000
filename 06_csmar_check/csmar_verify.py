# -*- coding: utf-8 -*-
import os, zipfile, time, openpyxl

def find_mth():
    for drv in ['D:/', 'C:/']:
        try:
            for e in os.listdir(drv):
                if '大学' in e:
                    cand = os.path.join(drv, e, 'mth301')
                    if os.path.isdir(cand):
                        return cand
        except Exception:
            pass
    return None

MTH = find_mth()
print('MTH =', MTH)
assert MTH, '未找到 mth301 目录'

OUT = os.path.join(MTH, '_extract')
os.makedirs(OUT, exist_ok=True)

entries = os.listdir(MTH)
def find_entry(substr):
    for e in entries:
        if substr in e:
            return e
    return None

# 抽取 5 个 GBK 乱码 zip 中的 ASCII 命名 xlsx
zip_targets = {
    '134755223': 'STK_MKT_CARHARTFOURFACTORS.xlsx',
    '140244518': 'FUND_MKT_Quotation.xlsx',
    '134857558': 'STK_MKT_THRFACWEEK.xlsx',
    '134930323': 'STK_MKT_THRFACMONTH.xlsx',
    '132553233': 'XQ_InvestorSentimentSta.xlsx',
}
print('=== 抽取 zip -> xlsx ===')
for zid, target in zip_targets.items():
    ze = find_entry(zid)
    if not ze:
        print('  缺失zip:', zid); continue
    zp = os.path.join(MTH, ze)
    with zipfile.ZipFile(zp) as z:
        for n in z.namelist():
            if os.path.basename(n) == target:
                with open(os.path.join(OUT, target), 'wb') as f:
                    f.write(z.read(n))
                print('  已抽取:', target); break

# 已解压文件夹(按数字ID)
folder_targets = {
    '132201088': 'STK_MKT_THRFACDAY.xlsx',    # 三因子(日)
    '134712866': 'STK_MKT_MOMENTUM.xlsx',      # 动量(月)
    '141014171': 'TRD_Nrrate.xlsx',            # 无风险利率
    '133910906': 'XQ_TextSentimentSta.xlsx',   # 文本情绪(股吧)
}
TARGETS = []
for fid, target in folder_targets.items():
    fe = find_entry(fid)
    if fe:
        TARGETS.append((os.path.join(MTH, fe, target), 'folder-' + fid))
    else:
        print('  缺失文件夹:', fid)
for tid, target in zip_targets.items():
    TARGETS.append((os.path.join(OUT, target), 'zip-' + tid))

def inspect(path, label):
    print('=' * 70)
    print('【%s】' % label, path)
    if not os.path.exists(path):
        print('  !! 文件不存在'); return
    t0 = time.time()
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    header = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    cols = [str(h) for h in header]
    print('sheets:', wb.sheetnames, ' ncols:', len(header))
    print('header:', header)
    date_idx = None
    for i, h in enumerate(cols):
        if any(k in h for k in ['日期', 'Date', 'Month', 'Clsdt', 'Nrr']):
            date_idx = i; break
    if date_idx is None:
        date_idx = 0
    stock_idx = cols.index('股票代码') if '股票代码' in cols else None
    sym_idx = cols.index('Symbol') if 'Symbol' in cols else None
    mind = maxd = None; cnt = 0; stocks = set(); CAP = 900000
    for row in ws.iter_rows(min_row=2, values_only=True):
        cnt += 1
        if date_idx is not None:
            v = row[date_idx]
            if v is not None:
                sv = str(v)
                if mind is None or sv < mind: mind = sv
                if maxd is None or sv > maxd: maxd = sv
        if stock_idx is not None and len(stocks) < 40000:
            v = row[stock_idx]
            if v is not None: stocks.add(str(v))
        if cnt >= CAP:
            print('  [扫描至 %d 行停止]' % CAP); break
    print('rows_scanned:', cnt)
    print('date_min:', mind, ' date_max:', maxd)
    if stock_idx is not None:
        print('distinct_stockcodes(样本):', len(stocks))
        print('样本前20:', sorted(stocks)[:20])
        etf = [s for s in stocks if s.startswith('51')]
        print('51xxxx(基金/ETF)类样本:', etf[:12], ' 数量:', len(etf))
        print('是否含 515000:', '515000' in stocks)
    if sym_idx is not None:
        syms = set(); c2 = 0
        wb2 = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws2 = wb2[wb2.sheetnames[0]]
        for row in ws2.iter_rows(min_row=2, values_only=True):
            c2 += 1
            v = row[sym_idx]
            if v is not None: syms.add(str(v))
            if c2 >= 60000: break
        wb2.close()
        print('Symbol 样本(前6万行):', sorted(syms)[:20])
        print('是否含 515000:', '515000' in syms)
    wb.close()
    print('耗时 %.1fs' % (time.time() - t0))

for p, l in TARGETS:
    try:
        inspect(p, l)
    except Exception:
        import traceback
        print('ERR', l); traceback.print_exc()
print('\n=== DONE ===')
