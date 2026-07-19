# AGENTS.md

## 1. 文档作用

本文件是本项目所有 AI 编程智能体、自动化开发工具和人工开发者必须遵守的最高级项目约束。

在执行任何代码修改之前，必须完整阅读本文件。

如果用户的临时要求与本文件冲突：

1. 停止执行冲突部分；
2. 明确指出冲突；
3. 优先遵守本文件中的安全、范围和架构限制；
4. 不得自行扩大项目能力。

不得删除、绕过、弱化或自动修改本文件中的约束。

---

# 2. 项目名称

**Mexico Instagram Creator Finder**

中文名称：

**墨西哥 Instagram 内容创作者发现工具**

---

# 3. 项目定位

本项目是参考 WaveInflu / Wavely 等达人发现产品的公开产品流程，在本地实现的 Instagram 创作者搜索、发现、分析与清单整理工具。

项目允许同时使用 Chrome 浏览器扩展、Instagram 公开网页可见数据、本地分析服务和 `instagrapi` 只读适配层。浏览器扩展是正式支持的数据采集入口，不再被视为实验性功能或阶段外功能。

`instagrapi` 应作为可选 Python 依赖使用，不再作为唯一数据入口。

除非是为了提交上游兼容性修复，否则不得直接复制、重写或修改 `instagrapi` 的核心源码。

本项目的用途是：

* 搜索公开的 Instagram 内容；
* 从公开帖子、Reels、Hashtag 和地点中发现内容创作者；
* 根据自然语言投放 Brief、内容方向或参考博主发现同类型创作者；
* 通过 Chrome 扩展读取当前公开页面、相似账号推荐和公开列表中的候选账号；
* 在用户启动任务后，按受控队列跳转公开主页并批量补全候选资料；
* 对批量候选进行标准化、跨任务去重、状态检测和匹配度排序；
* 筛选墨西哥本地或面向墨西哥市场的创作者；
* 分析公开主页及公开内容数据；
* 识别适合香水、美妆、护肤、穿搭和生活方式内容的创作者；
* 导出研究结果供人工判断。

## 3.1 竞品参考原则

允许参考 WaveInflu / Wavely 等竞品公开展示的以下产品流程：

* 自然语言描述目标达人；
* 从当前达人主页发现相似达人；
* 批量输入主页链接；
* 自动整理公开主页、粉丝量、近期表现、地区、垂类和公开联系方式；
* 自动去重、排序、收藏、形成清单并导出；
* 将“达人发现”“达人状态分析”“公开联系方式映射”拆分为独立能力或 Agent Skills。

参考竞品仅限于产品目标、交互流程、字段组织和公开功能。不得复制其闭源代码、接口密钥、数据库、品牌素材、受版权保护的页面文案或无法合法获得的专有算法。

本项目仅用于：

* 个人研究；
* 内部测试；
* 非商业化的软件开发学习；
* 人工筛选公开内容创作者。

本项目不是：

* Instagram 营销群发工具；
* 自动私信工具；
* 涨粉工具；
* 养号工具；
* 账号控制工具；
* 数据倒卖平台；
* 联系方式采集平台；
* 绕过 Instagram 限制的工具。

---

# 4. 核心开发原则

所有开发必须遵守以下原则：

1. **只处理公开数据。**
2. **只执行低频、只读的数据查询。**
3. **不自动联系任何账号。**
4. **不实现账号互动自动化。**
5. **不绕过 Instagram 的安全机制。**
6. **不收集或推测私人联系方式。**
7. **不使用多个账号规避限制。**
8. **不使用代理池规避风控。**
9. **不以高并发提高采集速度。**
10. **不将项目改造成商业化 SaaS。**
11. **优先保证账号安全和数据准确性，而不是搜索数量。**
12. **遇到平台限制时停止，而不是尝试绕过。**
13. **允许浏览器扩展读取用户当前已登录页面中公开可见的数据。**
14. **允许用户主动启动批量搜索、顺序页面跳转、候选补全和全局去重。**
15. **批量任务必须有数量、时间、层级、间隔和停止条件，不得无限运行。**
16. **浏览器采集、`instagrapi` 适配和人工导入必须统一转换为同一领域模型。**

---

# 5. 明确禁止的功能

以下功能不得实现，包括直接实现、隐藏实现、实验性实现或通过配置开启。

## 5.1 禁止账号互动自动化

不得实现：

* 自动私信；
* 批量私信；
* 定时私信；
* 自动关注；
* 批量关注；
* 自动取消关注；
* 自动点赞；
* 自动评论；
* 自动转发；
* 自动收藏；
* 自动查看 Story；
* 自动回复评论；
* 自动回复私信；
* 自动发送合作邀请；
* 根据搜索结果自动联系博主。

即使 `instagrapi` 提供对应接口，本项目也不得调用。

