# Checklist — Mexico Instagram Creator Finder 第一阶段 MVP

> 验证范围：`d:\桌面\ins\instagrapi\mexico-instagram-creator-finder\` 子项目。
> 验证时不得修改上游 `d:\桌面\ins\instagrapi\instagrapi\` 源码。

## 项目隔离与依赖

- [ ] `mexico-instagram-creator-finder/` 子项目根目录已创建
- [ ] 项目根 `pyproject.toml` 声明 `instagrapi`、`typer`、`pydantic`、`pydantic-settings`、`sqlalchemy`、`pandas`、`openpyxl`、`rich`、`pyyaml`、`python-dotenv`、`pytest`、`ruff` 依赖
- [ ] `pip install -e .` 在子项目目录可成功执行
- [ ] 上游 `d:\桌面\ins\instagrapi\instagrapi\` 源码子目录未被修改（`git status` 验证）
- [ ] 上游 `pyproject.toml`、`README.md`、`tests/`、`examples/`、`docs/`、`mkdocs.yml`、`.pre-commit-config.yaml`、`CODE_OF_CONDUCT.md`、`CONTRIBUTING.md`、`SECURITY.md`、`LICENSE`、`.github/` 未被修改
- [ ] workspace 级 `AGENTS.md` 未被修改

## 项目根文件

- [ ] `main.py` 作为 Typer 入口
- [ ] `LICENSE`（MIT）
- [ ] `.env.example` 含 `IG_USERNAME=` / `IG_PASSWORD=`
- [ ] `.gitignore` 含 `.env`、`*.session.json`、`.instagram_session.json`、`data/*.db`、`output/`、`logs/`、`__pycache__/`、`.pytest_cache/`、`.ruff_cache/`
- [ ] `THIRD_PARTY_NOTICES.md` 声明 instagrapi MIT、与 Instagram/Meta 无官方关联、使用者需遵守平台规则
- [ ] `README.md` 全中文，含 Windows PowerShell 安装与使用说明、CLI 命令示例、`.env` 配置说明、停止原因说明

## 配置系统

- [ ] `config/default.yaml` 含 instagram/discovery/filters/analysis/checkpoint/output 全部默认参数
- [ ] `config/hashtags.yaml` 至少含 18 个墨西哥垂类默认 Hashtag
- [ ] `config/mexico_locations.yaml` 含墨西哥州/城市/地区关键词
- [ ] `config/niche_keywords.yaml` 含 perfume/beauty/skincare/makeup/fashion/lifestyle/UGC 关键词
- [ ] `config/excluded_account_terms.yaml` 含品牌/媒体/商店标志词
- [ ] `app/config.py` 实现优先级「命令行 > 环境变量 > 用户 YAML > 默认」
- [ ] 默认粉丝区间 20,000-300,000
- [ ] 默认请求间隔 4-8 秒
- [ ] 默认 `stop_on_rate_limit=true`、`stop_on_challenge=true`
- [ ] `validate-config` 命令可校验配置
- [ ] `show-config` 命令显示脱敏后的配置

## Instagram 适配层

- [ ] `app/instagram/client.py` 封装所有 `instagrapi.Client` 调用
- [ ] 业务模块不直接创建 `instagrapi.Client()`
- [ ] `login_from_env()` 从 `IG_USERNAME`/`IG_PASSWORD` 读取
- [ ] Session 文件加载/保存到配置路径
- [ ] 密码不写入日志、数据库、YAML
- [ ] `ChallengeRequired`/`FeedbackRequired`/`PleaseWaitFewMinutes`/`ClientThrottledError`/HTTP 429/人工验证/账号安全警告转换为 `SecurityStopError` 并保存断点
- [ ] 网络错误最多重试 2 次，指数退避
- [ ] 安全异常不重试
- [ ] 请求间隔 4-8 秒，无线程池/异步并发
- [ ] `app/instagram/mappers.py` 将 instagrapi 类型映射为项目 Pydantic 模型

## 发现模块

- [ ] Hashtag 搜索受 `max_hashtags`/`media_per_hashtag`/`max_candidates` 限制
- [ ] 每完成一个 Hashtag 保存断点
- [ ] username 标准化（去 `@`/URL/转小写/末尾 `/`/去重/忽略空行与 `#` 注释）
- [ ] Instagram URL 解析（`https://www.instagram.com/username/`）
- [ ] 排除名单支持 TXT/CSV/XLSX/之前导出结果
- [ ] 每个被排除账号记录 `excluded`/`exclusion_source`/`exclusion_reason`

## 分析模块

- [ ] 墨西哥识别输出 `mexico_confidence_score`/`mexico_signals`/`detected_country`/`detected_state`/`detected_city`
- [ ] 不得仅凭 `mx`/西语/国旗表情/单 Hashtag 判定墨西哥
- [ ] 垂类分类输出 `primary_niche`/`niche_scores`/`niche_signals`/`classification_reasons`
- [ ] 垂类不得仅依赖单个关键词
- [ ] 账号类型输出 `account_type`/`account_type_confidence`/`account_type_reasons`
- [ ] 不直接删除疑似账号，仅标记
- [ ] 近 12 条内容统计输出全部字段（recent_media_checked/recent_reels_checked/last_post_date/days_since_last_post/average_likes/median_likes/average_comments/median_comments/average_visible_reel_views/median_visible_reel_views/maximum_visible_reel_views/posting_frequency/reels_view_data_available）
- [ ] Reels 播放量三态区分（no_reels/not_visible/available），不用 0 混淆
- [ ] 联系方式仅提取公开邮箱/mailto:/wa.me/WhatsApp Business/Linktree/Beacons/公开网站/public_email
- [ ] 不得推测邮箱或拼接域名邮箱
- [ ] 联系方式输出 `public_email`/`public_whatsapp_url`/`external_url`/`contact_source`/`has_public_contact`
- [ ] 评分总分 100，分项权重：地区 25 + 垂类 25 + Reels 20 + 活跃度 10 + 粉丝区间 10 + 联系方式 5 + 个人创作者 5
- [ ] 评分输出 `total_score`/`score_breakdown`/`recommendation_level`(A/B/C/D)/`recommendation_reasons`
- [ ] 默认仅保存头像 URL，不下载高清头像

## 存储与断点

- [ ] SQLite 数据库 `data/app.db`（SQLAlchemy）
- [ ] 表覆盖任务/Hashtag/候选账号/资料/内容统计/评分/联系方式/来源/状态/断点
- [ ] 不保存密码/Session/私信/私密内容/推测邮箱/视频文件/原始图片
- [ ] 断点保存：已完成 Hashtag、已发现/已分析 username、失败账号、错误原因、状态、停止原因
- [ ] `--resume` 可恢复且不重复请求已分析账号
- [ ] `task-status` 显示当前任务状态
- [ ] `--reset-task` 可重置任务

## 导出

- [ ] CSV 使用 UTF-8 BOM，中文与西语重音不乱码
- [ ] JSON 使用 UTF-8（`ensure_ascii=False`）
- [ ] XLSX 字段宽度合理、长文本自动换行、URL 可点击
- [ ] 默认排序：total_score 降序 → median_visible_reel_views 降序 → followers 降序
- [ ] 不导出密码与 Session

## CLI

- [ ] 支持 `search`、`search --hashtags`、`search --min-followers`、`search --max-followers`、`search --exclude`、`search --resume`、`task-status`、`export`、`validate-config`、`show-config`、`clear-local-data`
- [ ] Rich 显示当前任务/阶段/Hashtag/候选账号数/已分析账号数/已跳过数/错误数/停止原因/输出路径
- [ ] 未设置环境变量时显示清晰提示，不输出异常堆栈
- [ ] 主流程串联完整：配置 → 登录 → 发现 → 去重 → 排除 → 资料 → 筛选 → 墨西哥识别 → 垂类 → 账号类型 → 内容指标 → 联系方式 → 评分 → 存储 → 导出

## 日志

- [ ] 使用 Python `logging`，无大量无结构 `print()`
- [ ] 不记录密码/Cookie/完整 Session/Authorization Header/私信/私人联系方式
- [ ] 可记录任务 ID/用户名/请求类型/成功失败/错误分类/停止原因/运行时间

## 测试（Mock/Fake Client，不登录真实 Instagram）

- [ ] `tests/test_username_normalization.py`
- [ ] `tests/test_exclusion_list.py`（含 Instagram URL 解析）
- [ ] `tests/test_mexico_detector.py`（含城市/州识别）
- [ ] `tests/test_niche_classifier.py`
- [ ] `tests/test_account_classifier.py`（含品牌账号识别）
- [ ] `tests/test_contact_extractor.py`（邮箱、`wa.me`、WhatsApp Business）
- [ ] `tests/test_media_metrics.py`（含无播放量状态）
- [ ] `tests/test_scoring.py`
- [ ] `tests/test_config.py`（配置优先级）
- [ ] `tests/test_storage.py`（SQLite）
- [ ] `tests/test_checkpoint.py`（断点续传）
- [ ] `tests/test_exporters.py`（CSV/JSON/XLSX）

## 静态检查与运行

- [ ] `pytest` 全部通过
- [ ] `ruff check .` 无错误
- [ ] `ruff format --check .` 无错误

## 禁止功能确认

- [ ] 未实现自动私信/批量私信/定时私信
- [ ] 未实现自动关注/批量关注/自动取消关注
- [ ] 未实现自动点赞/评论/转发/收藏
- [ ] 未实现自动查看 Story/回复评论/回复私信/发送合作邀请
- [ ] 未实现验证码识别/Challenge 绕过/短信邮箱验证绕过/设备指纹伪造
- [ ] 未实现 Cookie 窃取/Session 劫持/多账号轮换/账号池/代理池/IP 切换
- [ ] 未实现私人联系方式采集（推测邮箱/推测电话/泄露数据库/第三方数据经纪）
- [ ] 未实现 SaaS/用户注册/付费/支付/订阅/多租户/CRM/营销自动化
- [ ] 未实现高并发（线程池/异步批量）
- [ ] 未修改 instagrapi 核心源码

## 验收标准（AGENTS.md 第 31 节）

- [ ] Windows 10/11 可运行
- [ ] Python 3.11 可运行
- [ ] 依赖安装成功
- [ ] 没有环境变量时有清晰提示
- [ ] 能复用 Session
- [ ] 能搜索指定 Hashtag
- [ ] 能从公开内容提取候选作者
- [ ] 能去重
- [ ] 能读取排除名单
- [ ] 能筛选粉丝范围
- [ ] 能识别墨西哥地区信号
- [ ] 能识别目标内容垂类
- [ ] 能统计近期公开内容
- [ ] 能计算 Reels 中位播放量
- [ ] 能识别停更账号
- [ ] 能提取公开联系方式
- [ ] 能断点续传
- [ ] 能导出三种格式
- [ ] 关键业务模块有测试
- [ ] 不包含任何禁止功能
- [ ] README 提供完整 PowerShell 使用说明
