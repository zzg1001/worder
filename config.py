# -*- coding: utf-8 -*-
"""
config.py - 配置文件
"""

import os

# ========== 企业微信配置 ==========
CORP_ID = "ww916ee9aaff82d432"
CORP_SECRET = "5lljSaa2TBcYqAMxvC7HZ6gIQHVMbeiMF657sbS9sWY"
CONTACTS_SECRET = "CEoy_E-Y18TaUrQlk2bcgiWcOADjWSkPkibJdXi1LVM"  # 通讯录Secret
TOKEN = "G18rPJGiiuWo8WQf68wWggeJbHY"
ENCODING_AES_KEY = "HTNGvKDbsDXkoOc7amRY8Xr2LU3MabI6wf6q8NPgmlL"
AGENT_ID = "1000012"

# ========== AI接口配置 ==========
AI_API_URL = "http://47.100.100.139:8028/v1/chat-messages"
AI_API_KEY = "app-wYllm3x9JhK4qjL9yU95DnJ8"

# ========== 图片AI接口配置（workflow） ==========
IMAGE_AI_API_URL = "http://47.100.100.139:8028/v1/workflows/run"
IMAGE_AI_API_KEY = "app-KPd1NBWxgrF1Yorx3wqk2lNm"

# ========== 工单提交AI接口配置（workflow） ==========
WORK_ORDER_API_URL = "http://47.100.100.139:8028/v1/workflows/run"
WORK_ORDER_API_KEY = "app-gk5gUlA1vdPSwDM0DuRz7O4E"

# ========== 服务端口配置 ==========
MAIN_PORT = 8091
OAUTH_PORT = 8092

# ========== OAuth授权配置 ==========
OAUTH_REDIRECT_URI = "https://yjservicetest.ike-data.com/oauth_callback"
OAUTH_SIGN_KEY = os.getenv("WX_SIGN_KEY", "wx_callback_2024")

# ========== MySQL数据库配置 ==========
DB_CONFIG = {
    'host': '8.153.198.194',
    'port': 63306,
    'user': 'wx_qa',
    'password': 'cKXF45BLSHW68ynk',
    'database': 'wx_qa',
    'charset': 'utf8mb4'
}

# ========== 日志配置 ==========
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"