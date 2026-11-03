#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 515000 新闻情绪因子研究的自包含 HTML 总结报告（内嵌 ECharts 交互图表 + 数据表）。"""
import os
import re
import json
import pandas as pd
import numpy as np

# ---------- 路径 ----------
MODEL_CSV = r'D:\mth301情绪因子\模型\日度情绪因子_模型.csv'
DICT_CSV = r'D:\mth301情绪因子\词典法\日度情绪因子_词典法.csv'
FUND = r'D:\大学（本科）\mth301\FUND_MKT_Quotation.xlsx'
RF = r'D:\大学（本科）\mth301\无风险利率文件141014171(仅供西交利物浦大学使用)\TRD_Nrrate.xlsx'
REG_DIR = r'D:\mth301回归结果'
ECHARTS_JS = r'C:\Users\98097\WorkBuddy\2026-10-05-16-36-21\assets\echarts.min.js'
OUT_HTML = r'C:\Users\98097\Desktop\mth301_情绪因子_任务总结报告.html'


def read_csmar(path):
    return pd.read_excel(path, header=0, skiprows=[1, 2])


def parse_regression(path):
    """从回归结果 txt 提取变量系数/标准误/t/p 与拟合统计。"""
    with open(path, encoding='utf-8') as f:
        txt = f.read()
    info = {}
    m = re.search(r'样本区间:\s*([\d-]+) ~ ([\d-]+)\s+观测数:\s*(\d+)', txt)
    if m:
        info['start'] = m.group(1)
        info['end'] = m.group(2)
        info['n'] = int(m.group(3))
    m = re.search(r'情绪源:\s*(\S+)', txt)
    info['source'] = m.group(1) if m else ''
    m = re.search(r'R² = ([\d.]+)\s+调整R² = ([\d.]+)', txt)
    if m:
        info['r2'] = float(m.group(1))
        info['r2_adj'] = float(m.group(2))
    m = re.search(r'情绪因子系数 = ([-\d.]+)\s+t = ([-\d.]+)\s+p = ([\d.]+)', txt)
    if m:
        info['sent_coef'] = float(m.group(1))
        info['sent_t'] = float(m.group(2))
        info['sent_p'] = float(m.group(3))
    # 变量行
    rows = []
    for line in txt.splitlines():
        mm = re.match(r'^(\S+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s*$', line)
        if mm:
            rows.append({
                'name': mm.group(1), 'coef': float(mm.group(2)),
                'se': float(mm.group(3)), 't': float(mm.group(4)), 'p': float(mm.group(5)),
            })
    info['rows'] = rows
    return info


