# -*- coding: utf-8 -*-
"""
message_handler.py - 消息处理器
"""

import logging
import threading
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class MessageHandler:
    """消息处理器"""

    def __init__(self, wechat_api, ai_client, mobile_manager):
        self.wechat_api = wechat_api
        self.ai_client = ai_client
        self.mobile_manager = mobile_manager

    def handle(self, plain_xml):
        """处理解密后的XML消息"""
        try:
            root = ET.fromstring(plain_xml)

            msg_type = root.findtext("MsgType", "")
            from_user = root.findtext("FromUserName", "")
            content = root.findtext("Content", "")

            logger.info(f"收到消息: 来自={from_user}, 类型={msg_type}, 内容={content}")

            if msg_type == "text" and content:
                threading.Thread(
                    target=self._process_reply,
                    args=(from_user, content)
                ).start()
                return True

            return False

        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            return False

    def _process_reply(self, from_user, content):
        """处理回复逻辑（异步）"""
        try:
            user_info = self.wechat_api.get_user_info(from_user)
            name = user_info.get("name", "未知") if user_info else "未知"
            api_mobile = user_info.get("mobile", "") if user_info else ""

            # 检查是否是绑定指令
            extracted_mobile = self.mobile_manager.extract_mobile(content)
            if extracted_mobile and len(content) < 20:
                self._handle_bind(from_user, name, extracted_mobile)
                return

            # 检查是否是授权获取手机号指令
            if "获取手机号" in content or "授权" in content:
                self._handle_auth_request(from_user)
                return

            # 获取手机号信息
            mobile, source = self.mobile_manager.get_mobile(from_user, api_mobile)

            # 打印用户信息
            info_str = self.mobile_manager.format_user_info(from_user, user_info, (mobile, source))
            print(info_str)

            # 调用AI回复
            ai_reply = self.ai_client.chat(from_user, content)
            self.wechat_api.send_app_message(from_user, ai_reply)

        except Exception as e:
            logger.error(f"处理回复失败: {e}")

    def _handle_bind(self, userid, name, mobile):
        """处理手机号绑定"""
        self.mobile_manager.bind_mobile(userid, mobile)
        self.wechat_api.send_app_message(
            userid,
            f"✅ 绑定成功！您的手机号 {mobile} 已保存。"
        )

        bind_info = self.mobile_manager.format_bind_success(name, userid, mobile)
        print(bind_info)

    def _handle_auth_request(self, userid):
        """处理授权获取手机号请求"""
        auth_url = self.mobile_manager.generate_auth_url(userid)

        if auth_url:
            message = (
                f"📱 请点击以下链接授权获取手机号：\n\n"
                f"{auth_url}\n\n"
                f"⚠️ 链接10分钟内有效，授权后您的手机号将自动同步"
            )
        else:
            message = "❌ 生成授权链接失败，请稍后重试"

        self.wechat_api.send_app_message(userid, message)