---

## 5.2 禁止规避平台风控

不得实现：

* 验证码自动识别；
* Challenge 自动绕过；
* 短信验证绕过；
* 邮箱验证绕过；
* 设备指纹伪造；
* 自动生成设备信息；
* 频繁更换设备标识；
* Cookie 窃取或导入；
* Session 劫持；
* 多账号轮换；
* 账号池；
* 代理池；
* IP 自动切换；
  -住宅代理集成；
* 数据中心代理集成；
* 通过代理绕过速率限制；
* 自动修改请求头模拟多个设备；
* 绕过登录限制；
* 绕过 Instagram 权限限制；
* 未授权访问私密账号；
* 抓取已删除或隐藏内容。

出现以下异常时必须停止相关任务：

* `ChallengeRequired`
* `FeedbackRequired`
* `PleaseWaitFewMinutes`
* `ClientThrottledError`
* HTTP 429
* 登录异常
* Instagram 要求人工验证
* 账号安全警告
* Session 被判定失效

不得在这些异常之后无限重试。

---

## 5.3 禁止采集私人数据

不得：

* 猜测电子邮箱；
* 根据用户名生成可能的邮箱；
* 推测私人手机号码；
* 提取非公开电话号码；
* 从泄露数据库查找联系方式；
* 从第三方数据经纪平台补充私人资料；
* 抓取私密账号内容；
* 保存登录账号的私信；
* 分析私人对话；
* 收集未公开的用户身份信息；
* 使用人脸识别判断用户身份；
* 推测种族、宗教、健康、政治倾向或其他敏感属性。

可以记录的联系方式仅限于：

* 用户在 Instagram biography 中主动公开的商务邮箱；
* Instagram 公开返回的 business email；
* 用户公开展示的 `wa.me` 链接；
* 用户公开展示的 WhatsApp Business 链接；
* 用户主动公开的 Linktree、Beacons 或个人网站；
* 用户主动公开标注的合作入口。

所有公开联系方式必须记录来源。

---

# 6. 允许开发的功能

本项目允许实现以下能力。

## 6.1 创作者发现

允许从以下公开入口发现候选账号：

* Hashtag 的近期帖子；
* Hashtag 的公开 Reels；
* Instagram 公开搜索结果；
* 用户用自然语言输入的达人 Brief 或内容方向；
* 用户输入的种子账号；
* 种子账号公开内容中提及的账号；
* 公开地点页面；
* 用户手动导入的用户名；
* 用户手动导入的 CSV；
* 用户批量粘贴的 Instagram 主页链接；
* 用户公开主页的相似账号推荐；
* Instagram 页面公开可见的推荐账号、关注列表或粉丝列表；
* 浏览器扩展在当前公开页面中识别出的创作者主页链接。

账号扩展只能有限进行。

默认扩展一层。允许通过配置增加受控扩展层级，但不得无限递归；每一层都必须执行去重、排除名单和数量上限检查。

允许一次批量导入或处理最多 100 条主页链接作为默认值；该值必须可配置。单个公开列表或种子账号可以发现更多候选，但必须受 `max_accounts_per_seed` 和 `max_candidates` 双重限制。现有实现中的候选上限可以保留，但不得绕过任务总上限。

每次任务必须有：

* 最大 Hashtag 数量；
* 每个 Hashtag 最大内容数；
* 最大候选账号数；
* 最大账号分析数；
* 最大种子账号扩展数；
* 最大运行时长。
* 最大批量主页链接数；
* 最大页面跳转数；
* 最大扩展层级；

## 6.1.1 相似达人发现

相似达人发现是本项目核心功能，允许组合以下信号：

* 自然语言 Brief；
* 种子账号的 biography、category、公开内容 Caption 和 Hashtag；
* 内容垂类、内容形式和公开视觉主题标签；
* 墨西哥地区信号和语言信号；
* 粉丝规模区间；
* 点赞、评论、Reels 可见播放量和发布频率；
* 账号类型；
* Instagram 公开展示的相似账号推荐关系。

相似度结果必须输出匹配分和可解释原因。不得仅因为共同出现一个关键词、一个 Hashtag 或一个推荐链接就判定为高度相似。

## 6.1.2 批量搜索、跳转与去重

允许浏览器扩展或本地任务在用户明确点击“开始搜索”后：

1. 建立候选队列；
2. 在 Instagram 公开页面之间顺序跳转；
3. 读取页面当前公开可见的主页与内容摘要；
4. 保存断点；
5. 对 username、Instagram URL 和稳定 user id 执行去重；
6. 跳过已分析、已排除、私密或不符合条件的账号；
7. 在达到数量、时间、限流或安全停止条件时结束。

页面跳转和批量补全属于只读研究流程，不属于自动关注、自动私信或账号互动。

