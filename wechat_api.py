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

    def __init__(self, corp_id, corp_secret, agent_id, contacts_secret=None):
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.contacts_secret = contacts_secret
        self.agent_id = int(agent_id)
        self._token_cache = {
            "access_token": None,
            "expire_time": 0
        }
        self._contacts_token_cache = {
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

    def get_contacts_access_token(self, force_refresh=False):
        """获取通讯录AccessToken（用于获取部门和用户信息）"""
        if not self.contacts_secret:
            logger.warning("未配置通讯录Secret，使用应用Token")
            return self.get_access_token(force_refresh)

        now = time.time()
        if not force_refresh and self._contacts_token_cache["access_token"] and now < self._contacts_token_cache["expire_time"]:
            return self._contacts_token_cache["access_token"]

        logger.info(f"开始获取通讯录Token, corpid={self.corp_id}")
        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corp_id}&corpsecret={self.contacts_secret}"
        try:
            resp = requests.get(url, timeout=10).json()
            logger.info(f"通讯录Token响应: errcode={resp.get('errcode')}, errmsg={resp.get('errmsg')}")
            if resp.get("access_token"):
                self._contacts_token_cache["access_token"] = resp["access_token"]
                self._contacts_token_cache["expire_time"] = now + 7100
                logger.info("通讯录AccessToken获取成功")
                return resp["access_token"]
            else:
                logger.error(f"获取通讯录token失败: {resp}")
                return None
        except Exception as e:
            logger.error(f"获取通讯录token异常: {e}")
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
                dept_map = {d['id']: d['name'] for d in resp.get('department', [])}
                logger.info(f"获取部门列表成功: {len(dept_map)}个部门")
                return dept_map
            else:
                logger.warning(f"获取部门列表失败: {resp}")
                return {}
        except Exception as e:
            logger.error(f"获取部门列表异常: {e}")
            return {}

    def send_app_message(self, touser, content, msg_type="text"):
        """发送应用消息"""
        access_token = self.get_access_token()
        if not access_token:
            return None

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
            if result.get("errcode") == 0:
                return result.get("msgid")  # 返回消息ID，用于后续撤回
            return None
        except Exception as e:
            logger.error(f"发送消息异常: {e}")
            return None

    def recall_message(self, msgid):
        """撤回应用消息"""
        access_token = self.get_access_token()
        if not access_token:
            return False

        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/recall?access_token={access_token}"
        data = {"msgid": msgid}

        try:
            resp = requests.post(url, json=data, timeout=10)
            result = resp.json()
            if result.get("errcode") == 0:
                logger.info(f"撤回消息成功: msgid={msgid}")
                return True
            else:
                logger.warning(f"撤回消息失败: {result}")
                return False
        except Exception as e:
            logger.error(f"撤回消息异常: {e}")
            return False

    def send_template_card(self, touser, card_type, main_title, sub_title="", response_code=None):
        """发送模板卡片消息（文本通知型）

        Args:
            touser: 接收用户ID
            card_type: 卡片类型，如 "text_notice"
            main_title: 主标题
            sub_title: 副标题（灰色小字）
            response_code: 用于更新卡片的唯一标识

        Returns:
            dict: {"response_code": ..., "msgid": ...} 或 None
        """
        access_token = self.get_access_token()
        if not access_token:
            return None

        import uuid
        if not response_code:
            response_code = str(uuid.uuid4())

        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"

        card = {
            "card_type": card_type,
            "source": {
                "desc": "AI助手"
            },
            "main_title": {
                "title": main_title
            },
            "card_action": {
                "type": 1,
                "url": ""
            },
            "task_id": response_code
        }

        if sub_title:
            card["sub_title_text"] = sub_title

        data = {
            "touser": touser,
            "msgtype": "template_card",
            "agentid": self.agent_id,
            "template_card": card
        }

        try:
            resp = requests.post(url, json=data, timeout=10)
            result = resp.json()
            logger.info(f"发送模板卡片结果: {result}")
            if result.get("errcode") == 0:
                return {
                    "response_code": response_code,
                    "msgid": result.get("msgid")
                }
            return None
        except Exception as e:
            logger.error(f"发送模板卡片异常: {e}")
            return None

    def update_template_card(self, touser, response_code, main_title, sub_title=""):
        """更新模板卡片消息

        Args:
            touser: 接收用户ID
            response_code: 发送时返回的response_code
            main_title: 新的主标题
            sub_title: 新的副标题（灰色小字）
        """
        access_token = self.get_access_token()
        if not access_token:
            return False

        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/update_template_card?access_token={access_token}"

        card = {
            "card_type": "text_notice",
            "source": {
                "desc": "AI助手"
            },
            "main_title": {
                "title": main_title
            },
            "card_action": {
                "type": 1,
                "url": ""
            }
        }

        if sub_title:
            card["sub_title_text"] = sub_title

        data = {
            "userids": [touser],
            "agentid": self.agent_id,
            "response_code": response_code,
            "template_card": card
        }

        try:
            resp = requests.post(url, json=data, timeout=10)
            result = resp.json()
            if result.get("errcode") == 0:
                logger.info(f"更新模板卡片成功: response_code={response_code}")
                return True
            else:
                logger.warning(f"更新模板卡片失败: {result}")
                return False
        except Exception as e:
            logger.error(f"更新模板卡片异常: {e}")
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