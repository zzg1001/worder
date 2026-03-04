# -*- coding: utf-8 -*-
"""
ai_client.py - AI接口客户端（原文件提取）
"""

import json
import logging
import requests
import base64

logger = logging.getLogger(__name__)


class AIClient:
    """AI服务客户端"""

    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self._conversation_ids = {}
        # 从chat-messages URL推导出基础URL
        self.base_url = api_url.replace("/chat-messages", "")

    def upload_image(self, image_data, filename, user_id):
        """上传图片到Dify，返回file_id"""
        upload_url = f"{self.base_url}/files/upload"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            files = {
                'file': (filename, image_data, 'image/png')
            }
            data = {
                'user': user_id
            }

            resp = requests.post(
                upload_url,
                headers=headers,
                files=files,
                data=data,
                timeout=30
            )
            resp.raise_for_status()

            result = resp.json()
            file_id = result.get('id')
            logger.info(f"图片上传成功: file_id={file_id}")
            return file_id

        except Exception as e:
            logger.error(f"图片上传失败: {e}")
            return None

    def chat(self, user_id, message, files=None):
        """发送消息到AI并获取回复

        Args:
            user_id: 用户ID
            message: 消息内容
            files: 文件列表，格式为 [{"type": "image", "transfer_method": "local_file", "upload_file_id": "xxx"}]
        """
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
            "files": files or []
        }

        # 打印完整请求
        print("\n" + "=" * 60)
        print(">>> AI接口请求 <<<")
        print("=" * 60)
        print(f"URL: {self.api_url}")
        print(f"Headers: {json.dumps(headers, ensure_ascii=False, indent=2)}")
        print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        print("=" * 60 + "\n")

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