---

## 6.2 公开主页分析

允许读取并保存以下公开字段：

* username；
* full_name；
* biography；
* profile_url；
* public profile picture URL；
* follower_count；
* following_count；
* media_count；
* is_private；
* is_verified；
* is_business；
* category_name；
* business_category；
* external_url；
* 公开 business email；
* 公开 business contact；
* 来源 Hashtag；
* 发现时间。

不得下载或长期保存高清头像，除非用户明确要求并且仅用于本地界面缓存。

默认只保存头像 URL。

---

## 6.3 公开内容分析

允许分析近期公开内容中的：

* 发布时间；
* 内容类型；
* Caption；
* Hashtag；
* 点赞数；
* 评论数；
* 可见播放量；
* 是否为 Reel；
* 是否包含香水、美妆、护肤、穿搭或生活方式关键词；
* 最近更新时间；
* 发布频率。

不得：

* 下载全部媒体文件；
* 建立永久媒体镜像；
* 大规模保存视频；
* 下载私密内容；
* 对人物外貌进行评分；
* 根据身体特征评价创作者。

默认只保存分析结果和公开媒体 URL，不保存原始媒体文件。

---

# 7. 目标搜索对象

项目主要用于发现符合以下方向的墨西哥内容创作者：

* 香水；
* 固体香水；
* 香氛；
* 美妆；
* 护肤；
* 穿搭；
* 女性生活方式；
* UGC 内容制作；
* 礼物推荐；
* 日常好物分享；
* 墨西哥本地消费内容。

目标粉丝区间默认为：

```text
20,000—300,000
```

但该范围必须可以在配置文件或界面中修改。

不得将粉丝数作为唯一筛选依据。

需要结合：

* 墨西哥地区可信度；
* 垂类匹配度；
* 近期内容活跃度；
* Reels 播放表现；
* 内容发布频率；
* 公开联系方式；
* 是否为个人创作者；
* 是否为品牌、媒体或机构账号。

---

# 8. 非商业化约束

本项目当前为非商业化内部工具。

不得主动增加以下功能：

* 用户注册；
* 付费会员；
* 订阅套餐；
* 支付系统；
* 微信支付；
* Stripe；
* PayPal；
* 余额系统；
* 积分系统；
* 多租户系统；
* 商业授权系统；
* API 收费；
* SaaS 部署；
* 营销落地页；
* 客户管理；
* 销售漏斗；
* 自动营销；
* 商业广告投放；
* 批量客户导入；
* 批量营销触达。

除非用户以后明确改变项目方向，否则不得为“未来商业化”提前增加复杂架构。

---

# 9. 技术架构约束

## 9.1 基础技术

建议使用：

* Python 3.11 或更高版本；
* `instagrapi`；
* Typer；
* Pydantic；
* Pydantic Settings；
* SQLite；
* SQLAlchemy；
* pandas；
* openpyxl；
* Rich；
* PyYAML；
* python-dotenv；
* pytest；
* Ruff。
* Chrome Extension Manifest V3；
* NiceGUI；

可选本地界面：

* Streamlit。

项目应同时维护三个入口：

* CLI：任务管理、配置、恢复和导出；
* NiceGUI：本地搜索、进度、结果和设置界面；
* Chrome 扩展：当前主页采集、相似候选发现、批量链接导入和受控页面跳转。

CLI 应可以独立完成本地数据管理和导出，但真实发现流程可以由浏览器扩展启动或提供数据，不再要求所有采集能力都必须由 CLI 独立完成。

不得为了简单的个人工具引入：

* Kubernetes；
* Kafka；
* RabbitMQ；
* Celery 集群；
* Elasticsearch；
* Redis 集群；
* 微服务架构；
* 云原生多租户架构。

除非有明确、现实的技术必要，否则使用单体模块化架构。

---

## 9.2 数据采集适配架构

项目允许以下采集通道并存：

1. Chrome 扩展读取 Instagram 公开网页当前可见数据；
2. `instagrapi` 只读适配层；
3. 用户手动输入、TXT、CSV、XLSX 和主页 URL；
4. Fake Client 和固定测试数据。

所有通道必须实现统一适配接口，并转换为统一的 `CandidateAccount`、`ProfileData`、公开内容摘要和联系方式模型。业务分析模块不得依赖具体 DOM 选择器或具体 Instagram Client 返回类型。

浏览器扩展可以作为默认采集入口。`instagrapi` 登录和 Session 复用只在启用该通道时需要，不得为了保留 `instagrapi` 而删除或禁用已经实现的浏览器扩展能力。

## 9.3 `instagrapi` 使用方式

启用 `instagrapi` 通道时，必须通过依赖管理器安装 `instagrapi`：

```text
pip install instagrapi
```

或在 `pyproject.toml` 中声明依赖。

