# -*- coding: utf-8 -*-
"""
wechat_api.py - 企业微信API封装
"""

import logging
import time
import requests

logger = logging.getLogger(__name__)


class WeChatAPI:
    """企业微信API客户端"""

    def __init__(self, corp_id, corp_secret, agent_id):
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.agent_id = int(agent_id)
        self._token_cache = {
            "access_token": None,
            "expire_time": 0
        }

    def get_access_token(self, force_refresh=False):
        """获取AccessToken（带缓存）"""
        now = time.time()

        if not force_refresh and self._token_cache["access_token"] and now < self._token_cache["expire_time"]:
            return self._token_cache["access_token"]

        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corp_id}&corpsecret={self.corp_secret}"
        try:
            resp = requests.get(url, timeout=10).json()
            if resp.get("access_token"):
                self._token_cache["access_token"] = resp["access_token"]
                self._token_cache["expire_time"] = now + 7100
                logger.info("AccessToken获取成功")
                return resp["access_token"]
            else:
                logger.error(f"获取token失败: {resp}")
                return None
        except Exception as e:
            logger.error(f"获取token异常: {e}")
            return None

    def get_user_info(self, userid):
        """获取用户基本信息（包含部门）"""
        access_token = self.get_access_token()
        if not access_token:
            return None

        url = f"https://qyapi.weixin.qq.com/cgi-bin/user/get?access_token={access_token}&userid={userid}"
        try:
            resp = requests.get(url, timeout=10).json()
            if resp.get("errcode") == 0:
                return {
                    "errcode": 0,
                    "userid": userid,
                    "name": resp.get("name", "未知"),
                    "mobile": resp.get("mobile", ""),  # 这里可能为空，需要通过OAuth获取
                    "department": resp.get("department", []),
                    "position": resp.get("position", ""),
                    "email": resp.get("email", ""),
                    "avatar": resp.get("avatar", ""),
                    "gender": resp.get("gender", 0),
                    "status": resp.get("status", 1)
                }
            else:
                logger.error(f"获取用户信息失败: {resp}")
                return None
        except Exception as e:
            logger.error(f"获取用户信息异常: {e}")
            return None

    def get_department_list(self):
        """获取部门列表"""
        access_token = self.get_access_token()
        if not access_token:
            return {}

        url = f"https://qyapi.weixin.qq.com/cgi-bin/department/list?access_token={access_token}"
        try:
            resp = requests.get(url, timeout=10).json()
            if resp.get("errcode") == 0:
                return {d['id']: d['name'] for d in resp.get('department', [])}
            return {}
        except Exception as e:
            logger.error(f"获取部门列表异常: {e}")
            return {}

    def send_app_message(self, touser, content, msg_type="text"):
        """发送应用消息"""
        access_token = self.get_access_token()
        if not access_token:
            return False

        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"

        if msg_type == "text":
            data = {
                "touser": touser,
                "msgtype": "text",
                "agentid": self.agent_id,
                "text": {"content": content},
                "safe": 0
            }
        else:
            data = {
                "touser": touser,
                "msgtype": msg_type,
                "agentid": self.agent_id,
                "safe": 0
            }

        try:
            resp = requests.post(url, json=data, timeout=10)
            result = resp.json()
            logger.info(f"发送消息结果: {result}")
            return result.get("errcode") == 0
        except Exception as e:
            logger.error(f"发送消息异常: {e}")
            return False

    def get_user_info_by_code(self, code):
        """通过code获取用户信息（OAuth授权流程）"""
        access_token = self.get_access_token()
        if not access_token:
            return None

        url = f"https://qyapi.weixin.qq.com/cgi-bin/auth/getuserinfo?access_token={access_token}&code={code}"
        try:
            resp = requests.get(url, timeout=10).json()
            if resp.get("errcode") == 0:
                return {
                    "userid": resp.get("userid"),
                    "user_ticket": resp.get("user_ticket"),
                    "expires_in": resp.get("expires_in", 7200)
                }
            else:
                logger.error(f"获取userinfo失败: {resp}")
                return None
        except Exception as e:
            logger.error(f"获取userinfo异常: {e}")
            return None

    def get_user_detail(self, user_ticket):
        """通过user_ticket获取用户详情（含手机号）"""
        access_token = self.get_access_token()
        if not access_token:
            return None

        url = f"https://qyapi.weixin.qq.com/cgi-bin/auth/getuserdetail?access_token={access_token}"
        try:
            resp = requests.post(
                url,
                json={"user_ticket": user_ticket},
                timeout=10
            ).json()

            if resp.get("errcode") == 0:
                return {
                    "userid": resp.get("userid"),
                    "name": resp.get("name", ""),
                    "mobile": resp.get("mobile", ""),
                    "email": resp.get("email", ""),
                    "avatar": resp.get("avatar", ""),
                    "position": resp.get("position", ""),
                    "gender": resp.get("gender", 0)
                }
            else:
                logger.error(f"获取userdetail失败: {resp}")
                return None
        except Exception as e:
            logger.error(f"获取userdetail异常: {e}")
            return None