# -*- coding: utf-8 -*-
"""
config.py - 配置文件
"""

import os

# ========== 企业微信配置 ==========
CORP_ID = "ww916ee9aaff82d432"
CORP_SECRET = "5lljSaa2TBcYqAMxvC7HZ6gIQHVMbeiMF657sbS9sWY"
TOKEN = "G18rPJGiiuWo8WQf68wWggeJbHY"
ENCODING_AES_KEY = "HTNGvKDbsDXkoOc7amRY8Xr2LU3MabI6wf6q8NPgmlL"
AGENT_ID = "1000012"

# ========== AI接口配置 ==========
AI_API_URL = "http://47.100.100.139:8028/v1/chat-messages"
AI_API_KEY = "app-9PcBKF15xLSzND8z25XwVkGe"

# ========== 服务端口配置 ==========
# 主服务端口（企微消息推送，直接暴露）
MAIN_PORT = 8091
# OAuth回调服务端口（Nginx 443转发到此处）
OAUTH_PORT = 8092

# ========== OAuth授权配置 ==========
# 注意：这是Nginx 443域名的地址，用于生成授权链接
OAUTH_REDIRECT_URI = "https://yjservicetest.ike-data.com/oauth_callback"
OAUTH_SIGN_KEY = os.getenv("WX_SIGN_KEY", "wx_callback_2024")

# ========== 日志配置 ==========
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"