禁止将整个 `instagrapi` 仓库源码复制进本项目。

所有 `instagrapi.Client` 调用必须封装在统一适配层，例如：

```text
app/instagram/client.py
app/instagram/gateway.py
```

业务模块不得直接到处创建 `Client()`。

在启用 `instagrapi` 通道时，统一适配层必须负责：

* 登录；
* Session 加载；
* Session 保存；
* 请求间隔；
* 异常转换；
* 安全停止；
* 日志脱敏；
* API 返回值转换。

这样做是为了避免业务逻辑与非官方接口紧密耦合。

## 9.4 Chrome 浏览器扩展

Chrome 扩展是正式产品组成部分，允许实现：

* 读取当前 Instagram 公开主页；
* 显示主页关键数据和本地分析结果；
* 在公开帖子或 Reels 封面附近显示本地计算的互动率、可见播放量或分析标记；
* 高亮主页主动公开的邮箱、WhatsApp、官网和合作入口，并标记是否已经进入本地名单；
* 收集当前页面公开展示的推荐账号；
* 批量导入和识别 Instagram 主页 URL；
* 建立受控候选队列；
* 顺序跳转候选主页并采集公开信息；
* 将候选、主页、内容摘要和公开联系方式发送到本地服务；
* 显示进度、重复、跳过、失败和停止原因；
* 保存、收藏和导出候选清单。

扩展不得读取 Cookie、localStorage 中的认证凭据、完整 Session、私信或非公开内容。扩展与本地服务之间必须使用本地令牌或等效鉴权，并只允许访问明确声明的本地地址和 Instagram 页面。

---

# 10. 推荐目录结构

```text
mexico-instagram-creator-finder/
├─ AGENTS.md
├─ README.md
├─ LICENSE
├─ pyproject.toml
├─ .env.example
├─ .gitignore
├─ main.py
│
├─ app/
│  ├─ __init__.py
│  ├─ cli.py
│  ├─ config.py
│  ├─ models.py
│  ├─ exceptions.py
│  │
│  ├─ instagram/
│  │  ├─ __init__.py
│  │  ├─ client.py
│  │  ├─ session.py
│  │  ├─ rate_limit.py
│  │  └─ mappers.py
│  │
│  ├─ discovery/
│  │  ├─ __init__.py
│  │  ├─ hashtag.py
│  │  ├─ location.py
│  │  ├─ seeds.py
│  │  └─ deduplication.py
│  │
│  ├─ analysis/
│  │  ├─ __init__.py
│  │  ├─ mexico_detector.py
│  │  ├─ niche_classifier.py
│  │  ├─ media_metrics.py
│  │  ├─ account_classifier.py
│  │  ├─ contact_extractor.py
│  │  └─ scoring.py
│  │
│  ├─ storage/
│  │  ├─ __init__.py
│  │  ├─ database.py
│  │  ├─ repositories.py
│  │  └─ checkpoint.py
│  │
│  ├─ export/
│  │  ├─ __init__.py
│  │  ├─ csv_exporter.py
│  │  ├─ json_exporter.py
│  │  └─ excel_exporter.py
│  │
│  └─ ui/
│     └─ streamlit_app.py
│
├─ config/
│  ├─ default.yaml
│  ├─ hashtags.yaml
│  ├─ mexico_locations.yaml
│  ├─ niche_keywords.yaml
│  └─ excluded_account_terms.yaml
│
├─ data/
│  ├─ .gitkeep
│  ├─ excluded.example.txt
│  └─ seeds.example.txt
│
└─ tests/
   ├─ test_config.py
   ├─ test_username_normalization.py
   ├─ test_mexico_detector.py
   ├─ test_niche_classifier.py
   ├─ test_contact_extractor.py
   ├─ test_media_metrics.py
   ├─ test_scoring.py
   ├─ test_checkpoint.py
   └─ test_exporters.py
```

目录可以根据实际代码调整，但必须保持职责分离。

---

# 11. 配置要求

所有可调参数必须进入配置系统。

不得将以下参数硬编码在业务函数中：

* 粉丝数范围；
* Hashtag 列表；
* 地区关键词；
* 垂类关键词；
* 请求间隔；
* 最大候选数；
* 最大分析账号数；
* 近期内容数量；
* 停更天数；
* 最低播放量；
* 评分权重；
* 导出目录；
* `instagrapi` 通道的 Session 文件路径；
* 默认数据采集通道；
* 浏览器扩展本地接口地址；
* 批量主页链接上限；
* 页面跳转间隔；
* 最大页面跳转数；
* 全局去重窗口；
* 是否允许刷新已分析账号。

配置优先级：

```text
命令行参数
> 环境变量
> 用户 YAML 配置
> 默认配置
```

默认配置必须保守。

示例：

