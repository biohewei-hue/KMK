# 舆情交叉分析报告系统

每日聚合 **雪球 / 同花顺 / Alpha派 / 韭研公社 / 知识星球 / 财联社 / 华尔街见闻 / 东方财富** 八类数据源，生成 21 章节的 A 股舆情交叉分析报告（含大盘技术研判、背离/突破信号、热度升降温、资金榜、中美财经日历、明日荐股）。

> ⚠️ 本系统必须在**能访问国内财经网站的机器**上运行（Claude Code 云端环境网络策略默认封锁这些域名）。

## 快速开始

```bash
pip install -r requirements.txt

# 1. 填监控池（15只个股）
#    编辑 config/config.yaml → watchlist

# 2. 填凭证（cookie 获取方法见下文）
cp config/credentials.example.json config/credentials.json
#    编辑 config/credentials.json

# 3. 每日运行（建议收盘后或晚间）
python run_daily.py --all

# 4. 在本仓库打开 Claude Code，说「生成今日报告」
#    Claude 按 CLAUDE.md 流程写出 data/YYYY-MM-DD/report.md
```

首日运行后「热度变化」章节没有对比基准，从第二天起自动生成升温/降温对比。

## 凭证获取方法（F12 抓包）

通用步骤：Chrome 打开目标网站并登录 → 按 `F12` → `Network(网络)` 标签 → 刷新页面 → 点任意该站域名的请求 → `Request Headers` 里复制 `Cookie` 整行的值。

| 数据源 | 打开的页面 | 要复制的内容 | 填到 credentials.json |
| --- | --- | --- | --- |
| 雪球 | xueqiu.com（登录后） | Cookie 全串 | `xueqiu.cookie` |
| 知识星球 | wx.zsxq.com（扫码登录） | Cookie 全串（含 `zsxq_access_token`） | `zsxq.cookie` |
| 韭研公社 | jiuyangongshe.com（登录后） | 请求头里的 `token`（XHR 请求上） | `jiuyan.headers.token` |
| Alpha派 | 蓝宝书/每日必看页面 | 对应 XHR 请求 → 右键『Copy as cURL』整段 | 发给 Claude 完成接线 |
| 同花顺 | （可选）data.10jqka.com.cn | Cookie 全串 | `ths.cookie` |

- **知识星球**：星球 ID 不用手动找，程序会按 `config.yaml → zsxq.group_keyword`（默认"黑金"）在你已加入的星球中自动定位；也可直接填 `group_id`。
- **Alpha派 / 韭研公社栏目**：接口非公开，首次使用把抓包的 cURL 发给 Claude，一次接线后长期使用。
- **同花顺资金榜**：默认用东方财富公开接口替代（同源数据，无需凭证）；也可用本机 iFinD 插件导出后替换。
- Cookie 一般能用数天到数周，失效后重新抓一次即可。**credentials.json 已被 gitignore，绝不会提交到仓库。**

## 报告章节

| 章节 | 内容 | 数据源 |
| --- | --- | --- |
| 今日核心 | 一段式总览 | 综合 |
| 〇 | 上证/科创50/创业板技术研判、背离与突破信号、见底判断 | 东方财富K线 |
| 一 | 监控池15只个股信号分级（强关注/关注/观察） | 全源交叉 |
| 二~四 | 风险/机会/主线热度事件卡片+来源标签 | 各源交叉 |
| 五 | 同花顺热榜升温最快/降温最快/新上榜 | 同花顺（快照对比） |
| 六~八 | MLCC、存储、消费等板块逻辑 | Alpha派/研报/公社 |
| 九 | 星球24h帖数、文字帖归纳、个股提及次数 | 知识星球 |
| 十 | 蓝宝书PaiPai每日必看归纳、24h提及、重点研报 | Alpha派 |
| 十一 | 公社内容精选(含链接帖全文)/学习笔记/公告精选/盘前纪要 | 韭研公社 |
| 十二 | 雪球高讨论热帖 | 雪球 |
| 十三 | 政策信号（已证实/传闻分级） | 新华社/财新/澎湃等 |
| 十四~十六 | 各方判断/交叉验证/小作文 | 综合 |
| 十七 | 财联社电报时间线 | 财联社 |
| 十八 | 中美财经日历（三星及以上） | 华尔街见闻 |
| 十九 | 概念板块/行业板块/个股 近5日主力净流入Top20 | 东方财富(替代同花顺) |
| 二十 | 综合研判：热度最高与升温最快的行业/个股 | 全源 |
| 二一 | 明日最值得关注的3只股票 | 全源+技术+资金 |

## 目录结构

```
config/           配置与凭证（credentials.json 不入库）
src/fetchers/     8 个数据源采集器
src/analysis/     技术指标、背离/突破检测、热度对比、监控池分级
src/report/       报告骨架生成
data/YYYY-MM-DD/  每日原始数据 + report_skeleton.md + report.md（不入库）
run_daily.py      主入口
```

## 免责声明

本系统输出为舆情信息聚合与分析，不构成任何投资建议。
