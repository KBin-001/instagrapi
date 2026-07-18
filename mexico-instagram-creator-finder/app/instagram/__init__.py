"""Instagram 适配层子包。

负责封装 instagrapi.Client 的登录、Session 加载/保存、请求间隔、
异常转换与日志脱敏等能力。业务模块不得直接创建 Client()。
"""
