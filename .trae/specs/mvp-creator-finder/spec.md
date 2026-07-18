# Mexico Instagram Creator Finder — 第一阶段 MVP Spec

## Why

需要基于 `subzeroid/instagrapi`（作为 pip 依赖）开发一个本地非商业的研究工具，用于从公开 Instagram 内容中发现面向墨西哥市场的香水、美妆、护肤、穿搭、生活方式和 UGC 内容创作者，并产出可人工审阅的导出结果。

当前工作目录 `d:\桌面\ins\instagrapi\` 是上游 `instagrapi` 源码仓库。按照 `AGENTS.md` 第 9.2 节约束，**禁止将 instagrapi 源码复制进本项目**，必须以 `pip install instagrapi` 形式作为依赖使用，且所有 `instagrapi.Client` 调用必须封装在项目内部统一适配层。

本 MVP 仅交付第一阶段范围：本地命令行工具 + SQLite 存储 + 三种导出格式 + 单元测试 + 中文 README，严格遵守 `AGENTS.md` 第 30 节 MVP 范围与第 31 节验收标准。

## What Changes

- **新增独立子项目**：在 `d:\桌面\ins\instagrapi\mexico-instagram-creator-finder\` 下创建完整项目根目录，自带 `pyproject.toml`、`README.md`、`LICENSE`、`.env.example`、`.gitignore`、`THIRD_PARTY_NOTICES.md`、`main.py`。
- **不修改任何上游 instagrapi 源码**：`d:\桌面\ins\instagrapi\instagrapi\` 子目录、上游 `pyproject.toml`、上游 `README.md`、上游 `tests/` 等保持原样。
- **不复制上游仓库根目录的 AGENTS.md**：项目根目录自带一份指向 workspace 级 AGENTS.md 的引用说明（或拷贝一份与 workspace 完全一致的副本，仅作项目内参考），不弱化任何约束。
- **模块化 `app/` 包**：config / instagram 适配层 / discovery / analysis / storage / export / cli / models / exceptions。
- **配置体系**：YAML 默认配置 + `.env` 环境变量 + 命令行参数，优先级「命令行 > 环境变量 > 用户 YAML > 默认」。
- **Instagram 统一适配层**：`app/instagram/client.py` + `app/instagram/session.py` + `app/instagram/rate_limit.py` + `app/instagram/mappers.py`，封装登录、Session 复用、请求间隔、异常转换、安全停止、日志脱敏、API 返回值映射。
- **发现模块**：Hashtag 帖子/Reels 搜索 → 提取作者用户名 → 去重 → 应用排除名单（TXT/CSV/Instagram URL）。
- **分析模块**：墨西哥地区信号识别、垂类分类、账号类型识别、近期内容指标、Reels 播放量统计（区分无 Reels/不可见/有播放量）、公开联系方式提取。
- **评分模块**：100 分透明评分（地区 25 + 垂类 25 + Reels 表现 20 + 活跃度 10 + 粉丝区间 10 + 联系方式 5 + 个人创作者 5），输出推荐级别 A/B/C/D。
- **存储模块**：SQLite + SQLAlchemy，支持任务、候选账号、资料、内容统计、评分、联系方式、断点信息。
- **导出模块**：CSV（UTF-8 BOM）、JSON、XLSX（openpyxl，字段宽度合理、长文本换行、URL 可点击）。
- **CLI**：Typer，提供 `search`、`task-status`、`export`、`validate-config`、`show-config`、`clear-local-data` 命令，使用 Rich 显示进度。
- **日志**：Python `logging`，脱敏（不输出密码、Cookie、Session、Authorization Header、私信、私人联系方式）。
- **测试**：pytest，全部使用 Mock/Fake Client，不登录真实 Instagram。
- **静态检查**：Ruff `check .` 与 `format --check .`。
- **中文 README**：完整 PowerShell 使用说明。
- **THIRD_PARTY_NOTICES.md**：声明使用 instagrapi（MIT License）、与 Instagram/Meta 无官方关联。

**BREAKING**：无（全新项目，无旧版本可破坏）。

## Impact

- **Affected specs**：本 spec 是项目首个 spec，无前置 spec 受影响。
- **Affected code**：
  - 新增：`mexico-instagram-creator-finder/` 整个子项目目录树。
  - 不修改：`d:\桌面\ins\instagrapi\instagrapi\`（上游源码）、上游 `pyproject.toml`、上游 `README.md`、上游 `tests/`、上游 `examples/`、上游 `docs/`、上游 `mkdocs.yml`、上游 `.pre-commit-config.yaml`、上游 `CODE_OF_CONDUCT.md`、上游 `CONTRIBUTING.md`、上游 `SECURITY.md`、上游 `LICENSE`、上游 `.github/`。
  - 不修改 workspace 级 `d:\桌面\ins\instagrapi\AGENTS.md`（用户已创建，保持原样）。
- **Instagram 接口兼容性风险**：依赖 `instagrapi` 非官方 Private API，Instagram 可能随时改变接口、要求验证或限流；本项目遇到 `ChallengeRequired`/`FeedbackRequired`/`PleaseWaitFewMinutes`/`ClientThrottledError`/HTTP 429/人工验证/账号安全警告时必须保存断点并停止，不得自动重试或绕过。
- **环境风险**：仅保证 Windows 10/11 + Python 3.11 可运行；用户需自备 Instagram 账号并在 `.env` 中配置 `IG_USERNAME`/`IG_PASSWORD`。

## ADDED Requirements

### Requirement: 项目结构独立于 instagrapi 源码

项目 SHALL 在 `d:\桌面\ins\instagrapi\mexico-instagram-creator-finder\` 下建立独立根目录，自带 `pyproject.toml`，将 `instagrapi` 声明为 pip 依赖（不直接 import 上游源码子目录）。

#### Scenario: 项目可独立安装

- **WHEN** 在 `mexico-instagram-creator-finder/` 目录执行 `pip install -e .`
- **THEN** 项目以可编辑模式安装成功，依赖列表包含 `instagrapi`、`typer`、`pydantic`、`pydantic-settings`、`sqlalchemy`、`pandas`、`openpyxl`、`rich`、`pyyaml`、`python-dotenv`、`pytest`、`ruff`
- **AND** 上游 `d:\桌面\ins\instagrapi\instagrapi\` 源码子目录未被修改

#### Scenario: 上游源码保持不变

- **WHEN** MVP 开发完成
- **THEN** `git status` 在 `d:\桌面\ins\instagrapi\` 显示上游 instagrapi 源码文件无修改
- **AND** 仅 `AGENTS.md`（用户已有）与新增的 `mexico-instagram-creator-finder/`、`.trae/specs/` 为 untracked

### Requirement: 统一 Instagram 适配层

所有 `instagrapi.Client` 调用 SHALL 通过 `app/instagram/client.py` 封装，业务模块不得直接创建 `Client()`。

#### Scenario: 登录并复用 Session

- **WHEN** 调用 `InstagramClient.login_from_env()`
- **THEN** 从 `IG_USERNAME`/`IG_PASSWORD` 环境变量读取凭据
- **AND** 若 `.instagram_session.json` 存在则加载复用
- **AND** 登录成功后保存 Session 到 `instagram.session_file` 配置路径
- **AND** 密码不写入日志、不写入数据库、不写入 YAML

#### Scenario: 安全停止

- **WHEN** Instagram 抛出 `ChallengeRequired`/`FeedbackRequired`/`PleaseWaitFewMinutes`/`ClientThrottledError`/HTTP 429/人工验证要求/账号安全警告
- **THEN** 适配层捕获异常并转换为项目内部 `SecurityStopError`
- **AND** 立即保存当前任务断点到 SQLite
- **AND** 不进行任何自动重试
- **AND** CLI 显示清晰的停止原因

#### Scenario: 网络错误有限重试

- **WHEN** 发生临时 DNS 错误、连接超时、临时服务器错误
- **THEN** 最多重试 `instagram.retry_network_errors` 次（默认 2 次）
- **AND** 每次重试采用指数退避
- **AND** 429/Challenge/FeedbackRequired 等安全异常不重试

#### Scenario: 请求间隔

- **WHEN** 适配层发起任意 Instagram 请求
- **THEN** 请求之间随机等待 `instagram.request_delay_min_seconds` ~ `instagram.request_delay_max_seconds` 秒（默认 4-8 秒）
- **AND** 不使用线程池或异步批量并发

### Requirement: YAML 配置系统

所有可调参数 SHALL 进入配置系统，不得硬编码在业务函数中。

#### Scenario: 配置优先级

- **WHEN** 同时存在命令行参数、环境变量、用户 YAML、默认 YAML
- **THEN** 优先级为「命令行参数 > 环境变量 > 用户 YAML > 默认配置」
- **AND** `validate-config` 命令可校验配置完整性
- **AND** `show-config` 命令可显示最终合并后的配置（脱敏，不显示密码）

#### Scenario: 默认配置保守

- **WHEN** 用户未提供任何配置
- **THEN** 默认粉丝区间为 20,000-300,000
- **AND** 默认请求间隔 4-8 秒
- **AND** 默认最大 Hashtag 数 15、每 Hashtag 媒体数 20、最大候选账号 300、最大分析账号 100
- **AND** 默认 `stop_on_rate_limit=true`、`stop_on_challenge=true`

### Requirement: Hashtag 发现与去重

#### Scenario: 从 Hashtag 提取候选作者

- **WHEN** 执行 `python main.py search --hashtags perfumemexico fraganciasmexico`
- **THEN** 对每个 Hashtag 调用 `cl.hashtag_medias_recent` 与 `cl.hashtag_medias_reels_v1`（按配置数量）
- **AND** 提取每条公开媒体对应的作者 `username`
- **AND** 累计候选账号数不超过 `discovery.max_candidates`（默认 300）
- **AND** 每完成一个 Hashtag 后保存断点

#### Scenario: 用户名去重

- **WHEN** 同一 username 被多个 Hashtag 命中
- **THEN** 仅保留一条候选记录
- **AND** 记录该账号的所有来源 Hashtag 列表

### Requirement: 排除名单解析

#### Scenario: 多格式排除名单

- **WHEN** 通过 `--exclude` 传入 TXT/CSV/XLSX 文件或之前导出的结果
- **THEN** 解析出待排除用户名集合
- **AND** 标准化：去除 `@`、去除 URL、转小写、去除末尾 `/`、去重、忽略空行、忽略 `#` 注释
- **AND** 支持 Instagram URL 形式（`https://www.instagram.com/username/`）
- **AND** 每个被排除账号记录 `excluded`/`exclusion_source`/`exclusion_reason`

