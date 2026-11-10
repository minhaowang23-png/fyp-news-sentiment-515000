# FYP：新闻情绪因子对 515000 科技 ETF 超额收益的预测

## 项目简介

本文研究**中文财经新闻情绪因子**对华宝中证科技龙头 ETF（**515000**，跟踪中证科技龙头指数 931087）**日度超额收益**的预测能力，采用 **Carhart 四因子**时间序列回归框架。

- **被解释变量**：515000 日度超额收益 = 日收益率 − 日度无风险利率
- **因子**：市场（MKT）、规模（SMB）、价值（HML）、动量（UMD）
- **情绪因子**：滞后一期（Sentimentₜ₋₁）
- **情绪度量方法**：
  - 主方法：FinBERT 中文金融情感模型 `bardsai/finance-sentiment-zh-base`
  - 稳健性检验：CFSD 金融情感词典法（姜富伟等，2020）
  - LLM 方法：DeepSeek `deepseek-chat`（抽样验证，全量打分待进行）
- **稳健性检验**：换度量方法（FinBERT → 词典法）+ 换样本区间（3 年主样本 → 5 年扩展）
- **标准误**：Newey-West HAC（修正残差自相关）

## 目录结构

```
fyp-news-sentiment-515000/
├── README.md
├── requirements.txt
├── .gitignore
├── 01_data_collection/        # 数据采集（新闻下载 + 数据源测试）
│   ├── download_news.py           # 新闻下载（主脚本）
│   ├── 0-下载新闻数据代码.py        # 新闻下载（桌面版）
│   ├── 0-下载新闻数据代码-测试版.py
│   └── test_*.py                  # 各数据源（东方财富/金融界/Tushare中转）连通性测试
├── 02_data_processing/        # 数据清洗与筛选
│   ├── clean_dedup_news.py        # 清洗 + 去重
│   ├── filter_tech_news.py        # 筛选科技相关新闻
│   └── tech_keywords.py           # 科技关键词表
├── 03_sentiment/              # 情绪打分
│   ├── sentiment_model_score.py   # FinBERT 模型打分（主方法，GPU）
│   ├── sentiment_dict_score.py    # CFSD 词典法打分（稳健性）
│   ├── sentiment_deepseek_score.py# DeepSeek LLM 打分（抽样验证）
│   ├── sample_compare.py          # 三方法抽样对比 + 导出
│   └── smoke_test_model.py        # 模型下载 + 冒烟测试
├── 04_factor_regression/      # 因子构建与回归
│   ├── build_sentiment_factor.py  # 日度情绪因子构建
│   ├── regression.py              # Carhart 四因子 + 情绪因子回归
│   ├── smallcap_control.py        # 创业板指/科创50 对照回归
│   ├── fetch_stock_universe.py    # 全 A 股股票池（含行业字段）
│   ├── build_tech_portfolio.py    # 纯科技股大/中/小盘组合构建
│   └── tech_portfolio_reg.py      # 科技组合回归
└── 05_report/                 # 报告生成
    ├── make_report.py             # HTML 交互报告（ECharts）
    └── make_word_report.py        # Word 报告 + 图表 PNG
```

## 研究流程（Pipeline）

```
① 数据采集 → ② 清洗筛选 → ③ 情绪打分 → ④ 因子构建 → ⑤ 回归 → ⑥ 报告
```

1. **数据采集**：通过 Tushare 第三方中转接口下载 7×24 财经快讯（2021-01 ~ 2026-10，约 104 万条）。
2. **清洗筛选**：去重、清洗、按科技关键词表筛选出科技板块相关新闻。
3. **情绪打分**：对每条新闻分别用 FinBERT 模型（`P(positive) − P(negative)`）、CFSD 词典法（`(pos−neg)/(pos+neg)`）打分；并用 DeepSeek `deepseek-chat` 对随机抽样的 100 条做 LLM 打分（三方法交叉验证）。
4. **因子构建**：按日聚合新闻情绪得分，得到日度情绪因子（滞后一期使用）。
5. **回归**：Carhart 四因子 + 情绪因子时间序列回归，Newey-West HAC 标准误，输出「四因子 vs 五因子」的 ΔR² 增量对比；并以创业板指/科创 50 及纯科技股组合做跨标的稳健性检验。
6. **报告**：生成含图表的 Word/HTML 总结报告。