```yaml
instagram:
  session_file: ".instagram_session.json"
  request_delay_min_seconds: 4
  request_delay_max_seconds: 8
  retry_network_errors: 2
  stop_on_rate_limit: true
  stop_on_challenge: true

acquisition:
  default_channel: "browser_extension"
  browser_extension_enabled: true
  local_api_url: "http://127.0.0.1:8080"
  max_batch_profile_links: 100
  max_page_navigations: 300
  page_delay_min_seconds: 4
  page_delay_max_seconds: 8
  global_deduplication_enabled: true
  global_deduplication_window: 1000
  refresh_analyzed_profiles: false

discovery:
  max_hashtags: 15
  media_per_hashtag: 20
  max_candidates: 300
  max_profiles_to_analyze: 100
  seed_expansion_depth: 1
  max_accounts_per_seed: 100

filters:
  min_followers: 20000
  max_followers: 300000
  require_public_account: true
  require_mexico_signal: true
  maximum_days_since_last_post: 90
  minimum_recent_media_count: 3
  minimum_median_reel_views: 2000
  exclude_brands: true
  exclude_media_accounts: true

analysis:
  recent_media_amount: 12
  maximum_caption_length: 3000

checkpoint:
  enabled: true
  database_file: "data/app.db"

output:
  directory: "output"
  formats:
    - csv
    - json
    - xlsx
```

---

# 12. 登录与凭据安全

浏览器扩展通道使用用户已经在 Chrome 中打开的 Instagram 页面，不要求项目读取 Instagram 用户名、密码、Cookie 或 Session。没有配置 `IG_USERNAME` 和 `IG_PASSWORD` 时，浏览器扩展、本地导入、结果分析和导出仍应可以工作。

Instagram 用户名和密码只能从以下位置读取：

* 环境变量；
* 本地 `.env` 文件。

变量名称：

```text
IG_USERNAME
IG_PASSWORD
```

不得：

* 将密码写入源码；
* 将密码写入 YAML；
* 将密码写入日志；
* 将密码写入数据库；
* 将完整 Cookie 写入日志；
* 将 Session 内容上传到 GitHub；
* 在异常信息中输出密码；
* 在界面中回显密码。

`.gitignore` 必须包含：

```text
.env
*.session.json
.instagram_session.json
data/*.db
output/
logs/
__pycache__/
.pytest_cache/
.ruff_cache/
```

应提供 `.env.example`：

```text
IG_USERNAME=
IG_PASSWORD=
```

浏览器扩展与本地服务之间的令牌必须只保存在本机，不得提交到 Git、写入日志或发送到任何第三方服务。令牌只用于保护本地接口，不得作为 Instagram 登录凭据使用。

---

# 13. 请求频率与重试规则

本项目禁止高并发查询 Instagram。

默认要求：

* 单实例运行；
* 同一时间最多执行一个 Instagram 请求；
* 请求之间随机等待；
* 默认等待不少于 4 秒；
* 不使用线程池并发 Instagram 请求；
* 不使用异步批量并发 Instagram 请求；
* 网络异常最多重试两次；
* 每次重试使用指数退避；
* 验证、限流或账号安全异常不得自动重试。

浏览器扩展批量任务额外要求：

* 必须由用户主动启动；
* 页面跳转必须顺序执行，不得同时打开大量 Instagram 页面并发采集；
* 每次跳转或数据补全之间必须应用可配置间隔；
* 进入队列前先按 username、URL 和 user id 去重；
* 已在全局历史中完成分析的账号默认不重复跳转，除非用户选择刷新；
* 每完成一个账号立即保存结果和断点；
* 页面无法加载、账号私密、字段缺失或 DOM 不兼容时记录原因并继续下一账号；
* 遇到 429、Challenge、安全警告或人工验证时立即停止整个批量任务；
* 不得通过无头多实例、隐藏窗口、多个账号或代理池扩大吞吐量。

只允许重试：

* 临时 DNS 错误；
* 连接超时；
* 临时服务器错误；
* 可明确判断为短暂网络异常的问题。

不得重试：

* 429；
* Challenge；
* FeedbackRequired；
* PleaseWaitFewMinutes；
* 登录验证；
* Session 安全警告；
* 权限拒绝。

当任务停止时，应保存断点。

---

# 14. 数据存储规则

默认使用 SQLite。

数据库可以保存：

* 搜索任务；
* Hashtag；
* 候选账号；
* 账号公开资料；
* 公开内容统计；
* 评分结果；
* 公开联系方式；
* 发现来源；
* 分析状态；
* 错误状态；
* 断点信息；
* 收集时间。

不得保存：

* Instagram 密码；
* 完整 Session；
* 私信内容；
* 私密账号内容；
* 未公开电话号码；
* 推测出的邮箱；
* 下载的视频文件；
* 大量原始图片；
* 敏感属性推断结果。