def main():
    # ---------- 1. 情绪因子 ----------
    model = pd.read_csv(MODEL_CSV, encoding='utf-8-sig')
    model['date'] = pd.to_datetime(model['date'])
    dic = pd.read_csv(DICT_CSV, encoding='utf-8-sig')
    dic['date'] = pd.to_datetime(dic['date'])

    # ---------- 2. 行情 + 超额收益 ----------
    fund = read_csmar(FUND)
    fund = fund[fund['Symbol'] == 515000][['TradingDate', 'ReturnDaily', 'ClosePrice']].copy()
    fund['TradingDate'] = pd.to_datetime(fund['TradingDate'])
    rf = read_csmar(RF)[['Clsdt', 'Nrrdaydt']].copy()
    rf['Clsdt'] = pd.to_datetime(rf['Clsdt'])
    price = fund.merge(rf, left_on='TradingDate', right_on='Clsdt', how='left')
    price['excess'] = price['ReturnDaily'] - price['Nrrdaydt'] / 100
    price = price.sort_values('TradingDate').reset_index(drop=True)

    # 合并情绪（模型法）算滞后情绪
    merged = price.merge(model[['date', 'sentiment_mean']],
                         left_on='TradingDate', right_on='date', how='left')
    merged['sent_lag'] = merged['sentiment_mean'].shift(1)
    scatter = merged.dropna(subset=['excess', 'sent_lag'])

    # ---------- 3. 回归结果 ----------
    regs = []
    for f in ['词典法_2021-01-01_2026-10-31_回归结果.txt',
              '词典法_2023-10-01_2026-10-31_回归结果.txt',
              '模型_2021-01-01_2026-10-31_回归结果.txt',
              '模型_2023-10-01_2026-10-31_回归结果.txt']:
        regs.append(parse_regression(os.path.join(REG_DIR, f)))

    # ---------- 4. 组装图表数据 ----------
    def to_dates(s):
        return s.dt.strftime('%Y-%m-%d').tolist()

    model['ma7'] = model['sentiment_mean'].rolling(7).mean()
    dic['ma7'] = dic['sentiment_mean'].rolling(7).mean()
    model['cnt7'] = model['news_count'].rolling(7).mean()

    chart = {
        # 图1 情绪走势
        'ts_dates': to_dates(model['date']),
        'ts_model': [None if pd.isna(x) else round(float(x), 4) for x in model['ma7']],
        'ts_dict': [None if pd.isna(x) else round(float(x), 4) for x in dic['ma7']],
        # 图2 新闻数量
        'cnt_dates': to_dates(model['date']),
        'cnt': [None if pd.isna(x) else round(float(x), 1) for x in model['cnt7']],
        # 图3 情绪分布（日度均值直方图）
        'hist_model': [round(float(x), 4) for x in model['sentiment_mean'].dropna()],
        'hist_dict': [round(float(x), 4) for x in dic['sentiment_mean'].dropna()],
        # 图4 价格 vs 情绪
        'price_dates': to_dates(price['TradingDate']),
        'price_close': [round(float(x), 3) for x in price['ClosePrice']],
        'price_ma7': to_dates(model['date']),
        'price_sent': [None if pd.isna(x) else round(float(x), 4) for x in model['ma7']],
        # 图5 回归情绪系数（森林图）
        'forest': [
            {'label': '词典法·5年', 'coef': regs[0]['sent_coef'], 'se': 0, 't': regs[0]['sent_t'], 'p': regs[0]['sent_p']},
            {'label': '词典法·3年', 'coef': regs[1]['sent_coef'], 'se': 0, 't': regs[1]['sent_t'], 'p': regs[1]['sent_p']},
            {'label': 'FinBERT·5年', 'coef': regs[2]['sent_coef'], 'se': 0, 't': regs[2]['sent_t'], 'p': regs[2]['sent_p']},
            {'label': 'FinBERT·3年', 'coef': regs[3]['sent_coef'], 'se': 0, 't': regs[3]['sent_t'], 'p': regs[3]['sent_p']},
        ],
        # 图6 散点
        'scatter_x': [round(float(x), 5) for x in scatter['sent_lag']],
        'scatter_y': [round(float(x), 5) for x in scatter['excess']],
    }

    # 散点拟合线
    if len(scatter) > 10:
        z = np.polyfit(scatter['sent_lag'], scatter['excess'], 1)
        p = np.poly1d(z)
        xs = np.linspace(scatter['sent_lag'].min(), scatter['sent_lag'].max(), 50)
        ys = p(xs)
        chart['fit_x'] = [round(float(x), 5) for x in xs]
        chart['fit_y'] = [round(float(x), 5) for x in ys]
        ss_res = np.sum((scatter['excess'] - p(scatter['sent_lag'])) ** 2)
        ss_tot = np.sum((scatter['excess'] - scatter['excess'].mean()) ** 2)
        chart['fit_r2'] = round(float(1 - ss_res / ss_tot), 4)
        chart['fit_slope'] = round(float(z[0]), 6)
    else:
        chart['fit_x'] = chart['fit_y'] = []
        chart['fit_r2'] = 0
        chart['fit_slope'] = 0

    # 概览统计
    stats = {
        'news_total': 1040123,
        'months': 70,
        'days': int(model['date'].nunique()),
        'daily_avg': round(float(model['news_count'].mean()), 1),
        'model_mean': round(float(model['sentiment_mean'].mean()), 4),
        'dict_mean': round(float(dic['sentiment_mean'].mean()), 4),
        'model_pos_ratio': round(float(model['pos_ratio'].mean()), 4) if 'pos_ratio' in model else 0,
        'model_neg_ratio': round(float(model['neg_ratio'].mean()), 4) if 'neg_ratio' in model else 0,
    }

    # ---------- 5. 读 echarts ----------
    with open(ECHARTS_JS, encoding='utf-8') as f:
        echarts_js = f.read()
    # 转义防止 </script> 截断
    echarts_js = echarts_js.replace('</', '<\\/')

    regs_json = json.dumps(regs, ensure_ascii=False)
    chart_json = json.dumps(chart, ensure_ascii=False)
    stats_json = json.dumps(stats, ensure_ascii=False)

    html = HTML_TEMPLATE.replace('__ECHARTS_JS__', echarts_js) \
        .replace('__REGS_JSON__', regs_json) \
        .replace('__CHART_JSON__', chart_json) \
        .replace('__STATS_JSON__', stats_json)

    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'报告已生成: {OUT_HTML}')
    print(f'统计: 新闻 {stats["news_total"]} 条 / {stats["days"]} 自然日 / 日均 {stats["daily_avg"]} 条')
    print(f'情绪均值: 模型 {stats["model_mean"]} / 词典法 {stats["dict_mean"]}')
    print('回归情绪系数:')
    for r in regs:
        print(f'  {r["source"]} {r["start"]}~{r["end"]} (n={r["n"]}): '
              f'β={r["sent_coef"]:.6f} t={r["sent_t"]:.3f} p={r["sent_p"]:.4f} R²={r["r2"]:.4f}')


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>515000 新闻情绪因子研究 · 任务总结报告</title>
<style>
  :root {
    --bg: #f5f6f8; --card: #ffffff; --ink: #1a1d24; --muted: #6b7280;
    --line: #e5e7eb; --brand: #2f6fed; --pos: #e2574c; --neg: #2f9e6e;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 0; background: var(--bg); color: var(--ink);
    font-family: -apple-system, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif;
    line-height: 1.65;
  }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 32px 20px 60px; }
  header.hero {
    background: linear-gradient(135deg, #1f3a8a 0%, #2f6fed 55%, #4f8df9 100%);
    color: #fff; border-radius: 16px; padding: 36px 40px; margin-bottom: 24px;
  }
  header.hero h1 { margin: 0 0 8px; font-size: 26px; letter-spacing: .5px; }
  header.hero p { margin: 0; opacity: .92; font-size: 14px; }
  .meta { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 14px; font-size: 13px; opacity: .9; }
  .meta span { background: rgba(255,255,255,.16); padding: 3px 10px; border-radius: 20px; }

  .conclusion {
    background: #fff7ed; border: 1px solid #fed7aa; border-left: 5px solid #f59e0b;
    border-radius: 12px; padding: 20px 24px; margin-bottom: 24px;
  }
  .conclusion b { color: #b45309; }

  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin-bottom: 24px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 18px; }
  .card .k { font-size: 13px; color: var(--muted); margin-bottom: 6px; }
  .card .v { font-size: 24px; font-weight: 700; }

  section { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 26px 28px; margin-bottom: 22px; }
  section h2 { margin: 0 0 6px; font-size: 19px; }
  section .sub { color: var(--muted); font-size: 13px; margin-bottom: 16px; }
  .chart { width: 100%; height: 380px; }
  .chart.tall { height: 440px; }

  table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
  th, td { padding: 9px 12px; border-bottom: 1px solid var(--line); text-align: right; }
  th:first-child, td:first-child { text-align: left; }
  th { background: #f9fafb; color: #374151; font-weight: 600; white-space: nowrap; }
  .sig { color: var(--pos); font-weight: 700; }
  .insig { color: var(--neg); font-weight: 600; }
  .mono { font-family: "SF Mono", Consolas, monospace; }
  tr:hover td { background: #fafbfc; }
  .note { font-size: 12.5px; color: var(--muted); margin-top: 8px; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; }
  @media (max-width: 760px) { .grid2 { grid-template-columns: 1fr; } .chart { height: 300px; } }
  footer { text-align: center; color: var(--muted); font-size: 12px; margin-top: 8px; }
</style>
</head>
<body>
<div class="wrap">

  <header class="hero">
    <h1>515000 科技 ETF 新闻情绪因子研究 · 任务总结报告</h1>
    <p>华宝中证科技龙头 ETF（515000，跟踪中证科技龙头指数 931087）· Carhart 四因子时间序列回归框架</p>
    <div class="meta">
      <span>生成时间：2026-11-04</span>
      <span>新闻样本：1,040,123 条（2021-01 ~ 2026-10）</span>
      <span>情绪方法：FinBERT 模型 + 词典法</span>
      <span>回归：Newey-West HAC</span>
    </div>
  </header>

  <div class="conclusion">
    <b>核心结论：</b>在控制 Carhart 四因子（MKT / SMB / HML / UMD）后，中文科技新闻情绪因子对 515000 的日度超额收益
    <b>没有统计上显著的预测力</b>——无论 FinBERT 模型法（主方法）还是词典法（稳健性检验），4 条回归中情绪因子 p 值均 &gt; 0.05。
    四因子本身高度显著（框架健康），情绪因子未提供增量解释。这是一个诚实的"负结果"，且结论在更换度量方法、扩展样本区间后保持稳健。
  </div>

  <div class="cards" id="statCards"></div>

  <section>
    <h2>① 情绪因子日度走势（7 日移动平均）</h2>
    <div class="sub">模型法（FinBERT，蓝）与词典法（黄橙）日度情绪均值对比；取值 [−1, +1]，正值偏乐观。</div>
    <div class="chart tall" id="chartTs"></div>
  </section>

  <section>
    <h2>② 科技新闻数量日度走势（7 日移动平均）</h2>
    <div class="sub">日度科技新闻条数，反映媒体关注度波动。</div>
    <div class="chart" id="chartCnt"></div>
  </section>

  <section>
    <h2>③ 情绪得分分布（日度均值直方图）</h2>
    <div class="sub">两种方法日度情绪均值的分布形态；模型法更集中于中性，词典法整体更偏正。</div>
    <div class="chart" id="chartHist"></div>
  </section>

  <section>
    <h2>④ 515000 收盘价 vs 情绪因子（双轴）</h2>
    <div class="sub">左轴：515000 收盘价（线）；右轴：模型法情绪 7 日移动平均（面积）。</div>
    <div class="chart tall" id="chartPrice"></div>
  </section>

  <section>
    <h2>⑤ 情绪因子回归系数（森林图）</h2>
    <div class="sub">4 条回归中情绪因子 β₅ 系数与 t 值；所有点均落在 0 附近且 p &gt; 0.05，故无显著预测力。</div>
    <div class="chart" id="chartForest"></div>
  </section>

  <section>
    <h2>⑥ 滞后情绪 vs 当日超额收益（散点 + 拟合）</h2>
    <div class="sub">X：滞后一期情绪（Sentiment<sub>t−1</sub>）；Y：当日超额收益。拟合线接近水平，斜率约 <span class="mono" id="fitSlope"></span>，R² ≈ <span class="mono" id="fitR2"></span>。</div>
    <div class="chart tall" id="chartScatter"></div>
  </section>

  <section>
    <h2>⑦ 完整回归结果矩阵</h2>
    <div class="sub">4 条回归全部变量系数；标准误为 Newey-West HAC（maxlags = √n）。</div>
    <div class="grid2" id="regTables"></div>
  </section>

  <section>
    <h2>⑧ 稳健性检验汇总</h2>
    <div class="sub">两条稳健性检验均支持"情绪因子不显著"的结论。</div>
    <table>
      <thead><tr><th>检验维度</th><th>主设定</th><th>稳健设定</th><th>结论是否一致</th></tr></thead>
      <tbody>
        <tr><td>情绪度量方法</td><td>FinBERT 模型法</td><td>词典法（CFSD 姜富伟 2020）</td><td>✅ 一致（均不显著）</td></tr>
        <tr><td>样本区间</td><td>3 年主样本（2023-10~2026-10）</td><td>5 年扩展（2021-01~2026-10）</td><td>✅ 一致（均不显著）</td></tr>
      </tbody>
    </table>
  </section>

  <footer>数据源：CSMAR 三/四因子、无风险利率、515000 行情；科技新闻（新浪/财联社等，经关键词筛选）。生成脚本 make_report.py。</footer>
</div>

<script>
var __ECHARTS_JS__
</script>
<script>
var REGS = __REGS_JSON__;
var CHART = __CHART_JSON__;
var STATS = __STATS_JSON__;
</script>
<script>
// ---- 统计卡片 ----
var cards = [
  ['新闻总条数', STATS.news_total.toLocaleString()],
  ['覆盖自然日', STATS.days],
  ['日均新闻', STATS.daily_avg + ' 条'],
  ['模型情绪均值', STATS.model_mean],
  ['词典情绪均值', STATS.dict_mean],
  ['模型正向占比', (STATS.model_pos_ratio*100).toFixed(1) + '%'],
];
document.getElementById('statCards').innerHTML = cards.map(function(c){
  return '<div class="card"><div class="k">'+c[0]+'</div><div class="v">'+c[1]+'</div></div>';
}).join('');

var C_MODEL = '#2f6fed', C_DICT = '#f59e0b', C_CNT = '#0ea5e9', C_PRICE = '#1f2937', C_ACCENT = '#e2574c';

// ---- 图1 情绪走势 ----
echarts.init(document.getElementById('chartTs')).setOption({
  grid: {left: 55, right: 30, top: 30, bottom: 45},
  tooltip: {trigger: 'axis'},
  legend: {data: ['模型法(FinBERT)', '词典法(CFSD)'], top: 0},
  xAxis: {type: 'category', data: CHART.ts_dates, boundaryGap: false},
  yAxis: {type: 'value', name: '情绪得分', min: -1, max: 1, splitLine: {lineStyle: {color: '#eef0f3'}}},
  dataZoom: [{type: 'inside'}, {type: 'slider', height: 18, bottom: 6}],
  series: [
    {name: '模型法(FinBERT)', type: 'line', data: CHART.ts_model, showSymbol: false, lineStyle: {width: 1.6, color: C_MODEL}, itemStyle: {color: C_MODEL}},
    {name: '词典法(CFSD)', type: 'line', data: CHART.ts_dict, showSymbol: false, lineStyle: {width: 1.6, color: C_DICT}, itemStyle: {color: C_DICT}},
  ]
});

// ---- 图2 新闻数量 ----
echarts.init(document.getElementById('chartCnt')).setOption({
  grid: {left: 60, right: 30, top: 30, bottom: 45},
  tooltip: {trigger: 'axis'},
  xAxis: {type: 'category', data: CHART.cnt_dates, boundaryGap: false},
  yAxis: {type: 'value', name: '条/日', splitLine: {lineStyle: {color: '#eef0f3'}}},
  dataZoom: [{type: 'inside'}, {type: 'slider', height: 18, bottom: 6}],
  series: [{name: '新闻数量(7日MA)', type: 'line', data: CHART.cnt, showSymbol: false,
    lineStyle: {width: 1.5, color: C_CNT}, areaStyle: {color: 'rgba(14,165,233,.12)'}, itemStyle: {color: C_CNT}}]
});

// ---- 图3 情绪分布直方图 ----
var bins = 40;
var hm = [], hd = [];
(function(){
  function hist(data){
    var mn = -1, mx = 1, w = (mx-mn)/bins, arr = new Array(bins).fill(0);
    data.forEach(function(v){ var i = Math.min(bins-1, Math.max(0, Math.floor((v-mn)/w))); arr[i]++; });
    return arr;
  }
  hm = hist(CHART.hist_model); hd = hist(CHART.hist_dict);
})();
var binLabels = [];
for (var i=0;i<bins;i++){ binLabels.push((-1 + (i+0.5)*(2/bins)).toFixed(2)); }
echarts.init(document.getElementById('chartHist')).setOption({
  grid: {left: 55, right: 30, top: 40, bottom: 40},
  tooltip: {trigger: 'axis'},
  legend: {data: ['模型法', '词典法'], top: 0},
  xAxis: {type: 'category', data: binLabels, name: '日度情绪均值'},
  yAxis: {type: 'value', name: '天数', splitLine: {lineStyle: {color: '#eef0f3'}}},
  series: [
    {name: '模型法', type: 'bar', data: hm, barWidth: '75%', itemStyle: {color: C_MODEL, opacity: .75}},
    {name: '词典法', type: 'bar', data: hd, barWidth: '75%', itemStyle: {color: C_DICT, opacity: .75}},
  ]
});

// ---- 图4 价格 vs 情绪 ----
echarts.init(document.getElementById('chartPrice')).setOption({
  grid: {left: 60, right: 60, top: 40, bottom: 45},
  tooltip: {trigger: 'axis'},
  legend: {data: ['515000收盘价', '模型情绪(7日MA)'], top: 0},
  xAxis: {type: 'category', data: CHART.price_dates, boundaryGap: false},
  yAxis: [
    {type: 'value', name: '收盘价', scale: true, splitLine: {lineStyle: {color: '#eef0f3'}}},
    {type: 'value', name: '情绪', min: -1, max: 1, splitLine: {show: false}},
  ],
  dataZoom: [{type: 'inside'}, {type: 'slider', height: 18, bottom: 6}],
  series: [
    {name: '515000收盘价', type: 'line', data: CHART.price_close, showSymbol: false, lineStyle: {width: 1.4, color: C_PRICE}},
    {name: '模型情绪(7日MA)', type: 'line', yAxisIndex: 1, data: CHART.price_sent, showSymbol: false,
      lineStyle: {width: 1.2, color: C_ACCENT}, areaStyle: {color: 'rgba(226,87,76,.08)'}},
  ]
});

// ---- 图5 森林图 ----
var forestCats = CHART.forest.map(function(r){return r.label;});
var forestCoef = CHART.forest.map(function(r){return r.coef;});
echarts.init(document.getElementById('chartForest')).setOption({
  grid: {left: 90, right: 60, top: 20, bottom: 40},
  tooltip: {trigger: 'axis', axisPointer: {type: 'shadow'},
    formatter: function(p){ var r = CHART.forest[p[0].dataIndex];
      return r.label+'<br/>β = '+r.coef.toFixed(6)+'<br/>t = '+r.t.toFixed(3)+'<br/>p = '+r.p.toFixed(4); }},
  xAxis: {type: 'value', name: '情绪系数 β₅', splitLine: {lineStyle: {color: '#eef0f3'}}},
  yAxis: {type: 'category', data: forestCats},
  series: [{type: 'bar', data: forestCoef.map(function(v){
      return {value: v, itemStyle: {color: Math.abs(v) < 0.005 ? C_ACCENT : C_MODEL}};
    }), barWidth: '45%'}],
  markLine: null
});

// ---- 图6 散点 + 拟合 ----
document.getElementById('fitSlope').textContent = CHART.fit_slope.toFixed(6);
document.getElementById('fitR2').textContent = CHART.fit_r2.toFixed(4);
echarts.init(document.getElementById('chartScatter')).setOption({
  grid: {left: 60, right: 30, top: 20, bottom: 45},
  tooltip: {trigger: 'item', formatter: function(p){
      return '滞后情绪: '+p.value[0].toFixed(4)+'<br/>超额收益: '+p.value[1].toFixed(5); }},
  xAxis: {type: 'value', name: 'Sentiment(t-1)', scale: true, splitLine: {lineStyle: {color: '#eef0f3'}}},
  yAxis: {type: 'value', name: '超额收益', scale: true, splitLine: {lineStyle: {color: '#eef0f3'}}},
  series: [
    {name: '观测', type: 'scatter', data: CHART.scatter_x.map(function(x,i){return [x, CHART.scatter_y[i]];}),
      symbolSize: 4, itemStyle: {color: C_MODEL, opacity: .25}},
    {name: '拟合线', type: 'line', data: CHART.fit_x.map(function(x,i){return [x, CHART.fit_y[i]];}),
      showSymbol: false, lineStyle: {width: 2, color: C_ACCENT}},
  ]
});

// ---- 图7 回归表格 ----
var names = ['alpha(常数)','MKT','SMB','HML','UMD(动量)','Sentiment_lag1'];
function regTable(r){
  var rows = '';
  r.rows.forEach(function(row){
    var isSent = row.name.indexOf('Sentiment') >= 0;
    var pcls = row.p < 0.05 ? 'sig' : 'insig';
    var pstr = row.p < 0.0001 ? '<0.0001' : row.p.toFixed(4);
    rows += '<tr><td>'+row.name+'</td><td class="mono">'+row.coef.toFixed(6)+'</td>'+
      '<td class="mono">'+row.se.toFixed(6)+'</td><td class="mono">'+row.t.toFixed(3)+'</td>'+
      '<td class="'+pcls+'">'+pstr+'</td></tr>';
  });
  return '<div><h3 style="margin:0 0 4px;font-size:15px;">'+r.source+' · '+r.start+' ~ '+r.end+'</h3>'+
    '<div class="sub">观测数 '+r.n+' · R² = '+r.r2.toFixed(4)+' · 调整R² = '+r.r2_adj.toFixed(4)+'</div>'+
    '<table><thead><tr><th>变量</th><th>系数</th><th>标准误</th><th>t值</th><th>p值</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
}
document.getElementById('regTables').innerHTML = REGS.map(regTable).join('');

</script>
</body>
</html>
"""


if __name__ == '__main__':
    main()