### Requirement: 公开账号资料获取与粉丝筛选

#### Scenario: 获取公开资料

- **WHEN** 候选账号进入分析阶段
- **THEN** 调用 `cl.user_info_by_username` 获取公开字段
- **AND** 保存 `username`/`full_name`/`biography`/`profile_url`/`profile_pic_url`/`follower_count`/`following_count`/`media_count`/`is_private`/`is_verified`/`is_business`/`category_name`/`business_category_name`/`external_url`/`public_email`
- **AND** 默认仅保存头像 URL，不下载高清头像

#### Scenario: 粉丝范围筛选

- **WHEN** `filters.min_followers=20000` 且 `filters.max_followers=300000`
- **THEN** 仅保留粉丝数在区间内的账号
- **AND** `filters.require_public_account=true` 时排除私密账号
- **AND** 粉丝数不作为唯一筛选依据，仍需结合其他信号

### Requirement: 墨西哥地区信号识别

#### Scenario: 多信号墨西哥识别

- **WHEN** 分析账号的墨西哥地区可信度
- **THEN** 综合以下信号：Biography 中的国家/城市/州名称、公开 business address、来源 Hashtag、近期 Caption、公开地点标签、`.mx` 网站、用户公开展示的墨西哥电话国家代码（仅辅助信号）
- **AND** 不得仅凭 `mx` 两字母、西班牙语、墨西哥国旗表情、单个 Hashtag 直接判定为墨西哥
- **AND** 输出 `mexico_confidence_score`（0-1）、`mexico_signals`（列表）、`detected_country`、`detected_state`、`detected_city`
- **AND** 每个信号可解释