应支持删除本地数据。

---

# 15. 墨西哥地区识别规则

地区识别必须基于多个公开信号。

可以使用：

* Biography 中的国家名称；
* Biography 中的城市或州；
* 公开 business address；
* 来源 Hashtag；
* 近期公开 Caption；
* 公开地点标签；
* `.mx` 网站；
* 墨西哥电话号码国家代码，但只能在用户已公开展示时作为辅助信号。

不得仅因为出现以下内容就直接判定为墨西哥：

* `mx` 两个字母；
* 西班牙语；
* 墨西哥国旗表情；
* 某一个 Hashtag。

输出至少包含：

```text
mexico_confidence_score
mexico_signals
detected_country
detected_state
detected_city
```

每个信号必须可解释。

---

# 16. 垂类分类规则

支持以下分类：

* perfume；
* beauty；
* skincare；
* makeup；
* fashion；
* lifestyle；
* UGC；
* general；
* brand；
* media；
* agency。

分类依据：

* Biography；
* Full name；
* Category；
* 来源 Hashtag；
* 近期 Caption；
* 近期内容 Hashtag。

不得仅依赖单个关键词。

分类结果必须输出：

```text
primary_niche
niche_scores
niche_signals
classification_reasons
```

---

# 17. 账号类型识别

需要区分：

* 个人创作者；
* UGC 创作者；
* 品牌；
* 商店；
* 媒体；
* 新闻账号；
* 经纪公司；
* 营销机构；
* 粉丝搬运账号；
* 主题聚合账号。

不得直接删除疑似账号。

应记录：

```text
account_type
account_type_confidence
account_type_reasons
```

筛选时可以默认隐藏品牌和媒体账号，但用户可以查看被排除原因。

---

# 18. 近期内容指标

每个账号默认分析最近 12 条公开内容。

至少计算：

* recent_media_checked；
* recent_reels_checked；
* last_post_date；
* days_since_last_post；
* average_likes；
* median_likes；
* average_comments；
* median_comments；
* average_visible_reel_views；
* median_visible_reel_views；
* maximum_visible_reel_views；
* posting_frequency；
* reels_view_data_available。

必须区分：

1. 没有发布 Reels；
2. 发布了 Reels，但播放量不可见；
3. 有可计算的播放量。

不得用 0 混淆以上三种情况。

中位数优先用于筛选，平均值仅作为补充指标。

---

# 19. 公开联系方式提取规则

联系方式提取必须独立封装并有测试。

允许提取：

* 正确格式的公开邮箱；
* `mailto:` 链接；
* `wa.me` 链接；
* WhatsApp Business 公开链接；
* Linktree；
* Beacons；
* 公开网站；
* Instagram 公开 business email。

必须输出：

```text
public_email
public_whatsapp_url
external_url
contact_source
has_public_contact
```

不得：

* 根据姓名推测邮箱；
* 根据域名拼接邮箱；
* 将普通数字识别为 WhatsApp；
* 抓取网站隐藏页面中的个人资料；
* 自动访问登录后才能看到的联系方式；
* 访问第三方泄露数据库。

---

# 20. 评分系统

评分必须透明、可配置、可测试。

默认总分为 100 分：

```text
墨西哥地区可信度：25
香水、美妆及生活方式匹配度：25
近期 Reels 表现：20
内容活跃度：10
粉丝区间匹配度：10
公开商务联系方式：5
个人创作者可信度：5
```

必须输出：

```text
total_score
score_breakdown
recommendation_level
recommendation_reasons
```

推荐级别：

```text
A：重点人工检查
B：值得人工检查
C：信息不足
D：不符合当前条件
```

不得将评分描述为对个人价值、外貌或可信人格的判断。

评分只是与当前搜索条件的匹配程度。

---

# 21. 排除名单

支持：

* TXT；
* CSV；
* XLSX；
* 之前导出的结果；
* 命令行用户名；
* Instagram URL。

标准化规则：

* 去除 `@`；
* 去除 URL；
* 转小写；
* 去除末尾 `/`；
* 去重；
* 忽略空行；
* 忽略 `#` 开头的注释。

每个被排除账号应记录：

```text
excluded
exclusion_source
exclusion_reason
```

---

# 22. 断点续传

断点续传是必须功能。

每完成一个关键步骤后保存：

* 已完成 Hashtag；
* 已发现用户名；
* 已分析用户名；
* 失败账号；
* 错误原因；
* 当前任务状态；
* 停止原因。

程序异常退出或用户手动停止后，应可以恢复。

需要支持：

```text
--resume
--reset-task
```

恢复任务时不得重复大量请求已经分析过的账号。

---

# 23. 导出要求

支持：

* CSV；
* JSON；
* XLSX。

