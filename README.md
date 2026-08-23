# KMK · 已废弃

本仓库的舆情分析系统**已停止使用**，功能由更成熟的 `daily-market-intel` skill 取代。

## 为什么废弃

`daily-market-intel` 在同一问题上做得更完整，且两者的做法有本质差异：

| | daily-market-intel | 本仓库 |
| --- | --- | --- |
| 经验规则 | 48 条，全部来自真实误判 | 无 |
| 股票池 | 426 只（0625/0704/优质企业 三份自选） | 15 只（.sel 的一小部分，本就不完整） |
| 产业主题 | 16 个，按下游客户归类 | 无 |
| 自检闭环 | 有，量化假阴性/买点偏差/方向偏差 | 无 |
| 行情数据 | Tushare 官方 API | 抓包逆向同花顺 |
| 知识星球 | 官方 MCP（api_key） | cookie 抓包 |
| Alpha派 | JWT + 官方接口 | 猜候选路径探测 |

本仓库为拿到数据做的大量抓包接线工作，在 `daily-market-intel` 里由官方接口直接解决。

## 唯一保留的东西

`salvaged/fetch_limit_pool.py` —— 同花顺涨停池/炸板池采集，产出**连板高度、炸板率、
2板以上家数、高标名单**，并带跨日快照以计算高度趋势。`daily-market-intel` 中没有同类脚本。

用法：放进 `skills/daily-market-intel/scripts/`，与其余采集脚本一致：

```bash
python scripts/fetch_limit_pool.py            # 今天
python scripts/fetch_limit_pool.py 2026-08-22 # 指定日期
```

落盘 `data/raw/<date>/limit_pool.json` 与 `data/snapshot/limit_pool_<date>.json`。

这三个指标是情绪周期的温度计：**连板高度回落=退潮、回升=启动；炸板率>50%说明承接弱；
2板以上家数反映晋级梯队厚度**。单日数值意义有限，脚本因此自动输出最近5日的高度轨迹。

## 历史代码

完整实现仍在 git 历史中，需要时可 `git log` 找回。
