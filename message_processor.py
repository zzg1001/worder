# -*- coding: utf-8 -*-
"""
message_processor.py - 消息处理器
"""

import logging
import threading
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class MessageProcessor:
    """消息处理器"""

    def __init__(self, wechat_api, ai_client, user_manager, auth_manager):
        self.wechat_api = wechat_api
        self.ai_client = ai_client
        self.user_manager = user_manager
        self.auth_manager = auth_manager

    def process(self, plain_xml):
        """处理消息入口"""
        try:
            root = ET.fromstring(plain_xml)

            msg_type = root.findtext("MsgType", "")
            from_user = root.findtext("FromUserName", "")
            content = root.findtext("Content", "")

            logger.info(f"收到消息: 用户={from_user}, 内容={content}")

            if msg_type == "text" and content:
                threading.Thread(
                    target=self._handle_message,
                    args=(from_user, content)
                ).start()
                return True

            return False

        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            return False

    def _handle_message(self, userid, content):
        """处理单条消息"""
        try:
            # 1. 检查用户是否已授权（数据库中有手机号）
            is_authorized, user_info = self.user_manager.check_user_authorized(userid)

            if not is_authorized:
                # 首次使用，保存消息并发送授权卡片
                self._send_auth_card(userid, content)
                return

            # 2. 获取用户上下文
            user_context = self.user_manager.get_user_context(userid)

            # 3. 打印用户信息（每次消息都显示）
            info_display = self.user_manager.format_user_info_for_display(user_context)
            print(info_display)

            # 4. 构建带用户信息的消息给AI
            message_with_context = self.user_manager.format_user_info_for_ai(user_context, content)

            # 5. 打印发送给AI的消息
            print("\n" + "*" * 60)
            print("*" + " " * 18 + ">>> 发送给AI的消息 <<<" + " " * 17 + "*")
            print("*" * 60)
            print(message_with_context)
            print("*" * 60 + "\n")

            # 6. 调用AI
            ai_reply = self.ai_client.chat(userid, message_with_context)

            # 7. 打印AI返回的回复
            print("\n" + "#" * 60)
            print("#" + " " * 18 + "<<< AI返回的回复 >>>" + " " * 19 + "#")
            print("#" * 60)
            print(ai_reply)
            print("#" * 60 + "\n")

            # 8. 发送回复
            self.wechat_api.send_app_message(userid, ai_reply)

        except Exception as e:
            logger.error(f"处理消息异常: {e}")
            self.wechat_api.send_app_message(userid, "系统繁忙，请稍后重试")

    def _send_auth_card(self, userid, original_message=None):
        """发送授权卡片，并保存用户原始消息"""
        auth_url = self.auth_manager.generate_auth_url(userid)

        if auth_url:
            # 保存用户原始消息，授权成功后自动处理
            if original_message:
                self.auth_manager.save_pending_message(userid, original_message)
            # 使用简洁的markdown链接格式
            message = self.auth_manager.render_auth_card_message(auth_url)
        else:
            message = "系统错误，请稍后重试"

        self.wechat_api.send_app_message(userid, message)