必须保证：

* 中文不乱码；
* 西班牙语重音字符不乱码；
* CSV 使用 UTF-8 BOM；
* Excel 字段宽度合理；
* 长文本自动换行；
* URL 可点击；
* 不导出密码和 Session。

默认排序：

1. total_score 降序；
2. median_visible_reel_views 降序；
3. followers 降序。

---

# 24. CLI 要求

使用 Typer。

至少支持：

```text
python main.py search
python main.py search --hashtags perfumemexico fraganciasmexico
python main.py search --min-followers 20000
python main.py search --max-followers 150000
python main.py search --exclude data/excluded.txt
python main.py search --resume
python main.py task-status
python main.py export
python main.py validate-config
python main.py show-config
python main.py clear-local-data
```

CLI 必须显示：

* 当前任务；
* 当前阶段；
* 当前 Hashtag；
* 候选账号数；
* 已分析账号数；
* 已跳过数；
* 错误数；
* 停止原因；
* 输出路径。

只有在用户明确选择 `instagrapi` 通道但没有设置账号环境变量时，才应显示清晰凭据提示。浏览器扩展通道不得因为缺少 `IG_USERNAME` 或 `IG_PASSWORD` 而阻止任务启动。

---

# 25. 本地界面要求

允许继续开发和维护已经实现的 NiceGUI 本地界面与 Chrome 浏览器扩展，不要求删除、回退或等待 CLI 完全稳定。

界面只作为本地工具。

不得开发公网注册和多用户系统。

页面允许包含：

* 搜索参数；
* Hashtag 输入；
* 自然语言达人 Brief；
* 种子账号和参考主页输入；
* 批量主页链接粘贴或导入；
* 粉丝范围；
* 最低播放量；
* 最大候选数；
* 排除名单上传；
* 开始搜索；
* 停止搜索；
* 候选队列与当前跳转账号；
* 相似达人推荐；
* 重复、跳过和失败原因；
* 任务状态；
* 结果表格；
* 条件筛选；
* 导出按钮；
* 本地数据删除。

Chrome 扩展侧边栏允许包含：

* 当前主页数据；
* 当前主页状态分析；
* 发现相似达人；
* 收集公开推荐账号；
* 批量链接导入；
* 开始、暂停和停止批量补全；
* 保存到本地清单；
* 打开本地结果页。

界面不得：

* 显示密码；
* 显示完整 Session；
* 提供自动私信按钮；
* 提供自动关注按钮；
* 提供批量互动按钮。

---

# 26. 日志要求

日志必须脱敏。

不得记录：

* 密码；
* Cookie；
* 完整 Session；
* Authorization Header；
* 私信内容；
* 私人联系方式。

日志可以记录：

* 任务 ID；
* 用户名；
* 请求类型；
* 成功或失败；
* 错误分类；
* 停止原因；
* 运行时间。

生产代码中不得使用大量无结构的 `print()`。

优先使用 Python `logging` 或 `structlog`。

---

# 27. 测试要求

所有纯业务逻辑必须可以脱离 Instagram 实际接口测试。

必须测试：

* 用户名标准化；
* Instagram URL 解析；
* 排除名单解析；
* 墨西哥地区识别；
* 城市和州识别；
* 垂类分类；
* 品牌账号判断；
* 邮箱提取；
* WhatsApp 链接提取；
* Reels 平均数和中位数；
* 无播放数据状态；
* 评分系统；
* 配置优先级；
* SQLite 存储；
* 断点续传；
* CSV 导出；
* JSON 导出；
* XLSX 导出。
* 自然语言 Brief 到结构化筛选条件的转换；
* 批量主页 URL 解析、标准化和去重；
* 全局历史去重和刷新覆盖规则；
* 候选队列顺序、数量上限和页面跳转上限；
* 浏览器扩展本地令牌校验；
* 浏览器扩展 payload 到统一领域模型的转换；
* 批量任务暂停、停止、恢复和安全停止。

测试中不得登录真实 Instagram 账号。

必须使用：

* Mock；
* Fake Client；
* 固定测试数据。

提交代码前执行：

```text
pytest
ruff check .
```

如果项目配置了格式化，再执行：

```text
ruff format --check .
```

---

# 28. 开发流程

AI 每次执行开发任务时必须遵守以下流程：

1. 阅读 `AGENTS.md`；
2. 阅读 `README.md`；
3. 检查 Git 状态；
4. 查看现有项目结构；
5. 阅读相关实现；
6. 说明本次修改范围；
7. 识别是否触碰禁止功能；
8. 只修改完成当前任务所需的文件；
9. 添加或更新测试；
10. 运行测试；
11. 运行静态检查；
12. 总结修改结果。

不得在没有阅读现有代码的情况下重写整个项目。

不得为了“代码更现代”无理由重构无关模块。

