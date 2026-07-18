# 真实测试操作指南

> 本文档介绍如何使用真实 Instagram 账号运行本工具，发现墨西哥内容创作者。
>
> ⚠️ **重要提示**：本项目仅用于个人研究、内部测试、非商业化的软件开发学习。请严格遵守 [AGENTS.md](../AGENTS.md) 与 Instagram 平台规则。

---

## 目录

1. [前置准备](#1-前置准备)
2. [第一步：配置 Instagram 凭据](#2-第一步配置-instagram-凭据)
3. [第二步：校验配置](#3-第二步校验配置)
4. [第三步：执行小规模真实测试](#4-第三步执行小规模真实测试)
5. [第四步：查看任务状态](#5-第四步查看任务状态)
6. [第五步：导出与查看结果](#6-第五步导出与查看结果)
7. [第六步：恢复中断的任务](#7-第六步恢复中断的任务)
8. [风险与最佳实践](#8-风险与最佳实践)
9. [常见错误处理](#9-常见错误处理)
10. [合规检查清单](#10-合规检查清单)

---

## 1. 前置准备

### 1.1 环境要求

- Windows 10/11
- Python 3.11+
- 已安装项目依赖：`pip install -e ".[dev]"`
- 网络可访问 Instagram（如在中国大陆，需自备合规网络环境）

### 1.2 Instagram 账号要求

**强烈建议使用专用测试账号**，不要使用个人主账号：

- ✅ 推荐：新建的或已有的小号，**已使用一段时间**（非全新注册账号）
- ✅ 推荐：账号已通过手机号/邮箱验证
- ✅ 推荐：账号近期无频繁登录/异常活动
- ❌ 避免：全新注册当天就使用（极易触发 Challenge）
- ❌ 避免：主账号（避免风控影响日常使用）
- ❌ 避免：已被 Instagram 风控过的账号

### 1.3 心理预期

- **速度慢**：默认 4-8 秒一次请求，单实例运行，不并发（合规要求）
- **可能触发风控**：Instagram 对第三方 API 调用敏感，登录或首次请求可能触发验证
- **遇风控即停**：本项目遇 `ChallengeRequired`/`HTTP 429` 等会**立即停止不重试**
- **需手动验证**：触发风控后需在官方 App 完成验证才能恢复

---

## 2. 第一步：配置 Instagram 凭据

### 2.1 创建 .env 文件

```powershell
cd d:\桌面\ins\instagrapi\mexico-instagram-creator-finder
Copy-Item .env.example .env
notepad .env
```

### 2.2 填入账号信息

`.env` 文件内容：

```text
IG_USERNAME=你的Instagram用户名
IG_PASSWORD=你的Instagram密码
```

> **安全说明**：
> - `.env` 已在 `.gitignore` 中，不会被提交到 Git
> - 密码只从环境变量或 `.env` 读取，不写入日志/数据库/YAML
> - Session 文件（`.instagram_session.json`）也在 `.gitignore` 中

### 2.3 替代方案：使用环境变量（更安全）

如不想把密码写入文件，可在 PowerShell 会话中临时设置：

```powershell
$env:IG_USERNAME='你的用户名'
$env:IG_PASSWORD='你的密码'
```

> 注意：此方式关闭 PowerShell 后失效，需重新设置。

---

## 3. 第二步：校验配置

### 3.1 验证配置完整性

```powershell
python main.py validate-config
```

预期输出（凭据已配置）：

```text
✓ 配置校验通过
┌──────────────────── 配置概览 ────────────────────┐
│ 凭据           IG_USERNAME 已配置                 │
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

### 3.2 查看完整合并配置

```powershell
python main.py show-config
```

输出 JSON 格式，密码字段会脱敏为 `***`。

### 3.3 建议初次测试时调小参数

为降低风控风险，**第一次真实测试强烈建议缩小范围**。编辑 `config/default.yaml`：

```yaml
discovery:
  max_hashtags: 3              # 从 15 改为 3
  media_per_hashtag: 10        # 从 20 改为 10
  max_candidates: 30           # 从 300 改为 30
  max_profiles_to_analyze: 10  # 从 100 改为 10
```

或通过命令行临时覆盖（不修改配置文件）：

```powershell
# 默认参数太大，建议先用小参数测试
python main.py search --hashtags perfumemexico --hashtags fraganciasmexico
```

---

## 4. 第三步：执行小规模真实测试

### 4.1 推荐的初次测试命令

**用 1-2 个 Hashtag 跑通流程**：

```powershell
python main.py search --hashtags perfumemexico
```

或：

```powershell
python main.py search --hashtags perfumemexico --hashtags fraganciasmexico
```

### 4.2 执行过程说明

命令执行后，会依次显示：

```text
┌─────────────────────── 开始搜索 ────────────────────────┐
│ Mexico Instagram Creator Finder v0.1.0                  │
│ Hashtag 数: 1  粉丝区间: 20000-300000                   │
│ 最大候选账号: 300  最大分析账号: 100                    │
└─────────────────────────────────────────────────────────┘
阶段 1/6: 登录 Instagram...
```

**登录阶段**（约 5-15 秒）：
- 首次登录会调用 `instagrapi.Client.login()`
- 登录成功后自动保存 Session 到 `.instagram_session.json`
- 后续运行会优先复用 Session（无需重新登录）

**阶段 2-6**：
- 从 Hashtag 提取候选账号
- 去重、排除名单、获取资料、分析、评分、导出
- 每个账号之间默认等待 4-8 秒（随机）

### 4.3 完整流程耗时估算

假设参数：1 个 Hashtag × 20 媒体 × 10 个候选账号 × 分析 10 个：

| 阶段 | 请求数 | 耗时（4-8 秒/次） |
|------|--------|-------------------|
| 登录 | 1 | 5-15 秒 |
| Hashtag 媒体 | 2（recent + reels） | 10-20 秒 |
| 用户资料 | 10 | 40-80 秒 |
| 用户媒体 | 10 | 40-80 秒 |
| **合计** | ~23 次 | **约 2-4 分钟** |

> 若用默认参数（15 Hashtag × 100 账号），耗时约 **30-60 分钟**。

### 4.4 实时观察输出

Rich UI 会实时显示进度：

```text
阶段 4/6: 获取资料与分析...
  分析账号... ━━━━━━━━━━━━━━━━━━ 5/10 0:01:23
当前 Hashtag: perfumemexico
已分析: 5  已跳过: 2  错误: 0
```

如需中止，按 `Ctrl+C`，会保存当前断点。

---

## 5. 第四步：查看任务状态

### 5.1 列出最近任务

```powershell
python main.py task-status
```

输出示例：

```text
┌───────────────────── 最近任务 ─────────────────────┐
│ task_20260718_153000_abc12345  completed          │
│   开始: 2026-07-18 15:30:00                       │
│   完成: 2026-07-18 15:34:12                       │
│   Hashtag: 1/1  候选: 8  已分析: 5  跳过: 3       │
└──────────────────────────────────────────────────┘
```

### 5.2 查看指定任务详情

```powershell
python main.py task-status --task-id task_20260718_153000_abc12345
```

会显示：
- 任务状态（completed/stopped/failed）
- 已完成的 Hashtag 列表
- 已发现/已分析/失败的账号
- 停止原因（如有）

---

## 6. 第五步：导出与查看结果

### 6.1 自动导出

任务完成后会**自动导出**到 `output/` 目录，文件名格式：`creators_<task_id>.<ext>`

```powershell
Get-ChildItem output\
```

预期看到三个文件：

```text
creators_task_20260718_153000_abc12345.csv
creators_task_20260718_153000_abc12345.json
creators_task_20260718_153000_abc12345.xlsx
```

### 6.2 手动重新导出

```powershell
# 导出所有任务
python main.py export

# 导出指定任务
python main.py export --task-id task_20260718_153000_abc12345

# 仅导出 CSV 和 XLSX
python main.py export --task-id task_20260718_153000_abc12345 --formats csv xlsx
```

### 6.3 查看 JSON 结果

```powershell
# 查看完整 JSON
Get-Content output\creators_task_*.json | Out-String

# 或用 Python 美化查看
python -c "import json; data=json.load(open('output/creators_task_xxx.json', encoding='utf-8')); print(json.dumps(data[:3], ensure_ascii=False, indent=2))"
```

### 6.4 用 Excel 打开 CSV

```powershell
Start-Process excel "output\creators_task_*.csv"
```

CSV 使用 UTF-8 BOM 编码，中文和西班牙语重音字符不会乱码，Excel 直接可读。

### 6.5 关键字段解读

每个创作者记录包含 47 个字段，重点关注：

| 字段 | 含义 |
|------|------|
| `username` | Instagram 用户名 |
| `profile_url` | 主页链接 |
| `follower_count` | 粉丝数 |
| `mexico_confidence_score` | 墨西哥可信度（0-1） |
| `primary_niche` | 主要垂类（perfume/beauty/skincare/...） |
| `account_type` | 账号类型（personal_creator/brand/...） |
| `median_visible_reel_views` | Reels 中位播放量 |
| `days_since_last_post` | 距上次发布天数 |
| `public_email` | 公开商务邮箱 |
| `public_whatsapp_url` | 公开 WhatsApp 链接 |
| `total_score` | 总评分（0-100） |
| `recommendation_level` | 推荐级别（A/B/C/D） |

**推荐级别说明**：
- **A** = 重点人工检查（评分 ≥ 75）
- **B** = 值得人工检查（评分 55-74）
- **C** = 信息不足（评分 35-54）
- **D** = 不符合当前条件（评分 < 35）

---

## 7. 第六步：恢复中断的任务

### 7.1 任务被中断的常见情况

- 遇到 `ChallengeRequired`（Instagram 要求验证）
- 遇到 `HTTP 429`（限流）
- 网络异常重试 2 次后仍失败
- 用户按 `Ctrl+C` 中止

### 7.2 恢复任务

```powershell
python main.py search --resume
```

行为：
- 自动查找最近一个 `running`/`paused`/`stopped` 状态的任务
- **跳过已完成的 Hashtag**（不重复请求）
- **跳过已分析的账号**（不重复调用 API）
- 保留已发现的候选与已排除账号

### 7.3 完全重置任务

如不想恢复，从头开始：

```powershell
python main.py search --reset-task
```

### 7.4 触发 Challenge 后的恢复流程

1. **不要立即重试**（会被再次风控）
2. 打开手机 Instagram 官方 App 或网页版
3. 完成 Instagram 要求的验证（短信/邮箱/自拍等）
4. **等待 24 小时**，让风控冷却
5. 再用 `--resume` 恢复：

```powershell
python main.py search --resume
```

---

## 8. 风险与最佳实践

### 8.1 风险等级

| 行为 | 风险 | 说明 |
|------|------|------|
| 使用全新注册账号 | 🔴 极高 | 几乎必触发 Challenge |
| 使用主账号 | 🟠 高 | 风控可能影响日常使用 |
| 首次测试用大参数（15 Hashtag/100 账号） | 🟠 高 | 请求量过大易触发限流 |
| 使用专用测试账号 + 小参数 | 🟢 低 | 推荐方案 |
| 已保存 Session 后续运行 | 🟢 低 | 无需重复登录 |

### 8.2 最佳实践

✅ **应该做的**：
- 使用专用测试账号，已注册一段时间
- 第一次运行用小参数（1-2 Hashtag，10 账号以内）
- 首次登录成功后保留 `.instagram_session.json` 复用 Session
- 遇到 Challenge 立即停止，等 24 小时再恢复
- 单日运行不超过 1-2 次
- 在 Instagram App 正常使用该账号（保持活跃度）

❌ **不应该做的**：
- 不要频繁运行（每天不超过 2 次）
- 不要使用代理池或多账号轮换（违反 AGENTS.md §5.2）
- 不要尝试绕过 Challenge（违反 AGENTS.md §5.2）
- 不要把 `.env` 或 `.instagram_session.json` 提交到 Git
- 不要修改代码提高并发或缩短请求间隔

### 8.3 Session 复用

首次登录成功后，项目会自动保存 Session：

```text
.instagram_session.json   ← Session 文件（已加入 .gitignore）
```

**后续运行会自动加载 Session，无需重新登录**，大幅降低风控风险。

如 Session 失效（被 Instagram 主动注销），项目会自动尝试用密码重新登录。

如需手动删除 Session：

```powershell
Remove-Item .instagram_session.json
```

或：

```powershell
python main.py clear-local-data --yes
```

---

## 9. 常见错误处理

### 9.1 登录失败：`ChallengeRequired`

**症状**：
```text
安全停止
原因: login security stop: ChallengeRequired
已保存断点，可使用 --resume 恢复任务。
```

**处理**：
1. 打开 Instagram 官方 App
2. 完成 App 内提示的验证
3. 等 24 小时
4. 删除 Session 文件：`Remove-Item .instagram_session.json`
5. 重新运行：`python main.py search --hashtags perfumemexico`

### 9.2 限流：`HTTP 429` / `ClientThrottledError`

**症状**：
```text
安全停止
原因: hashtag_medias_recent security stop: ClientThrottledError
```

**处理**：
1. 立即停止，不要重试
2. 等待 1-2 小时让限流冷却
3. 调小参数（减少 Hashtag 数和账号数）
4. 用 `--resume` 恢复

### 9.3 网络错误：`ClientConnectionError`

**症状**：
```text
Instagram 调用失败：hashtag_medias_recent failed: connection error
```

**处理**：
- 项目会自动重试 2 次（指数退避）
- 如仍失败，检查网络是否能访问 Instagram
- 如使用 VPN/代理，确认稳定后重试

### 9.4 Session 失效

**症状**：
```text
session invalid, will re-login
```

**处理**：
- 项目会自动用密码重新登录
- 如重新登录也失败，参考 9.1

### 9.5 账号不存在

**症状**：
```text
Instagram 调用失败：user_info_by_username failed: UserNotFound
```

**处理**：
- 该账号会被记录为失败，继续处理下一个
- 不影响整体任务

### 9.6 凭据未配置

**症状**：
```text
IG_USERNAME 未设置
请在 PowerShell 中执行：
  $env:IG_USERNAME='你的用户名'
  $env:IG_PASSWORD='你的密码'
或在项目根目录创建 .env 文件...
```

**处理**：
- 检查 `.env` 文件是否存在且正确填写
- 或在 PowerShell 中设置环境变量

---

## 10. 合规检查清单

运行真实测试前，请确认：

- [ ] 已阅读并理解 [AGENTS.md](../AGENTS.md) 全部约束
- [ ] 使用专用测试账号，非个人主账号
- [ ] 账号已使用一段时间（非全新注册）
- [ ] 第一次测试使用小参数（1-2 Hashtag，10 账号以内）
- [ ] `.env` 文件已正确配置但未提交到 Git
- [ ] 不使用代理池、多账号、并发
- [ ] 不尝试绕过 Challenge 或验证码
- [ ] 遇到风控立即停止，等 24 小时再恢复
- [ ] 单日运行不超过 1-2 次
- [ ] 仅用于个人研究/内部测试/学习
- [ ] 不用于商业用途、不批量联系博主、不倒卖数据

---

## 附录：完整真实测试流程示例

```powershell
# 1. 进入项目目录
cd d:\桌面\ins\instagrapi\mexico-instagram-creator-finder

# 2. 配置凭据（首次）
Copy-Item .env.example .env
notepad .env   # 填入 IG_USERNAME 和 IG_PASSWORD

# 3. 校验配置
python main.py validate-config

# 4. 第一次小规模测试（推荐 1 个 Hashtag）
python main.py search --hashtags perfumemexico

# 5. 查看任务状态
python main.py task-status

# 6. 查看导出结果
Get-ChildItem output\
Start-Process excel "output\creators_task_*.csv"

# 7. 如被中断，恢复任务
python main.py search --resume

# 8. 测试完成后清理数据（可选）
python main.py clear-local-data --yes
```

---

**最后更新**：2026-07-18
**适用版本**：v0.1.0
**合规依据**：[AGENTS.md](../AGENTS.md) §4-§5
