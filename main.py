# -*- coding: utf-8 -*-
"""
main.py - 主服务入口（双端口）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import threading
from flask import Flask, request, make_response

from config import (
    CORP_ID, CORP_SECRET, CONTACTS_SECRET, TOKEN, ENCODING_AES_KEY, AGENT_ID,
    AI_API_URL, AI_API_KEY, OAUTH_SIGN_KEY, OAUTH_REDIRECT_URI,
    MAIN_PORT, OAUTH_PORT, DB_CONFIG
)

from wechat_crypto import WXBizMsgCrypt
from wechat_api import WeChatAPI
from database import DatabaseManager
from user_manager import UserManager
from auth_manager import AuthManager
from ai_client import AIClient
from message_processor import MessageProcessor
from oauth_processor import OAuthProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化共享组件
db_manager = DatabaseManager(DB_CONFIG)
wechat_api = WeChatAPI(CORP_ID, CORP_SECRET, AGENT_ID, CONTACTS_SECRET)
user_manager = UserManager(wechat_api, db_manager)
auth_manager = AuthManager(OAUTH_SIGN_KEY, OAUTH_REDIRECT_URI, AGENT_ID, CORP_ID)
ai_client = AIClient(AI_API_URL, AI_API_KEY)

# ========== 主服务（8091） ==========
main_app = Flask('main_app')
wxcpt = WXBizMsgCrypt(TOKEN, ENCODING_AES_KEY, CORP_ID)
message_processor = MessageProcessor(wechat_api, ai_client, user_manager, auth_manager)


@main_app.route("/yjcallback", methods=["GET", "POST"])
def main_callback():
    """企微消息回调"""
    sig = request.args.get("msg_signature", "")
    ts = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")

    logger.info(f"[主服务] 请求: method={request.method}")

    if request.method == "GET":
        echo_str = request.args.get("echostr", "")
        if not echo_str:
            return "缺少echostr", 400

        try:
            result = wxcpt.verify_url(sig, ts, nonce, echo_str)
            logger.info("[主服务] URL验证成功")
            return make_response(result)
        except Exception as e:
            logger.error(f"[主服务] 验证失败: {e}")
            return make_response(echo_str)

    try:
        raw_data = request.data
        if not raw_data:
            return make_response("success")

        plain_xml = wxcpt.decrypt_msg(sig, ts, nonce, raw_data)
        logger.info(f"[主服务] 解密成功")

        message_processor.process(plain_xml)
        return make_response("success")

    except Exception as e:
        logger.exception("[主服务] 处理失败")
        return make_response("success")


@main_app.route("/health", methods=["GET"])
def main_health():
    return {"service": "main", "port": MAIN_PORT, "status": "running"}, 200


# ========== OAuth服务（8092） ==========
oauth_app = Flask('oauth_app')
oauth_processor = OAuthProcessor(wechat_api, auth_manager, user_manager, ai_client)


@oauth_app.route("/oauth_callback", methods=["GET"])
def oauth_callback():
    """OAuth回调"""
    code = request.args.get('code', '')
    state = request.args.get('state', '')

    logger.info(f"[OAuth] 回调: code={code[:10]}****")

    if not code:
        return auth_manager.render_error_page("缺少code参数"), 400

    return oauth_processor.handle(code, state)

# 添加新的代码了
@oauth_app.route("/health", methods=["GET"])
def oauth_health():
    return {"service": "oauth", "port": OAUTH_PORT, "status": "running"}, 200


def run_main():
    logger.info(f"主服务启动: 0.0.0.0:{MAIN_PORT}")
    main_app.run(host="0.0.0.0", port=MAIN_PORT, threaded=True)


def run_oauth():
    logger.info(f"OAuth服务启动: 0.0.0.0:{OAUTH_PORT}")
    oauth_app.run(host="0.0.0.0", port=OAUTH_PORT, threaded=True)


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 企业微信AI助手（优化版）")
    print("=" * 60)
    print(f"📍 消息服务: http://0.0.0.0:{MAIN_PORT}/yjcallback")
    print(f"📍 OAuth服务: http://0.0.0.0:{OAUTH_PORT}/oauth_callback")
    print(f"📍 对外授权: {OAUTH_REDIRECT_URI}")
    print("=" * 60)

    t1 = threading.Thread(target=run_main, daemon=True)
    t2 = threading.Thread(target=run_oauth, daemon=True)

    t1.start()
    t2.start()

    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\n服务已停止0000")