不得修改与当前任务无关的文件。

不得删除已有功能，除非用户明确要求或功能违反本文件约束。

---

# 29. AI 输出要求

每次开发完成后，AI 必须报告：

1. 修改了哪些文件；
2. 为什么修改；
3. 新增了什么功能；
4. 是否涉及数据库变更；
5. 是否涉及配置变更；
6. 测试执行结果；
7. 静态检查结果；
8. 当前已知限制；
9. 是否存在 Instagram 接口兼容性风险；
10. 下一步建议。

不得声称未运行的测试已经通过。

不得隐藏错误。

不得将推测描述为已验证事实。

---

# 30. 当前阶段 MVP 范围

当前阶段允许完成以下功能：

1. 浏览器扩展本地连接，以及可选 `instagrapi` 通道的登录和 Session 复用；
2. Hashtag 搜索；
3. 提取公开内容作者；
4. 用户名去重；
5. 排除名单；
6. 获取公开账号资料；
7. 粉丝范围筛选；
8. 墨西哥地区信号识别；
9. 香水、美妆、护肤、穿搭、生活方式和 UGC 分类；
10. 分析近期公开内容；
11. 计算 Reels 可见播放量中位数；
12. 判断账号活跃度；
13. 提取公开邮箱和公开 WhatsApp 链接；
14. 透明评分；
15. SQLite 断点续传；
16. CSV、JSON、XLSX 导出；
17. CLI；
18. 单元测试；
19. 中文 README；
20. Chrome Manifest V3 浏览器扩展；
21. 当前 Instagram 主页公开数据采集；
22. 自然语言达人 Brief；
23. 从当前主页发现相似账号和公开推荐账号；
24. 批量粘贴或导入 Instagram 主页链接；
25. 用户启动后的受控顺序页面跳转；
26. 批量候选补全、跨来源去重和历史去重；
27. 浏览器扩展与本地 NiceGUI 服务通信；
28. 候选收藏、结果排序和清单管理；
29. 将达人发现、状态分析、公开联系方式映射拆分为独立服务或 Agent Skills。

当前阶段仍不得开发：

* 自动私信；
* 自动关注；
* 自动点赞；
* 自动评论；
* SaaS；
* 用户系统；
* 支付系统；
* 多账号；
* 代理池；
* AI 自动生成营销话术；
* CRM；
* 合作进度管理；
* 自动邮件发送。

---

# 31. 当前阶段验收标准

MVP 完成必须满足：

* Windows 10/11 可运行；
* Python 3.11 可运行；
* 依赖安装成功；
* 浏览器扩展通道在没有 Instagram 环境变量时仍可运行；
* 启用 `instagrapi` 通道时，没有环境变量会给出清晰提示并能复用 Session；
* 能搜索指定 Hashtag；
* 能从公开内容提取候选作者；
* 能去重；
* 能读取排除名单；
* 能筛选粉丝范围；
* 能识别墨西哥地区信号；
* 能识别目标内容垂类；
* 能统计近期公开内容；
* 能计算 Reels 中位播放量；
* 能识别停更账号；
* 能提取公开联系方式；
* 能断点续传；
* 能导出三种格式；
* 关键业务模块有测试；
* 不包含任何禁止功能；
* README 提供完整 PowerShell 使用说明；
* Chrome 扩展可在用户已登录的 Instagram 页面读取当前公开主页；
* 扩展不读取 Cookie、Session、私信或私密内容；
* 可以输入自然语言 Brief 并生成结构化搜索条件；
* 可以从种子主页、公开推荐、Hashtag、地点和批量链接发现候选；
* 可以对候选执行受控顺序跳转和资料补全；
* 可以在跳转前去重，并跳过已完成或已排除账号；
* 可以保存批量任务断点并在停止后恢复；
* 相似达人结果包含匹配分、匹配原因和发现来源；
* 公开联系方式包含来源，不存在时明确显示为缺失；
* 批量任务达到数量、时间或安全停止条件时能够正常结束。

---

# 32. 许可证要求

本项目使用 `instagrapi` 作为依赖时，必须保留其许可证信息和第三方声明。

项目需要增加：

```text
THIRD_PARTY_NOTICES.md
```

其中说明：

* 使用了 `instagrapi`；
* `instagrapi` 采用 MIT License；
* 本项目与 Instagram、Meta 无官方关联；
* 本项目不是 Instagram 官方工具；
* 使用者需要自行遵守平台规则。

不得移除或伪造第三方版权声明。

---

# 33. 最终原则

当功能便利性、搜索数量和安全性冲突时：

```text
安全性 > 数据准确性 > 可维护性 > 搜索数量 > 开发速度
```

当不确定某功能是否会构成平台规避、隐私采集或自动营销时：

```text
默认不实现。
```
