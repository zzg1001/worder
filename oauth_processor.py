# -*- coding: utf-8 -*-
"""
oauth_processor.py - OAuth回调处理器（修复版）
"""

import logging
import threading

logger = logging.getLogger(__name__)


class OAuthProcessor:
    """OAuth处理器"""

    def __init__(self, wechat_api, auth_manager, user_manager, ai_client=None):
        self.wechat_api = wechat_api
        self.auth_manager = auth_manager
        self.user_manager = user_manager
        self.ai_client = ai_client

    def handle(self, code, state):
        """处理OAuth回调 - 快速返回页面，异步处理消息"""
        try:
            # 1. 验证state
            userid = self.auth_manager.verify_state(state)
            if not userid:
                return self.auth_manager.render_error_page("授权链接已过期，请重新获取")

            # 2. 通过code获取user_ticket
            user_ticket_info = self.wechat_api.get_user_info_by_code(code)
            if not user_ticket_info or not user_ticket_info.get("user_ticket"):
                return self.auth_manager.render_error_page("获取授权信息失败")

            # 3. 获取用户详情（主要是手机号）
            detail = self.wechat_api.get_user_detail(user_ticket_info["user_ticket"])
            if not detail:
                return self.auth_manager.render_error_page("获取用户信息失败")

            # 4. 必须有手机号
            mobile = detail.get("mobile")
            if not mobile:
                return self.auth_manager.render_error_page("您的账号未绑定手机号")

            # 5. 先获取待处理消息（从内存读取，很快）
            pending_message = self.auth_manager.get_pending_message(userid)

            # 6. 异步处理：保存用户信息 + 调用AI + 发送消息
            threading.Thread(
                target=self._async_process,
                args=(userid, mobile, pending_message),
                daemon=True
            ).start()

            # 7. 立即返回成功页面（不等待任何处理）
            return self.auth_manager.render_success_page()

        except Exception as e:
            logger.error(f"OAuth处理异常: {e}")
            return self.auth_manager.render_error_page("系统错误，请重试")

    def _async_process(self, userid, mobile, pending_message):
        """异步处理：保存用户信息 + 调用AI"""
        try:
            # 1. 保存用户信息
            user_data = self.user_manager.get_and_save_user_info(userid, mobile)
            if not user_data:
                logger.error(f"保存用户信息失败: {userid}")
                self.wechat_api.send_app_message(userid, "授权成功，但保存信息失败，请重试")
                return

            # 2. 处理待处理消息或发送成功通知
            if pending_message and self.ai_client:
                self._process_pending_message(userid, pending_message)
            else:
                self._send_success_notification(userid, user_data['name'])

        except Exception as e:
            logger.error(f"异步处理失败: {e}")

    def _process_pending_message(self, userid, message):
        """异步处理待处理的消息"""
        try:
            # 获取用户上下文
            user_context = self.user_manager.get_user_context(userid)

            # 构建带用户信息的消息
            message_with_context = self.user_manager.format_user_info_for_ai(user_context, message)

            # 打印发送给AI的消息
            print("\n" + "*" * 60)
            print("*" + " " * 14 + ">>> 授权后发送给AI的消息 <<<" + " " * 14 + "*")
            print("*" * 60)
            print(message_with_context)
            print("*" * 60 + "\n")

            # 调用AI
            ai_reply = self.ai_client.chat(userid, message_with_context)

            # 打印AI返回的回复
            print("\n" + "#" * 60)
            print("#" + " " * 18 + "<<< AI返回的回复 >>>" + " " * 19 + "#")
            print("#" * 60)
            print(ai_reply)
            print("#" * 60 + "\n")

            # 发送AI回复给用户
            self.wechat_api.send_app_message(userid, ai_reply)
            logger.info(f"授权后自动处理消息成功: userid={userid}")

        except Exception as e:
            logger.error(f"授权后处理消息失败: {e}")
            self.wechat_api.send_app_message(userid, "系统繁忙，请稍后重试")

    def _send_success_notification(self, userid, name):
        """异步发送授权成功通知"""
        try:
            self.wechat_api.send_app_message(
                userid,
                f"✅ 授权成功！{name}，现在可以开始使用AI助手了。"
            )
        except Exception as e:
            logger.error(f"发送通知失败: {e}")