### Requirement: 垂类内容分类

#### Scenario: 多信号垂类分类

- **WHEN** 判定账号垂类
- **THEN** 综合 Biography、Full name、Category、来源 Hashtag、近期 Caption、近期内容 Hashtag
- **AND** 不得仅依赖单个关键词
- **AND** 输出 `primary_niche`（perfume/beauty/skincare/makeup/fashion/lifestyle/UGC/general/brand/media/agency）+ `niche_scores` + `niche_signals` + `classification_reasons`

### Requirement: 账号类型识别

#### Scenario: 区分个人创作者与品牌/媒体

- **WHEN** 判定账号类型
- **THEN** 输出 `account_type`（personal_creator/ugc_creator/brand/shop/media/news/agency/marketing/fan_reposter/topic_aggregator）+ `account_type_confidence` + `account_type_reasons`
- **AND** 不直接删除疑似账号，仅标记
- **AND** `filters.exclude_brands=true` 与 `filters.exclude_media_accounts=true` 时在筛选中默认隐藏品牌/媒体账号，但用户可查看排除原因

### Requirement: 近期内容指标与 Reels 播放统计

#### Scenario: 近 12 条公开内容统计

- **WHEN** 获取账号近期内容
- **THEN** 默认分析最近 12 条公开内容（`analysis.recent_media_amount`）
- **AND** 输出 `recent_media_checked`/`recent_reels_checked`/`last_post_date`/`days_since_last_post`/`average_likes`/`median_likes`/`average_comments`/`median_comments`/`average_visible_reel_views`/`median_visible_reel_views`/`maximum_visible_reel_views`/`posting_frequency`/`reels_view_data_available`

