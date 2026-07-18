# 使用与测试指导文档

> Mexico Instagram Creator Finder — 墨西哥 Instagram 内容创作者发现工具（第一阶段 MVP）
>
> 本文档面向已安装本项目的用户，介绍已实现的功能、CLI 使用方法、单元测试运行方式以及常见场景示例。
> 项目合规约束详见 [AGENTS.md](../AGENTS.md) 与 [README.md](README.md)。

---

## 目录

1. [已实现功能](#1-已实现功能)
2. [环境准备](#2-环境准备)
3. [CLI 命令详解](#3-cli-命令详解)
4. [配置文件说明](#4-配置文件说明)
5. [典型使用场景](#5-典型使用场景)
6. [无 Instagram 账号测试（dry-run 模式）](#6-无-instagram-账号测试dry-run-模式)
7. [单元测试运行](#7-单元测试运行)
8. [静态检查](#8-静态检查)
9. [任务状态与断点续传](#9-任务状态与断点续传)
10. [导出文件说明](#10-导出文件说明)
11. [停止原因与异常处理](#11-停止原因与异常处理)
12. [常见问题](#12-常见问题)

---

## 1. 已实现功能

### 1.1 核心搜索流程（6 阶段）

| 阶段 | 模块 | 功能 |
|------|------|------|
| 1. 登录 | [app/instagram/client.py](app/instagram/client.py) | 从 `.env` 读取凭据登录、Session 复用 |
| 2. 发现 | [app/discovery/hashtag.py](app/discovery/hashtag.py) | 从 Hashtag 近期帖子/Reels 提取作者 username |
| 3. 去重 | [app/discovery/deduplication.py](app/discovery/deduplication.py) | 标准化 username（去 `@`、URL、转小写、去末尾 `/`）+ 合并 source_hashtags |
| 4. 排除 | [app/discovery/seeds.py](app/discovery/seeds.py) | 应用 TXT/CSV/XLSX/用户名/URL 排除名单 |
| 5. 分析 | [app/analysis/](app/analysis/) | 资料获取 + 粉丝筛选 + 墨西哥识别 + 垂类分类 + 账号类型 + 内容指标 + 联系方式 + 评分 |
| 6. 导出 | [app/export/](app/export/) | CSV（UTF-8 BOM）/ JSON / XLSX 三种格式 |

### 1.2 分析模块明细

- **墨西哥地区识别** [mexico_detector.py](app/analysis/mexico_detector.py)：7 类信号（Biography 国家名/州/城市、Hashtag、Caption、地点标签、`.mx` 网站、`+52` 辅助），输出 `mexico_confidence_score` / `mexico_signals` / `detected_country` / `detected_state` / `detected_city`。不得仅凭 `mx`/西语/国旗表情/单 Hashtag 判定。
- **垂类分类** [niche_classifier.py](app/analysis/niche_classifier.py)：7 个垂类（perfume / beauty / skincare / makeup / fashion / lifestyle / UGC）+ brand/media/agency/general，输出 `primary_niche` / `niche_scores` / `niche_signals` / `classification_reasons`。
- **账号类型识别** [account_classifier.py](app/analysis/account_classifier.py)：区分 personal_creator / ugc_creator / brand / shop / media / news / agency / marketing / fan_reposter / topic_aggregator。
- **内容指标** [media_metrics.py](app/analysis/media_metrics.py)：近 12 条内容的点赞/评论/Reels 播放量平均值/中位数/最大值 + 发布频率 + `days_since_last_post`。**三态严格区分**：`no_reels` / `not_visible` / `available`，不用 0 混淆 None。
- **联系方式提取** [contact_extractor.py](app/analysis/contact_extractor.py)：6 类公开联系方式（邮箱 / `mailto:` / `wa.me` / WhatsApp Business / Linktree / Beacons）。**不**推测邮箱、**不**拼接域名、**不**识别普通数字为 WhatsApp。
- **透明评分** [scoring.py](app/analysis/scoring.py)：100 分制（墨西哥 25 + 垂类 25 + Reels 20 + 活跃度 10 + 粉丝区间 10 + 联系方式 5 + 个人创作者 5），输出 `total_score` / `score_breakdown` / `recommendation_level`(A/B/C/D) / `recommendation_reasons`。

### 1.3 安全与合规

- **统一适配层** [app/instagram/client.py](app/instagram/client.py)：所有 instagrapi 调用通过封装，业务模块不直接创建 `Client()`
- **安全停止**：遇 `ChallengeRequired` / `FeedbackRequired` / `PleaseWaitFewMinutes` / `ClientThrottledError` / `RateLimitError` / `SentryBlock` / `LoginRequired` / `AccountSuspended` / `ProxyAddressIsBlocked` / HTTP 429 时立即转换为 `SecurityStopError`，保存断点并停止，**不自动重试**
- **请求频率** [rate_limit.py](app/instagram/rate_limit.py)：默认 4-8 秒随机间隔，单实例运行，不使用线程池/异步并发；网络错误最多重试 2 次（指数退避）
- **日志脱敏** [logging_config.py](app/logging_config.py)：屏蔽密码、Cookie、Session、Authorization Header、私信、私人联系方式
- **凭据安全**：密码只从 `.env` 或环境变量读取，不写入源码/YAML/日志/数据库
- **断点续传** [checkpoint.py](app/storage/checkpoint.py)：每完成一个 Hashtag 或账号分析即保存进度，支持 `--resume` / `--reset-task`

### 1.4 明确**不实现**的功能（AGENTS.md §5 禁止）

- 自动私信 / 批量私信 / 自动关注 / 自动点赞 / 自动评论 / 自动转发 / 自动收藏 / 自动查看 Story
- 验证码自动识别 / Challenge 自动绕过 / 短信/邮箱验证绕过 / 设备指纹伪造
- 多账号轮换 / 账号池 / 代理池 / IP 自动切换
- 猜测电子邮箱 / 推测私人手机号 / 抓取私密账号内容 / 人脸识别
- 用户注册 / 付费会员 / 支付系统 / 多租户 / SaaS / CRM / 自动营销

---

## 2. 环境准备

### 2.1 系统要求

- Windows 10 / 11
- Python 3.11 或更高版本
- 网络可访问 Instagram

### 2.2 安装依赖

```powershell
cd d:\桌面\ins\instagrapi\mexico-instagram-creator-finder
pip install -e ".[dev]"
```

依赖清单（[pyproject.toml](pyproject.toml)）：
- 运行依赖：instagrapi、typer、pydantic、pydantic-settings、sqlalchemy、pandas、openpyxl、rich、pyyaml、python-dotenv
- 开发依赖：pytest、ruff

### 2.3 配置凭据

复制 `.env.example` 为 `.env` 并填入 Instagram 账号：

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env` 内容：

```text
IG_USERNAME=your_instagram_username
IG_PASSWORD=your_instagram_password
```

或通过环境变量临时设置（不写入文件）：

```powershell
$env:IG_USERNAME='your_username'
$env:IG_PASSWORD='your_password'
```

> **注意**：建议使用小号或专用账号，避免主账号被风控。本项目仅读取公开数据，遇平台限制会立即停止。

---

## 3. CLI 命令详解

进入项目目录后通过 `python main.py <command>` 调用。所有命令均支持 `--help` 查看详细参数。

### 3.1 命令一览

```text
validate-config    校验配置完整性
show-config        显示最终合并后的配置（脱敏）
search             搜索墨西哥 Instagram 内容创作者
task-status        查看任务状态
export             导出已分析的结果
clear-local-data   清除本地数据（SQLite、Session、输出文件）
```

### 3.2 `validate-config` — 校验配置

```powershell
python main.py validate-config
```

输出示例（凭据已配置）：

```text
✓ 配置校验通过
┌──────────────────── 配置概览 ────────────────────┐
│ 粉丝区间       20000 - 300000                    │
│ 请求间隔       4-8 秒                             │
│ 最大 Hashtag 数 15                                │
│ 每 Hashtag 媒体数 20                              │
│ 最大候选账号数 300                                │
│ 最大分析账号数 100                                │
│ 近期内容数量   12                                 │
│ 断点续传       启用                               │
│ 导出格式       csv, json, xlsx                   │
└──────────────────────────────────────────────────┘
```

未配置凭据时显示清晰提示，不输出异常堆栈。

### 3.3 `show-config` — 查看合并后配置

```powershell
python main.py show-config
```

输出 JSON 格式的完整配置（密码字段已脱敏为 `***`），便于确认「命令行 > 环境变量 > 用户 YAML > 默认」合并结果。

### 3.4 `search` — 执行搜索

完整参数：

```powershell
python main.py search [OPTIONS]
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `--hashtags <TAG>` | `-t` | Hashtag（不带 `#`），可多次指定；不指定则使用 `config/hashtags.yaml` 默认 18 个 |
| `--min-followers <N>` | | 覆盖最小粉丝数（默认 20000） |
| `--max-followers <N>` | | 覆盖最大粉丝数（默认 300000） |
| `--exclude <PATH_OR_NAME>` | `-e` | 排除名单文件路径或用户名，可多次指定 |
| `--resume` | | 恢复上次未完成的任务 |
| `--reset-task` | | 重置任务后重新开始 |
| `--dry-run` | | **使用预定义示例数据测试完整流程，不登录 Instagram、不联网** |

**执行过程显示**（Rich UI）：
- 当前阶段（1/6 登录 → 6/6 完成）
- 当前 Hashtag / 候选账号数 / 已分析账号数 / 已跳过数 / 错误数
- 进度条 + 耗时
- 停止原因（如遇安全停止）
- 输出文件路径

### 3.5 `task-status` — 查看任务状态

```powershell
# 查看最近 5 个任务
python main.py task-status

# 查看指定任务详情
python main.py task-status --task-id task_20260718_153000_abc12345
```

输出字段：任务 ID、状态（running/paused/stopped/completed/failed）、开始/更新/完成时间、停止原因、已完成 Hashtag、已发现/已分析/失败账号数。

### 3.6 `export` — 重新导出结果

```powershell
# 导出所有任务的结果（默认 csv+json+xlsx）
python main.py export

# 导出指定任务
python main.py export --task-id task_20260718_153000_abc12345

# 仅导出 CSV 和 JSON
python main.py export --formats csv json
```

### 3.7 `clear-local-data` — 清除本地数据

```powershell
# 交互式确认
python main.py clear-local-data

# 跳过确认
python main.py clear-local-data --yes
```

清除范围：
- SQLite 数据库（`data/app.db`）
- Session 文件（`.instagram_session.json`）
- 输出目录内所有文件（`output/*`）

> **警告**：此操作不可恢复。

---

## 4. 配置文件说明

所有可调参数集中在 [config/](config/) 目录，**不硬编码在业务函数中**。

| 文件 | 作用 |
|------|------|
| [default.yaml](config/default.yaml) | 主配置：instagram/discovery/filters/analysis/checkpoint/output 6 个 section |
| [hashtags.yaml](config/hashtags.yaml) | 18 个墨西哥垂类默认 Hashtag |
| [mexico_locations.yaml](config/mexico_locations.yaml) | 32 个州 + 城市别名 + 国家别名 + 墨西哥 Hashtag + `+52` 区号 |
| [niche_keywords.yaml](config/niche_keywords.yaml) | perfume/beauty/skincare/makeup/fashion/lifestyle/UGC 七个垂类关键词（西/英双语） |
| [excluded_account_terms.yaml](config/excluded_account_terms.yaml) | brand/media/agency/shop/fan/aggregator 六类排除词 |

### 4.1 默认参数（[default.yaml](config/default.yaml) 摘要）

```yaml
instagram:
  request_delay_min_seconds: 4    # 请求最小间隔
  request_delay_max_seconds: 8    # 请求最大间隔
  retry_network_errors: 2         # 网络错误最多重试 2 次
  stop_on_rate_limit: true        # 限流立即停止
  stop_on_challenge: true         # Challenge 立即停止

discovery:
  max_hashtags: 15                # 最大 Hashtag 数
  media_per_hashtag: 20           # 每个 Hashtag 最多取 20 条媒体
  max_candidates: 300             # 最大候选账号数
  max_profiles_to_analyze: 100    # 最大分析账号数
  seed_expansion_depth: 1         # 种子扩展深度（MVP 仅 1 层）

filters:
  min_followers: 20000            # 最小粉丝数
  max_followers: 300000           # 最大粉丝数
  require_public_account: true    # 仅公开账号
  require_mexico_signal: true     # 必须有墨西哥信号（confidence ≥ 0.4）
  maximum_days_since_last_post: 90 # 最大停更天数
  minimum_recent_media_count: 3   # 最少近期内容数
  minimum_median_reel_views: 2000 # 最低 Reels 中位播放量
  exclude_brands: true            # 排除品牌账号
  exclude_media_accounts: true    # 排除媒体/新闻账号

analysis:
  recent_media_amount: 12         # 分析近 12 条内容
  maximum_caption_length: 3000    # Caption 截断长度

checkpoint:
  enabled: true                   # 启用断点续传
  database_file: "data/app.db"

output:
  directory: "output"
  formats: [csv, json, xlsx]
```

### 4.2 配置优先级

```text
命令行参数  >  环境变量  >  用户 YAML 配置  >  默认配置 (config/default.yaml)
```

修改默认参数推荐方式：直接编辑 `config/*.yaml`，或通过 CLI 选项临时覆盖。

---

## 5. 典型使用场景

### 场景 1：使用默认配置搜索

```powershell
python main.py search
```

使用 `config/hashtags.yaml` 中的 18 个默认 Hashtag，粉丝区间 20000-300000，最多分析 100 个账号。

### 场景 2：指定 Hashtag 与粉丝区间

```powershell
python main.py search --hashtags perfumemexico fraganciasmexico --min-followers 30000 --max-followers 150000
```

### 场景 3：使用排除名单

先准备排除名单文件 `data/excluded.txt`：

```text
# 注释行
brand_official
shop_example
https://www.instagram.com/another_brand/
@some_agency
```

执行：

```powershell
python main.py search --exclude data/excluded.txt
```

也支持直接传入用户名：

```powershell
python main.py search --exclude brand_official --exclude shop_example
```

支持的排除名单格式：TXT / CSV / XLSX / 之前导出的结果文件。

### 场景 4：断点续传

任务因限流或意外中断后恢复：

```powershell
python main.py search --resume
```

会自动找到最近一个 `running`/`paused`/`stopped` 状态的任务，跳过已完成的 Hashtag 和已分析的账号。

### 场景 5：完全重置任务

```powershell
python main.py search --reset-task
```

清除当前任务断点，从头开始。

### 场景 6：仅导出，不重新搜索

```powershell
python main.py export --task-id task_20260718_153000_abc12345 --formats csv xlsx
```

---

## 6. 无 Instagram 账号测试（dry-run 模式）

### 6.1 什么是 dry-run 模式

`--dry-run` 选项让你**无需 Instagram 账号、无需联网**即可运行完整搜索流程：

- 使用 [app/instagram/fake_client.py](app/instagram/fake_client.py) 中的 `FakeInstagramClient` 替代真实客户端
- 加载预定义的 10 个示例账号（覆盖各种筛选场景）
- 跑完整 6 阶段流程：登录（模拟）→ 发现 → 去重 → 排除 → 分析 → 导出
- 生成真实的 CSV/JSON/XLSX 导出文件
- 不调用任何 instagrapi API、不发起任何网络请求

### 6.2 运行 dry-run

```powershell
cd d:\桌面\ins\instagrapi\mexico-instagram-creator-finder

# 使用默认 18 个 Hashtag
python main.py search --dry-run

# 或指定 Hashtag（每个 -t 传一个）
python main.py search --dry-run --hashtags perfumemexico --hashtags bellezamx --hashtags skincaremx
```

> **注意**：Typer 的多值选项需用多次 `--hashtags` 传参，不能用空格分隔。

### 6.3 预期输出

```text
┌─────────────────────── 开始搜索 ────────────────────────┐
│ Mexico Instagram Creator Finder v0.1.0                  │
│ Hashtag 数: 3  粉丝区间: 20000-300000                   │
│ 最大候选账号: 300  最大分析账号: 100 [DRY-RUN 示例数据] │
└─────────────────────────────────────────────────────────┘
[DRY-RUN] 使用预定义示例数据，不登录 Instagram、不联网
阶段 1/6: 模拟登录（DRY-RUN）...
阶段 2/6: 从 Hashtag 发现候选账号...
待处理 Hashtag: 3 个
  发现候选... ───────────────────────────── 3/3 0:00:00
阶段 3/6: 去重...  候选数: 5
排除: 0  保留: 5
阶段 4/6: 获取资料与分析...  待分析: 5
  分析账号... ───────────────────────────── 5/5 0:00:01
已分析: 3  已跳过: 2  错误: 0
阶段 5/6: 导出结果...
  CSV: output\creators_task_xxx.csv
  JSON: output\creators_task_xxx.json
  XLSX: output\creators_task_xxx.xlsx
阶段 6/6: 任务完成
```

### 6.4 示例账号场景覆盖

预定义的 10 个示例账号覆盖各种筛选结果（全部为虚构数据，不对应真实 Instagram 账号）：

| 用户名 | 粉丝数 | 场景 | 预期结果 |
|--------|--------|------|----------|
| `xiangshui_cdmx` | 85000 | 完美匹配，CDMX + 香水 + .mx 域名 + WhatsApp | A 级（≈96 分） |
| `meizhuang_laura` | 124000 | 美妆博主，Guadalajara + Linktree | A 级（≈95 分） |
| `hufu_merida` | 42000 | 护肤创作者，Mérida + Beacons | A 级（≈86 分） |
| `chuanda_cdmx` | 67000 | 穿搭博主，无 Reels（信息不足） | 被跳过或低分 |
| `xiaoshizi_mx` | 8500 | 粉丝不足 20000 | 被跳过（粉丝筛选） |
| `private_xiangshui_riji` | 35000 | 私密账号 | 被跳过（公开账号筛选） |
| `xiangshui_pinpai_mx` | 180000 | 品牌账号 | 被排除（exclude_brands） |
| `meizhuang_news_mx` | 220000 | 媒体账号 | 被排除（exclude_media_accounts） |
| `jiu_xiangshui_blog` | 55000 | 停更 120 天 | 被跳过（停更筛选） |
| `xiangshui_lover_us` | 95000 | 加州账号，无墨西哥信号 | 被跳过（墨西哥信号筛选） |

### 6.5 验证导出文件

dry-run 完成后，可在 `output/` 目录查看生成的文件：

```powershell
# 查看导出文件
Get-ChildItem output\

# 查看 JSON 结果
Get-Content output\creators_task_*.json | Out-String

# 用 Excel 打开 CSV
Start-Process excel "output\creators_task_*.csv"
```

### 6.6 dry-run 与真实模式的差异

| 方面 | dry-run 模式 | 真实模式 |
|------|--------------|----------|
| Instagram 登录 | 模拟，立即成功 | 真实登录或 Session 复用 |
| Hashtag 媒体 | 预定义示例数据 | 真实 Instagram API |
| 网络请求 | 无 | 有（受 4-8 秒间隔限制） |
| 凭据要求 | 不需要 | 需要 `.env` 配置 |
| 数据真实性 | 虚构示例 | 真实公开数据 |
| 流程逻辑 | 完全一致 | 完全一致 |
| 导出文件 | 真实生成 | 真实生成 |

### 6.7 dry-run 的合规保证

- ✅ 不登录真实 Instagram 账号
- ✅ 不发起任何网络请求
- ✅ 不调用 instagrapi 任何 API
- ✅ 不绕过任何安全机制
- ✅ 仅用于本地流程演示与测试
- ✅ 示例数据全部为虚构，不对应真实账号

---

## 7. 单元测试运行

### 7.1 运行全部测试

```powershell
cd d:\桌面\ins\instagrapi\mexico-instagram-creator-finder
python -m pytest tests/
```

预期结果：

```text
============================ 256 passed in 14.21s =============================
```

> **重要**：所有测试使用 Mock / Fake Client，**不会**登录真实 Instagram 账号，**不会**发起任何网络请求。

### 7.2 详细输出

```powershell
python -m pytest tests/ -v --tb=short
```

### 7.3 测试文件清单

13 个测试文件，256 个测试用例：

| 测试文件 | 用例数 | 覆盖模块 |
|----------|--------|----------|
| [test_username_normalization.py](tests/test_username_normalization.py) | 38 | `deduplication.py`：去 `@`/URL/转小写/末尾 `/`/空行/`#` 注释/保留字/非法字符 |
| [test_exclusion_list.py](tests/test_exclusion_list.py) | 28 | `seeds.py`：TXT/CSV/XLSX/URL 解析 |
| [test_mexico_detector.py](tests/test_mexico_detector.py) | 19 | `mexico_detector.py`：Biography/城市/州/Hashtag/`.mx`/多信号/弱信号不判定 |
| [test_niche_classifier.py](tests/test_niche_classifier.py) | 16 | `niche_classifier.py`：7 个垂类关键词与多信号 |
| [test_account_classifier.py](tests/test_account_classifier.py) | 15 | `account_classifier.py`：品牌/媒体/个人创作者识别 |
| [test_contact_extractor.py](tests/test_contact_extractor.py) | 16 | `contact_extractor.py`：邮箱/`wa.me`/WhatsApp/Linktree/Beacons |
| [test_media_metrics.py](tests/test_media_metrics.py) | 19 | `mappers.py` + `media_metrics.py`：三态/中位数/naive datetime |
| [test_scoring.py](tests/test_scoring.py) | 14 | `scoring.py`：100 分评分 + A/B/C/D 级别 |
| [test_config.py](tests/test_config.py) | 26 | `config.py`：「命令行 > 环境变量 > YAML > 默认」优先级 |
| [test_storage.py](tests/test_storage.py) | 16 | `database.py` + `repositories.py`：SQLite 持久化、无密码列 |
| [test_checkpoint.py](tests/test_checkpoint.py) | 20 | `checkpoint.py`：断点保存/恢复/重置 |
| [test_exporters.py](tests/test_exporters.py) | 19 | `csv/json/excel_exporter.py`：UTF-8 BOM、中文不乱码、URL 可点击 |
| [test_fake_client.py](tests/test_fake_client.py) | 10 | `fake_client.py`：dry-run 模式的 FakeInstagramClient |

### 7.4 运行单个测试文件

```powershell
python -m pytest tests/test_fake_client.py -v
```

### 7.5 运行单个测试用例

```powershell
python -m pytest tests/test_fake_client.py::test_fake_client_login_immediate_success -v
```

### 7.6 查看测试覆盖率（可选）

如需安装覆盖率工具：

```powershell
pip install pytest-cov
python -m pytest tests/ --cov=app --cov-report=term-missing
```

---

## 8. 静态检查

### 8.1 Ruff 检查

```powershell
ruff check .
```

预期输出：

```text
All checks passed!
```

### 8.2 Ruff 格式化检查

```powershell
ruff format --check .
```

预期输出：

```text
48 files already formatted
```

### 8.3 自动修复与格式化

如检查未通过，可执行：

```powershell
# 自动修复 lint 问题
ruff check --fix .

# 自动格式化
ruff format .
```

### 8.4 一键验证（推荐提交前执行）

```powershell
python -m pytest tests/ ; ruff check . ; ruff format --check .
```

---

## 9. 任务状态与断点续传

### 9.1 任务状态流转

```text
running  ──┬──→ completed   （正常完成）
           ├──→ stopped     （遇 SecurityStopError）
           ├──→ failed      （遇其他异常）
           └──→ paused      （用户手动中断，未来版本支持）
```

### 9.2 断点保存内容

每完成一个关键步骤即保存到 SQLite：

- 已完成的 Hashtag 列表
- 已发现的 username 集合
- 已分析的 username 集合
- 失败的 username + 错误原因
- 当前任务状态
- 停止原因

### 9.3 恢复任务

```powershell
python main.py search --resume
```

行为：
1. 查找最近一个 `running`/`paused`/`stopped` 状态的任务
2. 跳过已完成的 Hashtag（不重复请求）
3. 跳过已分析的账号（不重复调用 `user_info`/`user_medias`）
4. 保留已发现的候选与已排除账号

### 9.4 查看任务详情

```powershell
# 列出最近 5 个任务
python main.py task-status

# 查看指定任务断点详情
python main.py task-status --task-id <TASK_ID>
```

### 9.5 重置任务

```powershell
python main.py search --reset-task
```

清除当前任务的所有断点信息，从头开始。

---

## 10. 导出文件说明

### 10.1 输出位置

`output/` 目录，文件名格式：`creators_<task_id>.<ext>`

### 10.2 支持格式

| 格式 | 特性 |
|------|------|
| CSV | UTF-8 BOM（中文/西班牙语重音不乱码）、Excel 可直接打开 |
| JSON | `ensure_ascii=False`、`indent=2`、保留 Unicode 原字符 |
| XLSX | openpyxl、字段宽度合理、长文本自动换行、URL 可点击、冻结首行 |

### 10.3 导出字段（47 列）

完整字段见 [app/export/common.py](app/export/common.py) 的 `EXPORT_FIELDS`，主要包括：

- 账号信息：username / full_name / profile_url / follower_count / media_count / is_verified / is_business / category_name
- 墨西哥信号：mexico_confidence_score / detected_country / detected_state / detected_city / mexico_signals
- 垂类：primary_niche / niche_scores / niche_signals
- 账号类型：account_type / account_type_confidence
- 内容指标：recent_media_checked / recent_reels_checked / last_post_date / days_since_last_post / average_likes / median_likes / average_comments / median_comments / average_visible_reel_views / median_visible_reel_views / maximum_visible_reel_views / posting_frequency / reels_view_data_available
- 联系方式：public_email / public_whatsapp_url / external_url / linktree_url / beacons_url / has_public_contact
- 评分：total_score / score_breakdown / recommendation_level / recommendation_reasons
- 来源：source_hashtags / discovered_at / collected_at

### 10.4 默认排序

1. `total_score` 降序
2. `median_visible_reel_views` 降序
3. `follower_count` 降序

### 10.5 安全保证

导出文件**不包含**：
- 密码
- Session 内容
- 私信
- 私人电话号码
- 推测的邮箱

---

## 11. 停止原因与异常处理

### 11.1 安全停止（退出码 2）

遇以下异常立即停止并保存断点：

| 异常 | 说明 |
|------|------|
| `ChallengeRequired` | Instagram 要求人工验证 |
| `FeedbackRequired` | Instagram 反馈要求 |
| `PleaseWaitFewMinutes` | 要求等待几分钟 |
| `ClientThrottledError` | HTTP 429 限流 |
| `RateLimitError` | 速率限制 |
| `SentryBlock` | Sentry 风控阻止 |
| `LoginRequired` | 需重新登录 |
| `AccountSuspended` | 账号被封禁 |
| `ProxyAddressIsBlocked` | IP 被封禁 |
| `ChallengeSelfieCaptcha` | 自拍验证码 |
| `ChallengeUnknownStep` | 未知验证步骤 |

恢复方式：**不自动重试**。需在官方 Instagram App 完成验证后用 `--resume` 恢复。

### 11.2 Instagram 调用失败（退出码 3）

网络错误等可重试异常重试 2 次后仍失败时退出。

### 11.3 其他运行失败（退出码 4）

配置错误、文件读写错误等。

### 11.4 配置错误（退出码 1）

`validate-config` 或 `search` 启动时校验失败。

---

## 11. 常见问题

### Q1：没有 Instagram 账号可以测试吗？

可以。有两种方式：

1. **运行 dry-run 模式**（推荐，端到端流程演示）：
   ```powershell
   python main.py search --dry-run
   ```
   使用预定义的 10 个示例账号跑完整 6 阶段流程，生成真实的 CSV/JSON/XLSX 导出文件。详见第 6 章。

2. **运行单元测试**（覆盖所有业务逻辑）：
   ```powershell
   python -m pytest tests/
   ```
   256 个测试用例使用 Mock/Fake Client，不需要真实账号也不发起网络请求。详见第 7 章。

### Q2：为什么默认粉丝区间是 20000-300000？

这是 AGENTS.md §7 规定的目标粉丝区间，针对香水/美妆/护肤垂类的中腰部创作者。可在 `config/default.yaml` 修改或通过 `--min-followers`/`--max-followers` 覆盖。

### Q3：搜索速度为什么很慢？

按 AGENTS.md §13 要求，默认 4-8 秒随机间隔、单实例运行、不并发。这是为了账号安全，**不**可调高并发。如需更快，可适当缩小 `max_hashtags` 或 `max_profiles_to_analyze`。

### Q4：遇到 ChallengeRequired 怎么办？

1. 不要重试，本项目已停止
2. 在官方 Instagram App 或网页版完成人工验证
3. 等待 24 小时再用 `--resume` 恢复
4. 如反复触发，建议更换账号或暂停使用

### Q5：如何彻底清除本地数据？

```powershell
python main.py clear-local-data --yes
```

清除 SQLite 数据库、Session 文件、输出目录内容。

### Q6：导出的 CSV 用 Excel 打开中文乱码？

本项目已使用 UTF-8 BOM 编码，正常情况下 Excel 直接打开不会乱码。如仍乱码，检查 Excel 版本或用 WPS 打开。

### Q7：如何添加自定义 Hashtag？

编辑 [config/hashtags.yaml](config/hashtags.yaml)，按现有格式追加：

```yaml
hashtags:
  - perfumemexico
  - tunuevohashtag    # 新增
```

或通过命令行临时指定：

```powershell
python main.py search --hashtags tunuevohashtag
```

### Q8：如何修改评分权重？

评分权重在 [app/analysis/scoring.py](app/analysis/scoring.py) 中定义（100 分制）。AGENTS.md §20 规定默认权重，修改需符合项目合规要求。

### Q9：为什么 "mx" 字母不判定为墨西哥？

按 AGENTS.md §15 要求，不得仅凭 `mx` 两字母判定（避免 "I love mx" 误判）。本项目将 `mx` 作为弱信号，需配合其他强信号（如城市名、`.mx` 网站、多个墨西哥 Hashtag）综合判定。

### Q10：项目是否绕过 Instagram 安全机制？

**否**。本项目严格遵守 AGENTS.md §5 约束，不实现任何验证码识别、Challenge 绕过、代理池、多账号轮换、设备指纹伪造等规避行为。遇平台限制立即停止。

---

## 附录：项目目录结构

```text
mexico-instagram-creator-finder/
├─ USAGE.md                   ← 本文档
├─ README.md                  ← 项目说明
├─ AGENTS.md (上级目录)        ← 项目最高约束
├─ LICENSE
├─ THIRD_PARTY_NOTICES.md
├─ pyproject.toml
├─ .env.example
├─ .gitignore
├─ main.py                    ← Typer 入口
│
├─ app/
│  ├─ cli.py                  ← 6 个 CLI 命令
│  ├─ config.py               ← Settings + YAML 合并
│  ├─ exceptions.py           ← SecurityStopError 等
│  ├─ logging_config.py       ← 脱敏过滤器
│  ├─ models.py               ← 10 个 Pydantic 模型
│  ├─ instagram/              ← 统一适配层
│  ├─ discovery/              ← 发现 + 去重 + 排除
│  ├─ analysis/               ← 6 个分析模块
│  ├─ storage/                ← SQLite + 断点续传
│  └─ export/                 ← CSV/JSON/XLSX 导出
│
├─ config/                    ← 5 个 YAML 配置
├─ data/                      ← SQLite 数据库
├─ output/                    ← 导出文件
├─ logs/                      ← 日志
└─ tests/                     ← 12 个测试文件 / 246 用例
```

---

**最后更新**：2026-07-18
**项目版本**：0.1.0
**测试状态**：256 passed / ruff check passed / ruff format check passed
**dry-run**：已支持（`python main.py search --dry-run`）
