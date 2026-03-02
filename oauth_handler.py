# -*- coding: utf-8 -*-
"""
oauth_handler.py - OAuth授权处理器
"""

import logging

logger = logging.getLogger(__name__)


class OAuthHandler:
    """OAuth授权处理器"""

    def __init__(self, wechat_api, mobile_manager):
        self.wechat_api = wechat_api
        self.mobile_manager = mobile_manager

    def handle_callback(self, code, state):
        """处理OAuth回调"""
        userid = self.mobile_manager.verify_state(state)
        if not userid:
            return {
                "success": False,
                "message": "授权链接已过期或无效，请重新获取",
                "html": self._render_error("授权链接已过期或无效")
            }

        user_info = self.wechat_api.get_user_info_by_code(code)
        if not user_info or not user_info.get("user_ticket"):
            return {
                "success": False,
                "message": "获取授权信息失败",
                "html": self._render_error("获取授权信息失败，请重新授权")
            }

        detail = self.wechat_api.get_user_detail(user_info["user_ticket"])
        if not detail:
            return {
                "success": False,
                "message": "获取手机号失败",
                "html": self._render_error("获取手机号详情失败")
            }

        if detail.get("mobile"):
            self.mobile_manager.bind_mobile(detail["userid"], detail["mobile"])

            self.wechat_api.send_app_message(
                detail["userid"],
                f"✅ 授权成功！手机号 {detail['mobile']} 已自动绑定。"
            )

            return {
                "success": True,
                "data": detail,
                "html": self._render_success(detail)
            }
        else:
            return {
                "success": False,
                "message": "该用户未绑定手机号",
                "html": self._render_error("该账号未绑定手机号，请联系管理员")
            }

    def _render_success(self, data):
        """渲染成功页面"""
        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>授权成功</title>
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    text-align: center; 
                    margin-top: 80px; 
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    color: white;
                }}
                .container {{
                    background: rgba(255,255,255,0.95);
                    padding: 40px;
                    border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    max-width: 400px;
                    margin: 0 auto;
                    color: #333;
                }}
                .success-icon {{ font-size: 64px; margin-bottom: 20px; }}
                h1 {{ color: #10b981; margin-bottom: 10px; }}
                .info {{ 
                    background: #f3f4f6; 
                    padding: 20px; 
                    border-radius: 8px; 
                    margin: 20px 0;
                    text-align: left;
                }}
                .info-item {{ margin: 10px 0; color: #4b5563; }}
                .info-label {{ font-weight: bold; color: #1f2937; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✅</div>
                <h1>授权成功！</h1>
                <p>您的手机号已成功绑定到系统</p>

                <div class="info">
                    <div class="info-item">
                        <span class="info-label">用户ID：</span>{data.get('userid', '')}
                    </div>
                    <div class="info-item">
                        <span class="info-label">姓名：</span>{data.get('name', '')}
                    </div>
                    <div class="info-item">
                        <span class="info-label">手机号：</span>{data.get('mobile', '')}
                    </div>
                    <div class="info-item">
                        <span class="info-label">邮箱：</span>{data.get('email') or '未设置'}
                    </div>
                </div>

                <p style="color: #6b7280; font-size: 14px;">您可以关闭此页面返回企业微信</p>
            </div>
        </body>
        </html>
        """

    def _render_error(self, message):
        """渲染错误页面"""
        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>授权失败</title>
            <style>
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    text-align: center; 
                    margin-top: 80px; 
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    min-height: 100vh;
                    color: white;
                }}
                .container {{
                    background: rgba(255,255,255,0.95);
                    padding: 40px;
                    border-radius: 16px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    max-width: 400px;
                    margin: 0 auto;
                    color: #333;
                }}
                .error-icon {{ font-size: 64px; margin-bottom: 20px; }}
                h1 {{ color: #ef4444; margin-bottom: 10px; }}
                .message {{ color: #6b7280; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error-icon">❌</div>
                <h1>授权失败</h1>
                <div class="message">{message}</div>
                <p style="color: #6b7280; font-size: 14px;">请返回企业微信重新获取授权链接</p>
            </div>
        </body>
        </html>
        """