#### Scenario: 三态 Reels 播放量区分

- **WHEN** 账号没有发布 Reels
- **THEN** `reels_view_data_available="no_reels"`，播放量字段为 `None`
- **WHEN** 账号发布了 Reels 但播放量不可见（`like_and_view_counts_disabled=true` 或 `view_count=None`）
- **THEN** `reels_view_data_available="not_visible"`，播放量字段为 `None`
- **WHEN** 账号有可计算播放量
- **THEN** `reels_view_data_available="available"`，输出平均/中位/最大播放量
- **AND** 不得用 0 混淆以上三种状态
- **AND** 中位数优先用于筛选，平均值仅作补充

### Requirement: 公开联系方式提取

#### Scenario: 仅提取公开联系方式

- **WHEN** 提取账号联系方式
- **THEN** 允许提取：格式正确的公开邮箱、`mailto:` 链接、`wa.me` 链接、WhatsApp Business 公开链接、Linktree、Beacons、公开网站、Instagram 公开 `public_email`
- **AND** 输出 `public_email`/`public_whatsapp_url`/`external_url`/`contact_source`/`has_public_contact`
- **AND** 不得根据姓名推测邮箱、不得拼接域名邮箱、不得将普通数字识别为 WhatsApp、不得访问登录后才能看到的联系方式、不得访问泄露数据库
- **AND** 每个联系方式记录来源

### Requirement: 100 分透明评分

#### Scenario: 评分计算

- **WHEN** 对账号计算评分
- **THEN** 总分 100，分项为：墨西哥地区可信度 25、垂类匹配度 25、近期 Reels 表现 20、内容活跃度 10、粉丝区间匹配度 10、公开商务联系方式 5、个人创作者可信度 5
- **AND** 输出 `total_score`/`score_breakdown`/`recommendation_level`（A/B/C/D）/`recommendation_reasons`
- **AND** A=重点人工检查、B=值得人工检查、C=信息不足、D=不符合当前条件
- **AND** 评分仅为与搜索条件的匹配程度，不描述个人价值或外貌

### Requirement: SQLite 存储与断点续传

#### Scenario: SQLite 持久化

- **WHEN** 任务运行
- **THEN** 数据写入 `data/app.db`（SQLite + SQLAlchemy）
- **AND** 表包括：搜索任务、Hashtag、候选账号、账号资料、内容统计、评分结果、公开联系方式、发现来源、分析状态、错误状态、断点信息、收集时间
- **AND** 不保存密码、Session、私信、私密内容、推测邮箱、视频文件、原始图片

#### Scenario: 断点续传

- **WHEN** 任务异常退出或用户手动停止
- **THEN** 已完成 Hashtag、已发现用户名、已分析用户名、失败账号、错误原因、当前状态、停止原因已保存
- **AND** `python main.py search --resume` 可恢复任务且不重复请求已分析账号
- **AND** `python main.py task-status` 显示当前任务状态
- **AND** `python main.py search --reset-task` 可重置任务

