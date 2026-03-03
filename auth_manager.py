# -*- coding: utf-8 -*-
"""
auth_manager.py - 授权管理模块（修复版）
"""

import re
import hashlib
import random
import time
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)


class AuthManager:
    """授权管理器"""

    def __init__(self, sign_key, redirect_uri, agent_id, corp_id):
        self.sign_key = sign_key
        self.redirect_uri = redirect_uri
        self.agent_id = agent_id
        self.corp_id = corp_id
        self._auth_states = {}
        self._pending_messages = {}  # 保存待处理的消息 {userid: message}

    def generate_auth_url(self, userid):
        """生成OAuth授权链接"""
        if not re.match(r'^[a-zA-Z0-9_]+$', userid):
            logger.error(f"用户ID格式错误: {userid}")
            return None

        nonce = str(random.randint(100000, 999999))
        timestamp = str(int(time.time()))
        sign_str = f"{userid}_{nonce}_{timestamp}_{self.sign_key}"
        sign = hashlib.md5(sign_str.encode()).hexdigest()
        state = f"{userid}_{nonce}_{timestamp}_{sign}"

        self._auth_states[userid] = {
            "nonce": nonce,
            "timestamp": timestamp,
            "sign": sign,
            "expire_time": time.time() + 600
        }

        redirect_uri_encoded = quote(self.redirect_uri, safe='')
        auth_url = (
            f"https://open.weixin.qq.com/connect/oauth2/authorize"
            f"?appid={self.corp_id}"
            f"&redirect_uri={redirect_uri_encoded}"
            f"&response_type=code"
            f"&scope=snsapi_privateinfo"
            f"&agentid={self.agent_id}"
            f"&state={state}"
            f"#wechat_redirect"
        )

        return auth_url

    def verify_state(self, state):
        """验证state"""
        try:
            parts = state.split('_')
            if len(parts) != 4:
                return None

            userid, nonce, timestamp, sign = parts

            if userid not in self._auth_states:
                return None

            stored = self._auth_states[userid]

            expected_sign = hashlib.md5(
                f"{userid}_{nonce}_{timestamp}_{self.sign_key}".encode()
            ).hexdigest()

            if sign != expected_sign:
                return None

            if time.time() > stored["expire_time"]:
                del self._auth_states[userid]
                return None

            del self._auth_states[userid]
            return userid

        except Exception as e:
            logger.error(f"验证state失败: {e}")
            return None

    def save_pending_message(self, userid, message):
        """保存用户待处理的消息"""
        self._pending_messages[userid] = {
            'message': message,
            'time': time.time()
        }
        logger.info(f"保存待处理消息: userid={userid}, message={message}")

    def get_pending_message(self, userid):
        """获取并清除用户待处理的消息"""
        if userid in self._pending_messages:
            pending = self._pending_messages[userid]
            # 检查消息是否过期（10分钟）
            if time.time() - pending['time'] < 600:
                del self._pending_messages[userid]
                return pending['message']
            else:
                del self._pending_messages[userid]
        return None

    def render_auth_card_message(self, auth_url):
        """
        渲染授权消息 - 专业简洁风格
        企微中显示为可点击链接
        """
        return (
            f"【身份验证】\n\n"
            f"为保障信息安全，首次使用需验证身份。\n\n"
            f"<a href='{auth_url}'>点击完成验证 ></a>\n\n"
            f"有效期10分钟，如失效请重新发送消息获取。"
        )

    def render_auth_page(self, auth_url):
        """
        渲染极简授权页面
        用户点击后会跳转到企微的授权确认页（选择手机号）
        """
        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>身份验证</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    background: #f5f5f5;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                }}
                .container {{
                    background: white;
                    padding: 40px 30px;
                    border-radius: 12px;
                    box-shadow: 0 2px 20px rgba(0,0,0,0.1);
                    text-align: center;
                    max-width: 320px;
                    width: 90%;
                }}
                .icon {{ font-size: 48px; margin-bottom: 16px; }}
                h1 {{ font-size: 20px; color: #333; margin-bottom: 8px; font-weight: 500; }}
                .desc {{ color: #666; font-size: 14px; margin-bottom: 30px; line-height: 1.5; }}
                .btn {{
                    display: block;
                    width: 100%;
                    padding: 14px;
                    background: #07c160;
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    font-size: 16px;
                    font-weight: 500;
                }}
                .btn:active {{ background: #06ad56; }}
                .tip {{
                    margin-top: 20px;
                    color: #999;
                    font-size: 12px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="icon">🔐</div>
                <h1>身份验证</h1>
                <p class="desc">需要验证您的手机号以继续使用AI助手</p>
                <a href="{auth_url}" class="btn">同意并验证手机号</a>
                <p class="tip">点击后将选择手机号进行验证</p>
            </div>
        </body>
        </html>
        """

    def render_success_page(self, name=None):
        """
        渲染授权成功页面
        不自动跳转，不调用任何微信接口，让用户手动关闭
        """
        display_name = f"{name}，" if name else ""
        display_msg = f"{display_name}验证已通过" if name else "验证已通过"
        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>授权成功</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    background: #f5f5f5;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                }}
                .container {{
                    background: white;
                    padding: 50px 30px;
                    border-radius: 12px;
                    box-shadow: 0 2px 20px rgba(0,0,0,0.1);
                    text-align: center;
                    max-width: 320px;
                    width: 90%;
                }}
                .success-icon {{ 
                    width: 70px; 
                    height: 70px; 
                    background: #07c160; 
                    border-radius: 50%; 
                    display: flex; 
                    align-items: center; 
                    justify-content: center; 
                    margin: 0 auto 25px;
                    color: white;
                    font-size: 36px;
                    font-weight: bold;
                }}
                h1 {{ font-size: 22px; color: #333; margin-bottom: 12px; font-weight: 500; }}
                .desc {{ color: #666; font-size: 15px; margin-bottom: 30px; line-height: 1.6; }}
                .close-tip {{
                    background: #f0f0f0;
                    color: #666;
                    padding: 12px;
                    border-radius: 6px;
                    font-size: 13px;
                }}
                .close-btn {{
                    display: inline-block;
                    margin-top: 20px;
                    padding: 10px 30px;
                    background: #07c160;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 15px;
                    cursor: pointer;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✓</div>
                <h1>授权成功</h1>
                <p class="desc">{display_msg}<br>现在可以返回企业微信使用AI助手</p>
                <div class="close-tip">
                    👆 点击右上角关闭按钮<br>或点击下方按钮返回
                </div>
                <button class="close-btn" onclick="closeWindow()">关闭页面</button>
            </div>
            <script>
                // 尝试关闭页面（可能因浏览器限制无效）
                function closeWindow() {{
                    window.close();
                    // 如果无法关闭，提示用户手动关闭
                    setTimeout(function() {{
                        alert('请手动点击右上角关闭按钮返回企业微信');
                    }}, 100);
                }}

                // 禁止任何跳转
                // 移除所有可能触发跳转的代码
                console.log('授权成功，等待用户手动关闭');
            </script>
        </body>
        </html>
        """

    def render_error_page(self, message):
        """渲染错误页面"""
        return f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>授权失败</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
                    background: #f5f5f5;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                }}
                .container {{
                    background: white;
                    padding: 50px 30px;
                    border-radius: 12px;
                    box-shadow: 0 2px 20px rgba(0,0,0,0.1);
                    text-align: center;
                    max-width: 320px;
                    width: 90%;
                }}
                .error-icon {{ 
                    width: 70px; 
                    height: 70px; 
                    background: #fa5151; 
                    border-radius: 50%; 
                    display: flex; 
                    align-items: center; 
                    justify-content: center; 
                    margin: 0 auto 25px;
                    color: white;
                    font-size: 36px;
                    font-weight: bold;
                }}
                h1 {{ font-size: 22px; color: #333; margin-bottom: 12px; font-weight: 500; }}
                .desc {{ color: #666; font-size: 15px; line-height: 1.6; margin-bottom: 20px; }}
                .retry {{
                    color: #07c160;
                    font-size: 14px;
                    text-decoration: none;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="error-icon">✕</div>
                <h1>授权失败</h1>
                <p class="desc">{message}</p>
                <p style="color:#999;font-size:13px;">请返回企业微信重新获取授权链接</p>
            </div>
        </body>
        </html>
        """