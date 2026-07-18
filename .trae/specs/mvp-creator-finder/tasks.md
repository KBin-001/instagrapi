# Tasks — Mexico Instagram Creator Finder 第一阶段 MVP

> 工作目录约定：所有路径均相对 `d:\桌面\ins\instagrapi\mexico-instagram-creator-finder\`。
> 上游 instagrapi 源码（`d:\桌面\ins\instagrapi\instagrapi\` 等）不得修改。

- [x] Task 1: 初始化独立子项目骨架
  - [x] SubTask 1.1: 创建 `mexico-instagram-creator-finder/` 目录及 `app/`、`config/`、`data/`、`tests/`、`output/` 子目录与 `.gitkeep`
  - [x] SubTask 1.2: 编写项目根 `pyproject.toml`，声明依赖（instagrapi、typer、pydantic、pydantic-settings、sqlalchemy、pandas、openpyxl、rich、pyyaml、python-dotenv、pytest、ruff）与 `[tool.ruff]` 配置
  - [x] SubTask 1.3: 编写项目根 `.gitignore`（含 `.env`、`*.session.json`、`.instagram_session.json`、`data/*.db`、`output/`、`logs/`、`__pycache__/`、`.pytest_cache/`、`.ruff_cache/`）
  - [x] SubTask 1.4: 编写 `.env.example`（`IG_USERNAME=` / `IG_PASSWORD=`）
  - [x] SubTask 1.5: 编写 `LICENSE`（MIT）与 `THIRD_PARTY_NOTICES.md`（声明 instagrapi MIT、与 Meta 无关联）
  - [x] SubTask 1.6: 编写项目根 `main.py`（仅作为 Typer 入口，调用 `app.cli.app`）

- [x] Task 2: 数据模型与异常体系
  - [x] SubTask 2.1: `app/exceptions.py` 定义 `SecurityStopError`、`ConfigError`、`InstagramClientError`、`CheckpointError`
  - [x] SubTask 2.2: `app/models.py` 定义 Pydantic 数据模型：`CandidateAccount`、`ProfileData`、`MediaMetrics`、`ContactInfo`、`NicheClassification`、`MexicoSignal`、`AccountTypeClassification`、`ScoreResult`、`TaskCheckpoint`

- [x] Task 3: 配置系统（YAML + .env + CLI 优先级）
  - [x] SubTask 3.1: `config/default.yaml` 写入用户给定默认参数（instagram/discovery/filters/analysis/checkpoint/output）
  - [x] SubTask 3.2: `config/hashtags.yaml` 写入 18 个墨西哥垂类默认 Hashtag
  - [x] SubTask 3.3: `config/mexico_locations.yaml` 写入墨西哥州/城市/地区关键词（CDMX、Jalisco、Monterrey、Guadalajara 等）
  - [x] SubTask 3.4: `config/niche_keywords.yaml` 写入 perfume/beauty/skincare/makeup/fashion/lifestyle/UGC 关键词（西/英双语）
  - [x] SubTask 3.5: `config/excluded_account_terms.yaml` 写入品牌/媒体/商店常见标志词（shop、store、oficial、tienda 等）
  - [x] SubTask 3.6: `app/config.py` 实现 `Settings`（pydantic-settings），从 `IG_USERNAME`/`IG_PASSWORD` 读环境变量；实现 YAML 加载与「命令行 > 环境变量 > 用户 YAML > 默认」合并逻辑；提供 `validate()` 与脱敏 `to_display_dict()`

- [x] Task 4: Instagram 统一适配层
  - [x] SubTask 4.1: `app/instagram/rate_limit.py` 实现随机延迟（4-8 秒）与指数退避重试（最多 2 次网络错误）
  - [x] SubTask 4.2: `app/instagram/session.py` 实现 Session 文件加载/保存，路径来自配置；不得将 Session 内容写入日志
  - [x] SubTask 4.3: `app/instagram/mappers.py` 将 `instagrapi.types.User`/`Media`/`Hashtag` 映射为项目内部 Pydantic 模型，提取公开字段
  - [x] SubTask 4.4: `app/instagram/client.py` 封装 `InstagramClient`，提供 `login_from_env()`、`hashtag_medias()`、`user_info_by_username()`、`user_medias()`；将 `ChallengeRequired`/`FeedbackRequired`/`PleaseWaitFewMinutes`/`ClientThrottledError`/HTTP 429/账号安全警告转换为 `SecurityStopError`；网络错误有限重试；不使用线程池或异步并发

- [x] Task 5: 发现模块
  - [x] SubTask 5.1: `app/discovery/hashtag.py` 调用适配层获取 Hashtag 帖子/Reels，提取作者 username，受 `max_hashtags`/`media_per_hashtag`/`max_candidates` 限制
  - [x] SubTask 5.2: `app/discovery/deduplication.py` 实现 username 标准化（去 `@`、去 URL、转小写、去末尾 `/`、去重、忽略空行与 `#` 注释）与 Instagram URL 解析
  - [x] SubTask 5.3: `app/discovery/seeds.py` 实现排除名单解析（TXT/CSV/XLSX/之前导出结果），每个被排除账号记录 `excluded`/`exclusion_source`/`exclusion_reason`
  - [x] SubTask 5.4: `app/discovery/location.py` 预留地点发现入口（MVP 阶段可仅返回空列表，保持模块完整）

- [x] Task 6: 分析模块
  - [x] SubTask 6.1: `app/analysis/mexico_detector.py` 多信号识别墨西哥地区（Biography/城市/州/Hashtag/Caption/`.mx`/公开电话国家代码辅助），输出 `mexico_confidence_score`/`mexico_signals`/`detected_country`/`detected_state`/`detected_city`；不得仅凭 `mx`/西语/国旗表情/单 Hashtag 判定
  - [x] SubTask 6.2: `app/analysis/niche_classifier.py` 多信号垂类分类（Biography/Full name/Category/Hashtag/Caption），输出 `primary_niche`/`niche_scores`/`niche_signals`/`classification_reasons`
  - [x] SubTask 6.3: `app/analysis/account_classifier.py` 区分 personal_creator/ugc_creator/brand/shop/media/news/agency/marketing/fan_reposter/topic_aggregator，输出 `account_type`/`account_type_confidence`/`account_type_reasons`
  - [x] SubTask 6.4: `app/analysis/media_metrics.py` 分析近 12 条公开内容，计算 `average_likes`/`median_likes`/`average_comments`/`median_comments`/`average_visible_reel_views`/`median_visible_reel_views`/`maximum_visible_reel_views`/`posting_frequency`/`days_since_last_post`/`reels_view_data_available`（三态：no_reels/not_visible/available，不得用 0 混淆）
  - [x] SubTask 6.5: `app/analysis/contact_extractor.py` 提取公开邮箱/`mailto:`/`wa.me`/WhatsApp Business/Linktree/Beacons/公开网站/`public_email`，输出 `public_email`/`public_whatsapp_url`/`external_url`/`contact_source`/`has_public_contact`；不得推测邮箱或拼接域名邮箱
  - [x] SubTask 6.6: `app/analysis/scoring.py` 100 分透明评分（地区 25 + 垂类 25 + Reels 20 + 活跃度 10 + 粉丝区间 10 + 联系方式 5 + 个人创作者 5），输出 `total_score`/`score_breakdown`/`recommendation_level`(A/B/C/D)/`recommendation_reasons`

- [x] Task 7: 存储模块
  - [x] SubTask 7.1: `app/storage/database.py` 使用 SQLAlchemy + SQLite 初始化 `data/app.db`，建表：tasks/hashtags/candidates/profiles/media_stats/scores/contacts/sources/statuses/checkpoints
  - [x] SubTask 7.2: `app/storage/repositories.py` 实现各表 CRUD（任务、候选、资料、统计、评分、联系方式、断点）；不得保存密码/Session/私信/推测邮箱
  - [x] SubTask 7.3: `app/storage/checkpoint.py` 实现断点保存与恢复：已完成 Hashtag、已发现/已分析 username、失败账号、错误原因、当前状态、停止原因

- [x] Task 8: 导出模块
  - [x] SubTask 8.1: `app/export/csv_exporter.py` 使用 UTF-8 BOM，默认排序（total_score 降序 → median_visible_reel_views 降序 → followers 降序）
  - [x] SubTask 8.2: `app/export/json_exporter.py` 输出 UTF-8 JSON（`ensure_ascii=False`、`indent=2`）
  - [x] SubTask 8.3: `app/export/excel_exporter.py` 使用 openpyxl，字段宽度合理、长文本自动换行、URL 可点击

- [x] Task 9: Typer CLI 与 Rich 进度
  - [x] SubTask 9.1: `app/cli.py` 实现 `search`/`task-status`/`export`/`validate-config`/`show-config`/`clear-local-data` 命令
  - [x] SubTask 9.2: `search` 支持 `--hashtags`/`--min-followers`/`--max-followers`/`--exclude`/`--resume`/`--reset-task`
  - [x] SubTask 9.3: 使用 Rich 显示当前任务/阶段/Hashtag/候选账号数/已分析账号数/已跳过数/错误数/停止原因/输出路径
  - [x] SubTask 9.4: 未设置 `IG_USERNAME`/`IG_PASSWORD` 时显示清晰提示，不输出异常堆栈
  - [x] SubTask 9.5: 串联主流程：配置 → 登录 → 发现 → 去重 → 排除 → 资料 → 筛选 → 墨西哥识别 → 垂类 → 账号类型 → 内容指标 → 联系方式 → 评分 → 存储 → 导出；遇 `SecurityStopError` 保存断点并停止

- [x] Task 10: 日志脱敏
  - [x] SubTask 10.1: `app/__init__.py` 或 `app/logging_config.py` 配置 Python `logging`，提供脱敏过滤器（屏蔽密码/Cookie/Session/Authorization Header/私信/私人联系方式）
  - [x] SubTask 10.2: 全项目移除无结构 `print()`，替换为 `logging`

- [x] Task 11: 单元测试（全部使用 Mock/Fake Client）
  - [x] SubTask 11.1: `tests/test_username_normalization.py` 覆盖去 `@`/URL/转小写/末尾 `/`/空行/`#` 注释
  - [x] SubTask 11.2: `tests/test_exclusion_list.py` 覆盖 TXT/CSV/Instagram URL 解析
  - [x] SubTask 11.3: `tests/test_mexico_detector.py` 覆盖 Biography/城市/州/Hashtag/`.mx` 多信号
  - [x] SubTask 11.4: `tests/test_niche_classifier.py` 覆盖各垂类关键词与多信号
  - [x] SubTask 11.5: `tests/test_account_classifier.py` 覆盖品牌/媒体/个人创作者识别
  - [x] SubTask 11.6: `tests/test_contact_extractor.py` 覆盖邮箱、`wa.me`、WhatsApp Business、Linktree、Beacons 提取
  - [x] SubTask 11.7: `tests/test_media_metrics.py` 覆盖平均/中位/最大播放量与三态（no_reels/not_visible/available）
  - [x] SubTask 11.8: `tests/test_scoring.py` 覆盖 100 分评分与 A/B/C/D 推荐级别
  - [x] SubTask 11.9: `tests/test_config.py` 覆盖「命令行 > 环境变量 > 用户 YAML > 默认」优先级
  - [x] SubTask 11.10: `tests/test_storage.py` 覆盖 SQLite 持久化
  - [x] SubTask 11.11: `tests/test_checkpoint.py` 覆盖断点保存与恢复
  - [x] SubTask 11.12: `tests/test_exporters.py` 覆盖 CSV（UTF-8 BOM）/JSON/XLSX 导出

- [x] Task 12: 中文 README 与第三方声明收尾
  - [x] SubTask 12.1: 编写 `README.md` 全中文：项目简介、合规声明、Windows PowerShell 安装与使用说明、`.env` 配置说明、CLI 命令示例、输出格式说明、常见问题、停止原因说明
  - [x] SubTask 12.2: 复核 `THIRD_PARTY_NOTICES.md`（声明 instagrapi MIT、与 Meta 无关联、使用者需遵守平台规则）

- [x] Task 13: 静态检查与测试运行
  - [x] SubTask 13.1: 在 `mexico-instagram-creator-finder/` 执行 `pytest`，全部通过（246 passed）
  - [x] SubTask 13.2: 执行 `ruff check .`，无错误（All checks passed）
  - [x] SubTask 13.3: 执行 `ruff format --check .`，无错误（46 files already formatted）
  - [x] SubTask 13.4: 修复本次修改引入的任何 lint/格式/测试失败（修复 4 个测试失败 + 5 个手动 lint 错误 + 104 个自动 lint 修复 + 14 个文件格式化）

- [x] Task 14: 最终验证
  - [x] SubTask 14.1: `git status` 在 `d:\桌面\ins\instagrapi\` 确认上游 instagrapi 源码未被修改（working tree clean）
  - [x] SubTask 14.2: 验证未实现任何禁止功能（自动私信/关注/点赞/评论/多账号/代理池/验证绕过/私人联系方式采集/SaaS 化）—— grep 确认无 follow/like/comment/direct_send/captcha/proxy_pool/email_guess 等调用
  - [x] SubTask 14.3: 汇报：修改文件、实现功能、测试结果、运行方法、当前限制、Instagram 接口兼容性风险

# Task Dependencies

- Task 1（项目骨架）是所有后续任务的前置。
- Task 2（数据模型/异常）与 Task 3（配置系统）可在 Task 1 后并行。
- Task 4（Instagram 适配层）依赖 Task 2 + Task 3。
- Task 5（发现）、Task 6（分析）、Task 7（存储）依赖 Task 4；三者之间相互独立，可并行。
- Task 8（导出）依赖 Task 7。
- Task 9（CLI）依赖 Task 5 + Task 6 + Task 7 + Task 8。
- Task 10（日志脱敏）可在 Task 4 后进行，与 Task 5-8 并行。
- Task 11（测试）依赖 Task 2-8 全部完成。
- Task 12（README）依赖 Task 9。
- Task 13（静态检查）依赖 Task 11。
- Task 14（最终验证）依赖 Task 13。
