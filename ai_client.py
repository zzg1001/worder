# -*- coding: utf-8 -*-
"""
ai_client.py - AI接口客户端
"""

import json
import logging
import requests

logger = logging.getLogger(__name__)


def _log_api(api_name, url, request_data, response_data):
    """统一打印接口日志"""
    print("\n" + "=" * 60)
    print(f"【{api_name}】")
    print("-" * 60)
    print(f"URL: {url}")
    print("-" * 60)
    print("输入:")
    print(json.dumps(request_data, ensure_ascii=False, indent=2))
    print("-" * 60)
    print("输出:")
    print(json.dumps(response_data, ensure_ascii=False, indent=2))
    print("=" * 60 + "\n")


class AIClient:
    """AI服务客户端"""

    def __init__(self, api_url, api_key, image_api_url=None, image_api_key=None,
                 work_order_api_url=None, work_order_api_key=None,
                 intent_api_url=None, intent_api_key=None):
        self.api_url = api_url
        self.api_key = api_key
        self._conversation_ids = {}
        self.base_url = api_url.replace("/chat-messages", "")
        self.image_api_url = image_api_url
        self.image_api_key = image_api_key
        self.work_order_api_url = work_order_api_url
        self.work_order_api_key = work_order_api_key
        self.intent_api_url = intent_api_url
        self.intent_api_key = intent_api_key

    def upload_image(self, image_data, filename, user_id):
        """上传图片到Dify，返回file_id"""
        api_name = "图片上传接口"
        upload_url = f"{self.base_url}/files/upload"

        request_data = {"file": f"(binary, {filename})", "user": user_id}

        try:
            resp = requests.post(
                upload_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={'file': (filename, image_data, 'image/png')},
                data={'user': user_id},
                timeout=30
            )
            resp.raise_for_status()
            result = resp.json()

            _log_api(api_name, upload_url, request_data, result)
            return result.get('id')

        except Exception as e:
            _log_api(api_name, upload_url, request_data, {"error": str(e)})
            logger.error(f"[{api_name}] 失败: {e}")
            return None

    def chat(self, user_id, message, files=None):
        """发送消息到AI并获取回复"""
        api_name = "聊天对话接口"
        conversation_id = self._conversation_ids.get(user_id, "")

        payload = {
            "inputs": {},
            "query": message,
            "response_mode": "streaming",
            "conversation_id": conversation_id,
            "user": user_id,
            "files": files or []
        }

        try:
            resp = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=60,
                stream=True
            )
            resp.raise_for_status()

            full_answer = ""
            new_conversation_id = ""
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
                                new_conversation_id = json_data.get('conversation_id', '')
                                if new_conversation_id:
                                    self._conversation_ids[user_id] = new_conversation_id
                        except json.JSONDecodeError:
                            continue

            response_data = {
                "answer": full_answer,
                "conversation_id": new_conversation_id
            }
            _log_api(api_name, self.api_url, payload, response_data)
            return full_answer if full_answer else "AI未返回有效内容"

        except Exception as e:
            _log_api(api_name, self.api_url, payload, {"error": str(e)})
            logger.error(f"[{api_name}] 失败: {e}")
            return "AI服务暂时不可用，请稍后重试"

    def analyze_image(self, user_id, file_id, text_content=None):
        """调用图片解析workflow接口"""
        api_name = "图片解析接口"

        if not self.image_api_url or not self.image_api_key:
            logger.error(f"[{api_name}] 未配置")
            return "图片解析服务未配置"

        payload = {
            "inputs": {
                "tup": {
                    "transfer_method": "local_file",
                    "upload_file_id": file_id,
                    "type": "image"
                }
            },
            "response_mode": "blocking",
            "user": user_id
        }

        try:
            resp = requests.post(
                self.image_api_url,
                headers={
                    "Authorization": f"Bearer {self.image_api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=120
            )
            resp.raise_for_status()
            result = resp.json()

            _log_api(api_name, self.image_api_url, payload, result)

            outputs = result.get('data', {}).get('outputs', {})
            full_output = outputs.get('text') or outputs.get('result') or outputs.get('output') or str(outputs)
            return full_output if full_output else "图片解析未返回有效内容"

        except Exception as e:
            _log_api(api_name, self.image_api_url, payload, {"error": str(e)})
            logger.error(f"[{api_name}] 失败: {e}")
            return "图片解析服务暂时不可用，请稍后重试"

    def submit_work_order(self, user_id, work_order_data):
        """调用工单提交workflow接口"""
        api_name = "工单创建接口"

        if not self.work_order_api_url or not self.work_order_api_key:
            logger.error(f"[{api_name}] 未配置")
            return False, "工单提交服务未配置"

        text_content = json.dumps(work_order_data, ensure_ascii=False)
        payload = {
            "inputs": {"text": text_content},
            "response_mode": "blocking",
            "user": user_id
        }

        try:
            resp = requests.post(
                self.work_order_api_url,
                headers={
                    "Authorization": f"Bearer {self.work_order_api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=120
            )
            resp.raise_for_status()
            result = resp.json()

            _log_api(api_name, self.work_order_api_url, payload, result)

            outputs = result.get('data', {}).get('outputs', {})
            status_code = outputs.get('status_code')

            if str(status_code) == "200":
                return True, "200"
            elif str(status_code) == "600":
                return False, "600"
            else:
                return False, f"状态码: {status_code}"

        except Exception as e:
            _log_api(api_name, self.work_order_api_url, payload, {"error": str(e)})
            logger.error(f"[{api_name}] 失败: {e}")
            return False, f"工单提交失败: {str(e)}"

    def clear_conversation(self, user_id):
        """清空用户的会话上下文"""
        if user_id in self._conversation_ids:
            del self._conversation_ids[user_id]
            logger.info(f"已清空用户会话上下文: {user_id}")

    def check_intent(self, user_id, query):
        """调用意图判断workflow接口

        Returns:
            int: 1=同意生成工单, 2=不同意, 3=想修改
        """
        api_name = "意图判断接口"

        if not self.intent_api_url or not self.intent_api_key:
            logger.error(f"[{api_name}] 未配置")
            return 3

        payload = {
            "inputs": {"decision": query},
            "response_mode": "blocking",
            "user": user_id
        }

        try:
            resp = requests.post(
                self.intent_api_url,
                headers={
                    "Authorization": f"Bearer {self.intent_api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )
            resp.raise_for_status()
            result = resp.json()

            _log_api(api_name, self.intent_api_url, payload, result)

            outputs = result.get('data', {}).get('outputs', {})
            intent = outputs.get('text') or ""

            try:
                return int(str(intent).strip())
            except ValueError:
                return 3

        except Exception as e:
            _log_api(api_name, self.intent_api_url, payload, {"error": str(e)})
            logger.error(f"[{api_name}] 失败: {e}")
            return 3