## 数据源

| 数据 | 来源 | 说明 |
|------|------|------|
| 财经新闻 | Tushare 第三方中转 `t.xiaodefa.top` | 7×24 快讯，需自行申请访问凭证 |
| 行情/因子/无风险利率 | CSMAR（国泰安） | 三因子（日频）、动量（月频）、日度无风险利率 |
| 情感词典 | CFSD 姜富伟等（2020） | 中文金融情感词典（积极 3194 + 消极 5621 词） |
| 情感模型 | `bardsai/finance-sentiment-zh-base` | HuggingFace 中文金融情感 BERT |
| LLM 打分 | DeepSeek `deepseek-chat`（OpenAI 兼容 API）| 抽样 100 条验证，temperature=0 |

## 环境与依赖

```bash
pip install -r requirements.txt
```

- Python 3.13
- PyTorch 需安装 **GPU 版**（CUDA），例如 `torch==2.6.0+cu124`
- 模型下载国内可用镜像：`HF_ENDPOINT=https://hf-mirror.com`

## 运行方法

```bash
# ① 数据采集
python 01_data_collection/download_news.py

# ② 清洗筛选
python 02_data_processing/clean_dedup_news.py
python 02_data_processing/filter_tech_news.py

# ③ 情绪打分（词典法 / 模型法 / LLM 抽样）
python 03_sentiment/sentiment_dict_score.py
python 03_sentiment/sentiment_model_score.py
python 03_sentiment/sample_compare.py --step sample --n 100            # 随机抽样 100 条
python 03_sentiment/sentiment_deepseek_score.py --api-key sk-xxx \
    --input 抽样100条_待deepseek打分.jsonl --output 抽样100条_已deepseek打分.jsonl
python 03_sentiment/sample_compare.py --step merge --n 100             # 合并三方法导出

# ④ 因子构建
python 04_factor_regression/build_sentiment_factor.py --source 模型

# ⑤ 回归（3 年主样本 / 5 年扩展样本）
python 04_factor_regression/regression.py --sentiment 模型 --start 2023-10-01 --end 2026-10-31
python 04_factor_regression/regression.py --sentiment 模型 --start 2021-01-01 --end 2026-10-31
```

> 注意：各脚本中的输入/输出路径（如 `D:\...`）和样本区间按本机环境调整。数据文件与模型权重体积较大，未纳入本仓库。

## Token 配置

部分脚本需要数据源访问凭证，代码中已用占位符替换：

- `YOUR_TUSHARE_RELAY_TOKEN`：Tushare 中转服务访问凭证
- `YOUR_JRWEI_TOKEN` / `YOUR_JRWEI_TOKEN_CODE`：金融界数据源凭证

运行前请将对应占位符替换为你自己申请的凭证。

## 主要结论

在控制 Carhart 四因子后，中文科技新闻情绪因子对 515000 的日度超额收益**无统计上显著的预测力**（FinBERT 与词典法、3 年与 5 年样本下结论一致）：

| 方法 | 样本 | 情绪系数 | t 值 | p 值 | ΔR² |
|------|------|----------|------|------|------|
| FinBERT | 3 年 | −0.0041 | −1.13 | 0.257 | 0.0004 |
| FinBERT | 5 年 | +0.0026 | +1.19 | 0.234 | 0.0002 |
| 词典法 | 3 年 | −0.0039 | −1.03 | 0.302 | 0.0002 |
| 词典法 | 5 年 | +0.0024 | +1.06 | 0.289 | 0.0001 |

四因子本身高度显著（框架健康），情绪因子未提供增量解释力（ΔR² < 0.04%）。这一负结果在创业板指/科创 50 及纯科技股大/中/小盘组合上同样成立，结论稳健。

## 三方法情绪打分对比（抽样 100 条）

三种方法对同一批新闻的判读存在系统性差异，方向一致性约 50%~62%：

| 方法 | 正面 | 中性 | 负面 | 特点 |
|------|------|------|------|------|
| 词典法 | 74% | 17% | 9% | 只看情感词，方向与 DeepSeek 最接近 |
| FinBERT | 36% | 46% | 18% | 中性过半，且 38% 的 p_neu>0.99（过度自信）|
| DeepSeek | 70% | 18% | 12% | 语义推理，能识别隐含情绪 |
