# -*- coding: utf-8 -*-
import os, openpyxl
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

# 诊断 Carhart (小文件)
p = os.path.join(OUT, 'STK_MKT_CARHARTFOURFACTORS.xlsx')
print('=== Carhart openpyxl 非read_only 诊断 ===')
wb = openpyxl.load_workbook(p)
ws = wb[wb.sheetnames[0]]
print('max_row', ws.max_row, 'max_column', ws.max_column)
print('第1行:', [c.value for c in ws[1]])
print('第2行:', [c.value for c in ws[2]])
print()
print('=== Carhart pandas 诊断 ===')
df = pd.read_excel(p)
print('shape', df.shape)
print('columns', list(df.columns))
print(df.head(3).to_string())
print()
# 诊断 FUND
p2 = os.path.join(OUT, 'FUND_MKT_Quotation.xlsx')
print('=== FUND pandas 诊断 ===')
df2 = pd.read_excel(p2)
print('shape', df2.shape)
print('columns', list(df2.columns))
print(df2.head(3).to_string())
print('Symbol 唯一数:', df2['Symbol'].nunique(), ' 含515000:', (df2['Symbol'].astype(str)=='515000').any())
print('ReturnDaily 示例:', df2['ReturnDaily'].head(3).tolist())
