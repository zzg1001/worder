# -*- coding: utf-8 -*-
"""
ai_client.py - AI接口客户端（原文件提取）
"""

import json
import logging
import requests

logger = logging.getLogger(__name__)


class AIClient:
    """AI服务客户端"""

    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self._conversation_ids = {}

    def chat(self, user_id, message):
        """发送消息到AI并获取回复"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        conversation_id = self._conversation_ids.get(user_id, "")

        payload = {
            "inputs": {},
            "query": message,
            "response_mode": "streaming",
            "conversation_id": conversation_id,
            "user": user_id,
            "files": []
        }

        try:
            resp = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=60,
                stream=True
            )
            resp.raise_for_status()

            full_answer = ""
            for line in resp.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        data = line_text[6:]
                        if data == '[DONE]':
                            break
                        try:
                            json_data = json.loads(data)
                            if json_data.get('event') == 'message':
                                full_answer += json_data.get('answer', '')
                            elif json_data.get('event') == 'message_end':
                                new_conv_id = json_data.get('conversation_id')
                                if new_conv_id:
                                    self._conversation_ids[user_id] = new_conv_id
                        except json.JSONDecodeError:
                            continue

            return full_answer if full_answer else "AI未返回有效内容"

        except Exception as e:
            logger.error(f"AI调用异常: {e}")
            return "AI服务暂时不可用，请稍后重试"