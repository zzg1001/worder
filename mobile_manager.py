# -*- coding: utf-8 -*-
"""
mobile_manager.py - 手机号管理模块
"""

import re
import hashlib
import random
import time
import logging
from urllib.parse import quote
from datetime import datetime

logger = logging.getLogger(__name__)


class MobileManager:
    """手机号管理器"""

    def __init__(self, sign_key, redirect_uri, agent_id, corp_id):
        self.sign_key = sign_key
        self.redirect_uri = redirect_uri
        self.agent_id = agent_id
        self.corp_id = corp_id
        self._bindings = {}
        self._auth_states = {}

    def extract_mobile(self, text):
        """从文本中提取手机号"""
        pattern = r'1[3-9]\d{9}'
        match = re.search(pattern, text.replace('-', '').replace(' ', ''))
        return match.group(0) if match else None

    def bind_mobile(self, userid, mobile):
        """绑定用户手机号"""
        self._bindings[userid] = {
            "mobile": mobile,
            "bind_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "manual"
        }
        logger.info(f"用户 {userid} 绑定手机号: {mobile}")
        return True

    def get_mobile(self, userid, api_mobile=""):
        """获取用户手机号"""
        if api_mobile:
            return api_mobile, "api"

        if userid in self._bindings:
            return self._bindings[userid]["mobile"], "binding"

        return "", "none"

    def is_bound(self, userid):
        """检查用户是否已绑定手机号"""
        return userid in self._bindings

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

        logger.info(f"生成授权链接成功: {userid}")
        return auth_url

    def verify_state(self, state):
        """验证state是否合法"""
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

    def format_user_info(self, userid, user_info, mobile_info):
        """格式化用户信息输出"""
        lines = [
            "=" * 60,
            "【用户信息详情】",
            "=" * 60,
            f"  用户ID: {userid}",
            f"  姓名: {user_info.get('name', '未知') if user_info else '未知'}",
            f"  职位: {user_info.get('position', '未设置') if user_info else '未知'}",
        ]

        if mobile_info[0]:
            source_text = "企业微信API" if mobile_info[1] == "api" else "用户绑定"
            lines.append(f"  手机号: {mobile_info[0]} (来源: {source_text})")
        else:
            lines.append(f"  手机号: 【未获取】")
            lines.append(f"\n  💡 提示: 回复\"绑定手机号138xxxx\"或\"获取手机号\"")

        email = user_info.get('email', '') if user_info else ''
        if email:
            lines.append(f"  邮箱: {email}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def format_bind_success(self, name, userid, mobile):
        """格式化绑定成功信息"""
        return (
            f"\n{'=' * 60}\n"
            f"【手机号绑定成功】\n"
            f"{'=' * 60}\n"
            f"  用户: {name} ({userid})\n"
            f"  手机号: {mobile}\n"
            f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{'=' * 60}\n"
        )