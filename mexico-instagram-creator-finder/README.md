# Mexico Instagram Creator Finder

**墨西哥 Instagram 内容创作者发现工具**

> 一个基于 `instagrapi` 的本地研究工具，用于从公开 Instagram 内容中发现墨西哥本地或面向墨西哥市场的内容创作者，覆盖香水、美妆、护肤、穿搭、生活方式与 UGC 等垂类。

---

## 目录

1. [项目简介](#1-项目简介)
2. [合规声明](#2-合规声明)
3. [环境要求](#3-环境要求)
4. [安装步骤（PowerShell）](#4-安装步骤powershell)
5. [配置 .env](#5-配置-env)
6. [配置文件说明](#6-配置文件说明)
7. [CLI 命令示例（PowerShell）](#7-cli-命令示例powershell)
8. [主流程说明](#8-主流程说明)
9. [评分体系](#9-评分体系)
10. [输出格式说明](#10-输出格式说明)
11. [断点续传](#11-断点续传)
12. [停止原因说明](#12-停止原因说明)
13. [常见问题](#13-常见问题)
14. [数据安全](#14-数据安全)
15. [第三方声明](#15-第三方声明)
16. [许可证](#16-许可证)
17. [当前限制](#17-当前限制)
18. [Instagram 接口兼容性风险](#18-instagram-接口兼容性风险)

---

## 1. 项目简介

**Mexico Instagram Creator Finder** 是一个在开源项目 `subzeroid/instagrapi` 基础能力之上开发的本地研究工具。

**项目用途：**

- 搜索公开的 Instagram 内容；
- 从公开帖子、Reels、Hashtag 和地点中发现内容创作者；
- 筛选墨西哥本地或面向墨西哥市场的创作者；
- 分析公开主页及公开内容数据；
- 识别适合香水、美妆、护肤、穿搭和生活方式内容的创作者；
- 导出研究结果供人工判断。

**目标垂类：**

- 香水 / 固体香水 / 香氛
- 美妆 / 化妆
- 护肤
- 穿搭
- 女性生活方式
- UGC 内容制作
- 礼物推荐 / 日常好物分享
- 墨西哥本地消费内容

**目标市场：** 墨西哥

**目标粉丝区间（默认）：** 20,000 — 300,000（可在配置文件或命令行中修改）

**适用场景：**

- 个人研究；
- 内部测试；
- 非商业化的软件开发学习；
- 人工筛选公开内容创作者。

---

## 2. 合规声明

本项目仅用于个人研究、内部测试与非商业化的软件开发学习。使用本项目前，请仔细阅读以下声明：

### 2.1 项目不是

- Instagram 营销群发工具；
- 自动私信工具；
- 涨粉工具；
- 养号工具；
- 账号控制工具；
- 数据倒卖平台；
- 联系方式采集平台；
- 绕过 Instagram 限制的工具。

### 2.2 不实现的功能

本项目**绝不实现**以下功能（包括直接实现、隐藏实现、实验性实现或通过配置开启）：

- 自动私信 / 批量私信 / 定时私信；
- 自动关注 / 批量关注 / 自动取消关注；
- 自动点赞 / 自动评论 / 自动转发 / 自动收藏；
- 自动查看 Story；
- 自动回复评论或私信；
- 自动发送合作邀请；
- 根据搜索结果自动联系博主。

即使 `instagrapi` 提供对应接口，本项目也不会调用。

### 2.3 不绕过平台风控

本项目不实现：

- 验证码自动识别；
- Challenge 自动绕过；
- 短信/邮箱验证绕过；
- 设备指纹伪造；
- Cookie 窃取或导入；
- Session 劫持；
- 多账号轮换 / 账号池 / 代理池；
- 通过代理绕过速率限制；
- 绕过登录或权限限制；
- 未授权访问私密账号；
- 抓取已删除或隐藏内容。

**遇到平台限制时立即停止**，而不是尝试绕过。

### 2.4 不收集私人数据

本项目不：

- 猜测电子邮箱；
- 推测私人手机号码；
- 从泄露数据库查找联系方式；
- 抓取私密账号内容；
- 保存登录账号的私信；
- 推测种族、宗教、健康、政治倾向等敏感属性。

仅提取用户主动公开的商务联系方式（公开邮箱、`wa.me` 链接、Linktree、Beacons、公开网站等），并记录来源。

### 2.5 与 Instagram / Meta 的关系

- 本项目与 Instagram、Meta Platforms, Inc. 及其关联公司**无任何官方关联**；
- 本项目不是 Instagram 官方工具，也未获得 Instagram 或 Meta 的授权或认可；
- 使用者需自行遵守 Instagram 平台规则、服务条款及适用法律法规；
- 使用者需自行承担因使用本项目而产生的全部责任与风险。

---

## 3. 环境要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 10 / Windows 11（仅在本环境验证） |
| Python | 3.11 或更高版本 |
| 包管理 | pip（随 Python 安装） |
| Instagram 账号 | 一个有效的 Instagram 账号（用于读取公开数据） |
| 网络 | 可访问 Instagram 的网络环境 |

> 本项目优先保证 Windows 10/11 + Python 3.11 可运行。其他操作系统（macOS/Linux）理论兼容，但未做完整验证。

---

## 4. 安装步骤（PowerShell）

以下命令在 **Windows PowerShell** 中执行。

### 4.1 进入项目目录

```powershell
cd D:\桌面\ins\instagrapi\mexico-instagram-creator-finder
```

### 4.2 创建虚拟环境

```powershell
python -m venv .venv
```

### 4.3 激活虚拟环境

```powershell
.\.venv\Scripts\Activate.ps1
```

> **若提示"无法加载脚本，因为在此系统上禁止运行脚本"**，请先执行：
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```
>
> 然后再次激活。

激活后，命令行前会出现 `(.venv)` 前缀。

### 4.4 升级 pip（推荐）

```powershell
python -m pip install --upgrade pip
```

### 4.5 安装项目与开发依赖

```powershell
pip install -e ".[dev]"
```

该命令会安装：

- 项目运行依赖（`instagrapi`、`typer`、`pydantic`、`sqlalchemy`、`pandas`、`openpyxl`、`rich`、`pyyaml`、`python-dotenv` 等）；
- 开发依赖（`pytest`、`ruff`）。

### 4.6 验证安装

```powershell
python main.py --help
```

若看到 Typer 的帮助信息（包含 `search`、`task-status`、`export` 等命令），说明安装成功。

---

## 5. 配置 .env

Instagram 用户名和密码只能从**环境变量**或**本地 `.env` 文件**读取，**绝不**写入源码、YAML、日志或数据库。

### 5.1 复制示例文件

```powershell
Copy-Item .env.example .env
```

### 5.2 编辑 `.env`

用文本编辑器打开 `.env`，填入 Instagram 账号：

```text
IG_USERNAME=your_username
IG_PASSWORD=your_password
```

### 5.3 安全说明

- `.env` 已在 `.gitignore` 中，**不会被提交到 Git**；
- 密码不写入日志；
- 密码不写入数据库；
- 密码不写入 YAML 配置；
- 异常信息中不输出密码；
- 界面与 CLI 不回显密码。

### 5.4 临时环境变量（可选）

如不想使用 `.env`，也可在当前 PowerShell 会话中临时设置：

```powershell
$env:IG_USERNAME = "your_username"
$env:IG_PASSWORD = "your_password"
```

---

## 6. 配置文件说明

所有可调参数集中在 `config/` 目录下，**禁止在业务函数中硬编码**。

配置优先级：

```text
命令行参数 > 环境变量 > 用户 YAML 配置 > 默认配置
```

### 6.1 `config/default.yaml`

主配置文件，包含：

| 配置块 | 关键字段 | 默认值 |
| --- | --- | --- |
| `instagram` | `session_file` | `.instagram_session.json` |
|  | `request_delay_min_seconds` | 4 |
|  | `request_delay_max_seconds` | 8 |
|  | `retry_network_errors` | 2 |
|  | `stop_on_rate_limit` | true |
|  | `stop_on_challenge` | true |
| `discovery` | `max_hashtags` | 15 |
|  | `media_per_hashtag` | 20 |
|  | `max_candidates` | 300 |
|  | `max_profiles_to_analyze` | 100 |
|  | `seed_expansion_depth` | 1 |
|  | `max_accounts_per_seed` | 20 |
| `filters` | `min_followers` | 20000 |
|  | `max_followers` | 300000 |
|  | `require_public_account` | true |
|  | `require_mexico_signal` | true |
|  | `maximum_days_since_last_post` | 90 |
|  | `minimum_recent_media_count` | 3 |
|  | `minimum_median_reel_views` | 2000 |
|  | `exclude_brands` | true |
|  | `exclude_media_accounts` | true |
| `analysis` | `recent_media_amount` | 12 |
|  | `maximum_caption_length` | 3000 |
| `checkpoint` | `enabled` | true |
|  | `database_file` | `data/app.db` |
| `output` | `directory` | `output` |
|  | `formats` | csv, json, xlsx |

### 6.2 `config/hashtags.yaml`

默认 18 个垂类 Hashtag，覆盖香水、美妆、护肤、穿搭、生活方式、UGC 等方向，例如：

- `perfumemexico`、`perfumesmexico`、`fraganciasmexico`
- `bellezamexicana`、`bellezamexico`、`maquillajemexico`
- `skincaremexico`、`cuidadodelapielmx`
- `creadoradecontenidomx`、`ugcmexico`
- `lifestylemexico`、`modamexicana`
- `cdmxblogger`、`mexicoblogger`

### 6.3 `config/mexico_locations.yaml`

墨西哥 32 个州（含 CDMX）的名称、别名与主要城市，用于地区信号识别。例如：

- Aguascalientes、Baja California、Baja California Sur、Campeche、Chiapas、Chihuahua、Coahuila、Colima、Ciudad de México（CDMX）、Durango、México（EDOMEX）等。

### 6.4 `config/niche_keywords.yaml`

垂类关键词配置，按以下分类组织：

- `perfume`（香水）：perfume、fragancia、perfume sólido、eau de parfum 等；
- `beauty`（美妆）：belleza、beauty、cosméticos 等；
- `skincare`、`makeup`、`fashion`、`lifestyle`、`UGC` 等垂类。

每个垂类同时包含 `keywords` 与 `hashtags`。

### 6.5 `config/excluded_account_terms.yaml`

用于识别并默认排除非个人创作者账号，包含：

- `brand_terms`（品牌）：oficial、official、store、shop、tienda、boutique、marca、brand；
- `media_terms`（媒体）：news、noticias、prensa、magazine、revista、media；
- `agency_terms`（经纪/机构）：agency、agencia、management、talent、representante；
- `shop_terms`（店铺）、`fan_terms`（粉丝搬运）等。

### 6.6 校验与查看配置

```powershell
python main.py validate-config
python main.py show-config
```

`show-config` 输出脱敏后的最终合并配置，不会显示密码。

---

## 7. CLI 命令示例（PowerShell）

本项目使用 Typer 提供命令行界面。所有命令在项目根目录、虚拟环境已激活的前提下执行。

### 7.1 搜索创作者

```powershell
python main.py search
```

使用 `config/hashtags.yaml` 中的默认 Hashtag 列表开始搜索。

### 7.2 指定 Hashtag

```powershell
python main.py search --hashtags perfumemexico fraganciasmexico
```

多个 Hashtag 用空格分隔，**不带 `#`**。

### 7.3 指定粉丝区间

```powershell
python main.py search --min-followers 20000 --max-followers 150000
```

### 7.4 排除名单

```powershell
python main.py search --exclude data/excluded.txt
```

可多次指定，混合使用文件路径与用户名：

```powershell
python main.py search --exclude data/excluded.txt --exclude someone_user --exclude https://www.instagram.com/another_user/
```

排除名单支持 TXT / CSV / XLSX / Instagram URL / 直接用户名，自动标准化（去 `@`、去 URL、转小写、去末尾 `/`、去重、忽略 `#` 注释与空行）。

### 7.5 恢复任务

```powershell
python main.py search --resume
```

从上次断点继续，不会重复分析已完成账号。

### 7.6 重置任务

```powershell
python main.py search --reset-task
```

清空当前任务断点后从头开始。

### 7.7 查看任务状态

```powershell
python main.py task-status
```

显示最近 5 个任务的概要。指定任务 ID 查看详情：

```powershell
python main.py task-status --task-id task_20260718_120000_abcd1234
```

### 7.8 导出结果

```powershell
python main.py export
```

按 `config/default.yaml` 中 `output.formats` 导出（默认 CSV/JSON/XLSX 三种）。也可指定格式与任务：

```powershell
python main.py export --formats csv xlsx --task-id task_20260718_120000_abcd1234
```

### 7.9 校验配置

```powershell
python main.py validate-config
```

检查配置完整性，并显示粉丝区间、请求间隔、最大候选数等关键参数。

### 7.10 显示配置（脱敏）

```powershell
python main.py show-config
```

输出最终合并后的配置（JSON 格式，不含密码）。

### 7.11 清除本地数据

```powershell
python main.py clear-local-data
```

交互式确认后删除 SQLite 数据库、Session 文件与输出目录内容。跳过确认：

```powershell
python main.py clear-local-data --yes
```

---

## 8. 主流程说明

执行 `search` 命令时，主流程分为 6 个阶段：

```text
阶段 1/6  登录 Instagram
          读取 .env 凭据，登录并复用 Session

阶段 2/6  发现候选账号
          遍历 Hashtag 近期公开帖子/Reels，提取作者

阶段 3/6  去重
          对候选账号按用户名标准化去重

阶段 4/6  应用排除名单
          按用户提供的排除文件/用户名过滤

阶段 5/6  获取资料与分析
          - 拉取公开主页资料
          - 粉丝区间筛选
          - 私密账号筛选
          - 拉取近期公开内容
          - 计算内容指标（点赞/评论/Reels 播放量中位数）
          - 墨西哥地区信号识别
          - 垂类分类
          - 账号类型识别
          - 公开联系方式提取
          - 停更/最低播放量/品牌媒体筛选
          - 评分

阶段 6/6  导出结果
          按 CSV / JSON / XLSX 三种格式输出到 output/ 目录
```

CLI 在每个阶段会显示当前阶段、当前 Hashtag、候选账号数、已分析账号数、已跳过数、错误数与输出路径。

---

## 9. 评分体系

评分透明、可配置、可测试。默认总分 **100 分**，分项如下：

| 维度 | 分值 | 说明 |
| --- | --- | --- |
| 墨西哥地区可信度 | 25 | 基于多个公开信号（biography、地点、Hashtag 等）综合判断 |
| 垂类匹配度（香水/美妆/护肤/穿搭/生活方式/UGC） | 25 | 基于关键词与 Hashtag 综合分类 |
| 近期 Reels 表现 | 20 | 以中位可见播放量为主，平均值仅作补充 |
| 内容活跃度 | 10 | 最近更新时间、发布频率、近期内容数量 |
| 粉丝区间匹配度 | 10 | 与配置的粉丝区间匹配程度 |
| 公开商务联系方式 | 5 | 是否有公开邮箱 / WhatsApp / Linktree 等 |
| 个人创作者可信度 | 5 | 是否为个人创作者（排除品牌/媒体/机构） |

### 9.1 推荐级别

| 级别 | 分数区间 | 含义 |
| --- | --- | --- |
| **A** | ≥ 80 | 重点人工检查 |
| **B** | ≥ 60 | 值得人工检查 |
| **C** | ≥ 40 | 信息不足 |
| **D** | < 40 | 不符合当前条件 |

### 9.2 评分输出字段

```text
total_score
score_breakdown
recommendation_level
recommendation_reasons
```

> 评分仅表示与当前搜索条件的匹配程度，**不**描述对个人价值、外貌或可信人格的判断。

---

## 10. 输出格式说明

支持三种导出格式，输出到 `output/` 目录，文件名形如 `creators_<task_id>.csv` / `.json` / `.xlsx`。

### 10.1 CSV

- 编码：**UTF-8 with BOM**，确保 Excel 打开中文与西班牙语重音字符不乱码；
- 默认排序：`total_score` 降序 → `median_visible_reel_views` 降序 → `follower_count` 降序；
- 不导出密码、Cookie、Session。

### 10.2 JSON

- 按统一字段顺序输出 key；
- 复杂字段（如 `mexico_signals`、`score_breakdown`）以对象/数组形式保留。

### 10.3 XLSX

- 字段宽度合理，长文本自动换行；
- URL 字段可点击；
- 中文与西班牙语重音字符正常显示。

### 10.4 导出字段概要

输出统一包含以下字段（按顺序）：

```text
username                       用户名
full_name                      全名
profile_url                    主页 URL
follower_count                 粉丝数
following_count                关注数
media_count                    公开内容数
is_private                     是否私密账号
is_verified                    是否已认证
is_business                    是否商业账号
category_name                  类目
business_category_name         商业类目
biography                      个人简介
external_url                   外链
profile_pic_url                头像 URL
public_email                   公开邮箱
public_whatsapp_url            公开 WhatsApp 链接
linktree_url                   Linktree 链接
beacons_url                    Beacons 链接
has_public_contact             是否有公开联系方式
contact_source                 联系方式来源
detected_country               识别到的国家
detected_state                 识别到的州
detected_city                  识别到的城市
mexico_confidence_score        墨西哥可信度分数
mexico_signals                 墨西哥信号列表
primary_niche                  主垂类
niche_scores                   垂类评分
account_type                   账号类型
account_type_confidence        账号类型可信度
recent_media_checked           已检查的近期内容数
recent_reels_checked           已检查的近期 Reels 数
last_post_date                 最近发布时间
days_since_last_post           距上次发布天数
average_likes                  平均点赞
median_likes                   中位点赞
average_comments               平均评论
median_comments                中位评论
average_visible_reel_views     平均可见 Reels 播放
median_visible_reel_views      中位可见 Reels 播放
maximum_visible_reel_views     最大可见 Reels 播放
posting_frequency              发布频率
reels_view_data_available      Reels 播放数据可用性
total_score                    总分
score_breakdown                评分明细
recommendation_level           推荐级别（A/B/C/D）
recommendation_reasons         推荐理由
source_hashtags                来源 Hashtag
```

`reels_view_data_available` 区分三种情况：`no_reels`（未发布 Reels）、`not_visible`（已发布但播放量不可见）、`available`（有可计算的播放量），不会用 0 混淆。

---

## 11. 断点续传

断点续传是本项目的核心功能之一，**保证任务异常退出或手动停止后可恢复**。

### 11.1 自动保存断点

每完成一个关键步骤后保存：

- 已完成的 Hashtag；
- 已发现的用户名；
- 已分析的用户名；
- 失败账号与错误原因；
- 当前任务状态；
- 停止原因。

### 11.2 恢复任务

```powershell
python main.py search --resume
```

恢复时**不会重复请求已分析过的账号**，已完成的 Hashtag 也会跳过。

### 11.3 查看任务状态

```powershell
python main.py task-status
python main.py task-status --task-id <任务ID>
```

显示任务状态、已完成 Hashtag、已发现/已分析/失败账号数等。

### 11.4 重置任务

```powershell
python main.py search --reset-task
```

清空当前任务断点，从头开始。

---

## 12. 停止原因说明

当 Instagram 触发安全机制时，本项目**立即停止**当前任务并保存断点，**不自动重试、不绕过**。

### 12.1 安全停止触发条件

| 触发条件 | 含义 |
| --- | --- |
| `ChallengeRequired` | Instagram 要求验证码挑战 |
| `FeedbackRequired` | 平台要求反馈处理 |
| `PleaseWaitFewMinutes` | 平台要求稍候几分钟再试 |
| `ClientThrottledError` | 客户端被限流 |
| HTTP 429 | 请求频率过高被拒绝 |
| 人工验证要求 | Instagram 要求人工验证 |
| 账号安全警告 | 账号被判定存在安全风险 |

此外，登录异常、Session 被判定失效等情况也会触发停止。

### 12.2 停止后行为

- 任务状态标记为 `stopped`，并记录停止原因；
- 自动保存断点；
- CLI 显示红色面板提示，并建议使用 `--resume` 恢复；
- **不自动重试**上述任何异常。

### 12.3 可重试的异常

仅以下临时网络异常可重试，最多 2 次，使用指数退避：

- 临时 DNS 错误；
- 连接超时；
- 临时服务器错误；
- 可明确判断为短暂网络异常的问题。

---

## 13. 常见问题

### Q1：没有设置环境变量怎么办？

执行任何需要登录的命令时，CLI 会显示清晰提示：

```text
未检测到 Instagram 账号凭据

请在项目根目录创建 `.env` 文件并配置：
  IG_USERNAME=your_username
  IG_PASSWORD=your_password

或通过环境变量设置：
  PowerShell:  $env:IG_USERNAME='your_username'; $env:IG_PASSWORD='your_password'
  CMD:         set IG_USERNAME=your_username && set IG_PASSWORD=your_password
```

按提示配置 `.env` 后重试即可。不会输出复杂异常堆栈。

### Q2：遇到 `ChallengeRequired` 怎么办？

这是 Instagram 触发了验证码挑战。本项目**不会自动绕过**。处理步骤：

1. 任务已自动停止并保存断点；
2. 在手机或浏览器上手动完成 Instagram 的安全验证；
3. 确认账号状态正常后，使用 `python main.py search --resume` 恢复任务；
4. 如频繁触发，请暂停使用并检查账号安全设置。

### Q3：如何修改粉丝区间？

三种方式（优先级从高到低）：

**命令行参数（临时）：**

```powershell
python main.py search --min-followers 10000 --max-followers 200000
```

**修改 `config/default.yaml`（持久）：**

```yaml
filters:
  min_followers: 10000
  max_followers: 200000
```

**查看当前配置：**

```powershell
python main.py show-config
```

### Q4：如何排除已有账号？

使用 `--exclude` 参数，支持文件路径或用户名，可多次指定：

```powershell
python main.py search --exclude data/excluded.txt
python main.py search --exclude data/excluded.txt --exclude another_user
```

排除名单文件格式示例（`data/excluded.txt`）：

```text
# 注释行忽略
user_one
@user_two
https://www.instagram.com/user_three/
user_four/
```

每行一个账号，自动标准化：去 `@`、去 URL、转小写、去末尾 `/`、去重、忽略 `#` 开头的注释与空行。

### Q5：如何重新开始任务？

```powershell
python main.py search --reset-task
```

或彻底清除所有本地数据后重启：

```powershell
python main.py clear-local-data --yes
python main.py search
```

### Q6：任务中途断了怎么办？

直接恢复即可：

```powershell
python main.py search --resume
```

恢复时会跳过已完成的 Hashtag 与已分析的账号，不重复请求。

### Q7：如何只导出特定格式？

```powershell
python main.py export --formats csv
python main.py export --formats csv xlsx
```

### Q8：Session 文件在哪？会被提交到 Git 吗？

Session 默认保存在项目根目录 `.instagram_session.json`，已在 `.gitignore` 中排除，**不会被提交**。可使用 `python main.py clear-local-data` 一并清除。

---

## 14. 数据安全

### 14.1 不保存的敏感数据

- Instagram 密码；
- 完整 Session（仅保存本地 Session 文件，不上传 Git）；
- 完整 Cookie；
- Authorization Header；
- 私信内容；
- 私密账号内容；
- 未公开电话号码；
- 推测出的邮箱；
- 下载的视频文件；
- 大量原始图片；
- 敏感属性推断结果。

### 14.2 日志脱敏

日志中**不**记录：

- 密码、Cookie、完整 Session、Authorization Header；
- 私信内容；
- 私人联系方式。

日志**可以**记录：

- 任务 ID、用户名、请求类型、成功/失败、错误分类、停止原因、运行时间。

生产代码使用 Python `logging`，不使用大量无结构的 `print()`。

### 14.3 一键清除本地数据

```powershell
python main.py clear-local-data
```

会删除：

- SQLite 数据库（`data/app.db`）；
- Session 文件（`.instagram_session.json`）；
- `output/` 目录下的所有导出文件。

需交互确认，或使用 `--yes` 跳过确认。

### 14.4 .gitignore 已排除

```text
.env
*.session.json
.instagram_session.json
data/*.db
data/*.db-journal
output/*
logs/*
__pycache__/
.pytest_cache/
.ruff_cache/
.venv/
```

---

## 15. 第三方声明

本项目使用 `instagrapi`（MIT License）作为 Python 依赖，不复制、重写或修改其核心源码。所有 `instagrapi.Client` 调用通过统一适配层（`app/instagram/client.py`）封装。

完整第三方声明见 [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md)，包含：

- instagrapi（MIT License）；
- typer、pydantic、pydantic-settings、sqlalchemy、pandas、openpyxl、rich、pyyaml、python-dotenv、pytest、ruff 等依赖的许可证；
- 与 Instagram / Meta 的关系声明；
- 免责声明。

**再次强调：**

- 本项目与 Instagram、Meta Platforms, Inc. 及其关联公司无任何官方关联；
- 本项目不是 Instagram 官方工具；
- 使用者需自行遵守 Instagram 平台规则、服务条款及适用法律法规；
- 使用者需自行承担因使用本项目而产生的全部责任与风险。

---

## 16. 许可证

本项目采用 [MIT License](./LICENSE)。

```text
MIT License

Copyright (c) 2026 Mexico Instagram Creator Finder Contributors
```

---

## 17. 当前限制

- **操作系统**：仅保证在 Windows 10 / Windows 11 上正常运行；macOS/Linux 理论兼容，但未做完整验证；
- **Python 版本**：要求 3.11 或更高版本；
- **非官方 API**：依赖 `instagrapi` 提供的非官方 Private API，不保证 100% 可用；
- **接口变化**：Instagram 可能随时改变接口，导致部分功能不可用；
- **账号风险**：频繁或不当使用可能触发 Instagram 风控，使用者需自行承担风险；
- **单实例运行**：禁止高并发查询，同一时间最多执行一个 Instagram 请求；
- **数据范围**：仅处理公开数据，无法访问私密账号内容；
- **联系方式**：仅提取用户主动公开的联系方式，不推测、不抓取隐藏页面。

---

## 18. Instagram 接口兼容性风险

本项目依赖 `instagrapi` 提供的**非官方 Private API**，存在以下固有风险：

1. **接口变更**：Instagram 可能随时修改 Private API，导致 `instagrapi` 部分或全部功能失效；
2. **风控升级**：Instagram 可能升级反爬虫与账号风控机制，导致登录失败、要求验证、Session 失效等；
3. **功能受限**：某些字段（如 Reels 播放量）可能不再公开返回，此时本项目会区分"未发布 Reels / 已发布但播放量不可见 / 有可计算的播放量"三种状态，而**不会**用 0 混淆；
4. **可用性不保证**：本项目不保证在任何时间、任何账号下都能正常运行；
5. **安全停止**：一旦触发 `ChallengeRequired`、`FeedbackRequired`、`PleaseWaitFewMinutes`、`ClientThrottledError`、HTTP 429、人工验证要求或账号安全警告，本项目**立即停止**，**不自动重试、不绕过**。

**遇到接口失效或风控触发时，请停止使用并等待 `instagrapi` 上游更新，不要尝试绕过。**

---

## 最终原则

当功能便利性、搜索数量和安全性冲突时：

```text
安全性 > 数据准确性 > 可维护性 > 搜索数量 > 开发速度
```

当不确定某功能是否会构成平台规避、隐私采集或自动营销时：

```text
默认不实现。
```
