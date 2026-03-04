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
            logger.info(f"获取用户信息API返回: {resp}")
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

    def get_jsapi_ticket(self, force_refresh=False):
        """获取jsapi_ticket（用于JSSDK签名）"""
        if not hasattr(self, '_jsapi_ticket_cache'):
            self._jsapi_ticket_cache = {"ticket": None, "expire_time": 0}

        now = time.time()
        if not force_refresh and self._jsapi_ticket_cache["ticket"] and now < self._jsapi_ticket_cache["expire_time"]:
            return self._jsapi_ticket_cache["ticket"]

        access_token = self.get_access_token()
        if not access_token:
            return None

        url = f"https://qyapi.weixin.qq.com/cgi-bin/get_jsapi_ticket?access_token={access_token}"
        try:
            resp = requests.get(url, timeout=10).json()
            if resp.get("errcode") == 0:
                self._jsapi_ticket_cache["ticket"] = resp["ticket"]
                self._jsapi_ticket_cache["expire_time"] = now + 7100
                logger.info("jsapi_ticket获取成功")
                return resp["ticket"]
            else:
                logger.error(f"获取jsapi_ticket失败: {resp}")
                return None
        except Exception as e:
            logger.error(f"获取jsapi_ticket异常: {e}")
            return None

    def get_agent_jsapi_ticket(self, force_refresh=False):
        """获取应用的jsapi_ticket（用于agentConfig签名）"""
        if not hasattr(self, '_agent_jsapi_ticket_cache'):
            self._agent_jsapi_ticket_cache = {"ticket": None, "expire_time": 0}

        now = time.time()
        if not force_refresh and self._agent_jsapi_ticket_cache["ticket"] and now < self._agent_jsapi_ticket_cache["expire_time"]:
            return self._agent_jsapi_ticket_cache["ticket"]

        access_token = self.get_access_token()
        if not access_token:
            return None

        url = f"https://qyapi.weixin.qq.com/cgi-bin/ticket/get?access_token={access_token}&type=agent_config"
        try:
            resp = requests.get(url, timeout=10).json()
            if resp.get("errcode") == 0:
                self._agent_jsapi_ticket_cache["ticket"] = resp["ticket"]
                self._agent_jsapi_ticket_cache["expire_time"] = now + 7100
                logger.info("agent_jsapi_ticket获取成功")
                return resp["ticket"]
            else:
                logger.error(f"获取agent_jsapi_ticket失败: {resp}")
                return None
        except Exception as e:
            logger.error(f"获取agent_jsapi_ticket异常: {e}")
            return None

    def get_jsapi_signature(self, url):
        """生成JSSDK签名（包含corp和agent两个签名）"""
        import hashlib

        # 企业签名
        corp_ticket = self.get_jsapi_ticket()
        if not corp_ticket:
            return None

        timestamp = str(int(time.time()))
        noncestr = hashlib.md5(f"{timestamp}".encode()).hexdigest()[:16]

        # 企业签名
        corp_sign_str = f"jsapi_ticket={corp_ticket}&noncestr={noncestr}&timestamp={timestamp}&url={url}"
        corp_signature = hashlib.sha1(corp_sign_str.encode()).hexdigest()

        # 应用签名
        agent_ticket = self.get_agent_jsapi_ticket()
        agent_signature = ""
        if agent_ticket:
            agent_sign_str = f"jsapi_ticket={agent_ticket}&noncestr={noncestr}&timestamp={timestamp}&url={url}"
            agent_signature = hashlib.sha1(agent_sign_str.encode()).hexdigest()

        return {
            "appId": self.corp_id,
            "agentId": self.agent_id,
            "timestamp": timestamp,
            "nonceStr": noncestr,
            "signature": corp_signature,
            "agentSignature": agent_signature
        }

    def download_media(self, media_id):
        """下载媒体文件（图片、语音、视频、文件）

        Returns:
            tuple: (文件内容bytes, 文件名) 或 (None, None)
        """
        access_token = self.get_access_token()
        if not access_token:
            return None, None

        url = f"https://qyapi.weixin.qq.com/cgi-bin/media/get?access_token={access_token}&media_id={media_id}"
        try:
            resp = requests.get(url, timeout=30)

            # 检查是否返回错误JSON
            content_type = resp.headers.get('Content-Type', '')
            if 'application/json' in content_type or 'text/plain' in content_type:
                error_info = resp.json()
                logger.error(f"下载媒体文件失败: {error_info}")
                return None, None

            # 从Content-Disposition获取文件名
            content_disposition = resp.headers.get('Content-Disposition', '')
            filename = None
            if 'filename=' in content_disposition:
                # 解析文件名
                import re
                match = re.search(r'filename="?([^";\n]+)"?', content_disposition)
                if match:
                    filename = match.group(1)

            if not filename:
                # 根据Content-Type生成默认文件名
                import uuid
                ext_map = {
                    'image/jpeg': '.jpg',
                    'image/png': '.png',
                    'image/gif': '.gif',
                    'audio/amr': '.amr',
                    'video/mp4': '.mp4',
                    'application/octet-stream': ''
                }
                ext = ext_map.get(content_type.split(';')[0], '')
                filename = f"{uuid.uuid4().hex}{ext}"

            logger.info(f"下载媒体文件成功: {filename}, 大小: {len(resp.content)} bytes")
            return resp.content, filename

        except Exception as e:
            logger.error(f"下载媒体文件异常: {e}")
            return None, None