### Requirement: 三种格式导出

#### Scenario: CSV 导出

- **WHEN** 执行 `python main.py export`
- **THEN** 默认导出 CSV/JSON/XLSX 三种格式到 `output/` 目录
- **AND** CSV 使用 UTF-8 BOM，中文与西班牙语重音字符不乱码
- **AND** 默认排序：`total_score` 降序 → `median_visible_reel_views` 降序 → `followers` 降序
- **AND** 不导出密码与 Session

#### Scenario: XLSX 导出

- **WHEN** 生成 XLSX
- **THEN** 字段宽度合理、长文本自动换行、URL 可点击
- **AND** 使用 openpyxl

### Requirement: Typer CLI

#### Scenario: 命令完整

- **WHEN** 用户执行 CLI
- **THEN** 至少支持：`search`、`search --hashtags`、`search --min-followers`、`search --max-followers`、`search --exclude`、`search --resume`、`task-status`、`export`、`validate-config`、`show-config`、`clear-local-data`
- **AND** 使用 Rich 显示：当前任务、阶段、Hashtag、候选账号数、已分析账号数、已跳过数、错误数、停止原因、输出路径
- **WHEN** 未设置 `IG_USERNAME`/`IG_PASSWORD`
- **THEN** 显示清晰提示，不直接输出复杂异常堆栈

### Requirement: 日志脱敏

#### Scenario: 日志不泄露敏感信息

- **WHEN** 任何日志输出
- **THEN** 不记录密码、Cookie、完整 Session、Authorization Header、私信内容、私人联系方式
- **AND** 可记录任务 ID、用户名、请求类型、成功/失败、错误分类、停止原因、运行时间
- **AND** 生产代码不使用大量无结构 `print()`

### Requirement: 单元测试

#### Scenario: 纯业务逻辑可测

- **WHEN** 执行 `pytest`
- **THEN** 全部测试通过，且测试中不登录真实 Instagram
- **AND** 至少覆盖：用户名标准化、Instagram URL 解析、排除名单、墨西哥地区识别、城市/州识别、垂类分类、品牌账号识别、邮箱提取、WhatsApp 链接提取、Reels 指标、无播放量状态、评分系统、配置优先级、SQLite 存储、断点续传、CSV/JSON/XLSX 导出
- **AND** 使用 Mock/Fake Client 与固定测试数据

#### Scenario: 静态检查

- **WHEN** 执行 `ruff check .` 与 `ruff format --check .`
- **THEN** 无错误

### Requirement: 中文 README 与第三方声明

#### Scenario: README 完整

- **WHEN** 用户阅读 `mexico-instagram-creator-finder/README.md`
- **THEN** 包含：项目简介、合规声明、Windows PowerShell 安装与使用说明、`.env` 配置说明、CLI 命令示例、输出格式说明、常见问题、停止原因说明
- **AND** 全中文

#### Scenario: 第三方声明

- **WHEN** 用户阅读 `THIRD_PARTY_NOTICES.md`
- **THEN** 声明使用 `instagrapi`（MIT License）
- **AND** 声明与 Instagram/Meta 无官方关联
- **AND** 声明使用者需自行遵守平台规则

### Requirement: 默认 Hashtag 列表

#### Scenario: 内置墨西哥垂类 Hashtag

- **WHEN** 用户未通过 `--hashtags` 指定
- **THEN** 默认加载 `config/hashtags.yaml`，至少包含：`perfumemexico`/`perfumesmexico`/`fraganciasmexico`/`perfumesdemujer`/`perfumessolidos`/`bellezamexicana`/`bellezamexico`/`maquillajemexico`/`skincaremexico`/`cuidadodelapielmx`/`beautybloggermexico`/`bloggeramexicana`/`creadoradecontenidomx`/`ugcmexico`/`lifestylemexico`/`modamexicana`/`cdmxblogger`/`mexicoblogger`
- **AND** 实际请求的 Hashtag 数量不超过 `discovery.max_hashtags`（默认 15）

## MODIFIED Requirements

无（本项目为全新 spec，无前置版本可修改）。

## REMOVED Requirements

无。
