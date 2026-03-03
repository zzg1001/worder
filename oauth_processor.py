# -*- coding: utf-8 -*-
"""
oauth_processor.py - OAuth回调处理器（修复版）
"""

import logging

logger = logging.getLogger(__name__)


class OAuthProcessor:
    """OAuth处理器"""

    def __init__(self, wechat_api, auth_manager, user_manager, ai_client=None):
        self.wechat_api = wechat_api
        self.auth_manager = auth_manager
        self.user_manager = user_manager
        self.ai_client = ai_client

    def handle(self, code, state):
        """处理OAuth回调"""
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

        # 5. 获取完整用户信息（姓名、部门等从API获取）并保存
        user_data = self.user_manager.get_and_save_user_info(userid, mobile)

        if not user_data:
            return self.auth_manager.render_error_page("保存用户信息失败")

        # 6. 检查是否有待处理的消息
        pending_message = self.auth_manager.get_pending_message(userid)

        if pending_message and self.ai_client:
            # 有待处理消息，自动处理并返回AI回复
            try:
                # 获取用户上下文
                user_context = self.user_manager.get_user_context(userid)

                # 构建带用户信息的消息
                message_with_context = self.user_manager.format_user_info_for_ai(user_context, pending_message)

                # 打印发送给AI的消息
                print("\n" + "*" * 60)
                print("*" + " " * 18 + ">>> 发送给AI的消息 <<<" + " " * 17 + "*")
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
                self.wechat_api.send_app_message(
                    userid,
                    f"✅ 授权成功！{user_data['name']}，现在可以开始使用AI助手了。"
                )
        else:
            # 没有待处理消息，发送普通通知
            try:
                self.wechat_api.send_app_message(
                    userid,
                    f"✅ 授权成功！{user_data['name']}，现在可以开始使用AI助手了。"
                )
            except Exception as e:
                logger.error(f"发送通知失败: {e}")

        # 7. 返回成功页面（不跳转，不带自动关闭）
        # 传入用户名，页面显示"某某，验证已通过"
        return self.auth_manager.render_success_page(user_data.get('name', ''))