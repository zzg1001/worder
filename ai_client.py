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

    def __init__(self, api_url, api_key, image_api_url=None, image_api_key=None,
                 work_order_api_url=None, work_order_api_key=None):
        self.api_url = api_url
        self.api_key = api_key
        self._conversation_ids = {}
        # 从chat-messages URL推导出基础URL
        self.base_url = api_url.replace("/chat-messages", "")
        # 图片AI接口配置
        self.image_api_url = image_api_url
        self.image_api_key = image_api_key
        # 工单提交AI接口配置
        self.work_order_api_url = work_order_api_url
        self.work_order_api_key = work_order_api_key

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

    def analyze_image(self, user_id, file_id, text_content=None):
        """调用图片解析workflow接口"""
        if not self.image_api_url or not self.image_api_key:
            logger.error("图片AI接口未配置")
            return "图片解析服务未配置"

        headers = {
            "Authorization": f"Bearer {self.image_api_key}",
            "Content-Type": "application/json"
        }

        # workflow的输入格式
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

        # 打印完整请求
        print("\n" + "=" * 60)
        print(">>> 图片AI接口请求（Workflow） <<<")
        print("=" * 60)
        print(f"URL: {self.image_api_url}")
        print(f"Headers: {json.dumps(headers, ensure_ascii=False, indent=2)}")
        print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        print("=" * 60 + "\n")

        try:
            resp = requests.post(
                self.image_api_url,
                headers=headers,
                json=payload,
                timeout=120
            )
            resp.raise_for_status()

            result = resp.json()

            # 打印完整响应
            print("\n" + "-" * 60)
            print(">>> 图片AI接口响应 <<<")
            print("-" * 60)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("-" * 60 + "\n")

            # blocking模式直接返回结果
            outputs = result.get('data', {}).get('outputs', {})
            # 尝试获取输出文本（根据workflow配置可能是不同的key）
            full_output = outputs.get('text') or outputs.get('result') or outputs.get('output') or str(outputs)

            return full_output if full_output else "图片解析未返回有效内容"

        except Exception as e:
            logger.error(f"图片AI调用异常: {e}")
            return "图片解析服务暂时不可用，请稍后重试"

    def submit_work_order(self, user_id, work_order_data, query):
        """调用工单提交workflow接口

        Args:
            user_id: 用户ID
            work_order_data: 工单数据字典
            query: 用户回复内容，让大模型判断是否保存

        Returns:
            tuple: (success, result_message)
        """
        if not self.work_order_api_url or not self.work_order_api_key:
            logger.error("工单提交AI接口未配置")
            return False, "工单提交服务未配置"

        headers = {
            "Authorization": f"Bearer {self.work_order_api_key}",
            "Content-Type": "application/json"
        }

        # 将工单数据转为JSON字符串
        text_content = json.dumps(work_order_data, ensure_ascii=False)

        # workflow的输入格式 - query是用户回复，text是工单数据
        payload = {
            "inputs": {
                "query": query,
                "text": text_content
            },
            "response_mode": "blocking",
            "user": user_id
        }

        # 打印完整请求
        print("\n" + "=" * 60)
        print(">>> 工单提交AI接口请求（Workflow） <<<")
        print("=" * 60)
        print(f"URL: {self.work_order_api_url}")
        print(f"Headers: {json.dumps(headers, ensure_ascii=False, indent=2)}")
        print(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)}")
        print("=" * 60 + "\n")

        try:
            resp = requests.post(
                self.work_order_api_url,
                headers=headers,
                json=payload,
                timeout=120
            )
            resp.raise_for_status()

            result = resp.json()

            # 打印完整响应
            print("\n" + "-" * 60)
            print(">>> 工单提交AI接口响应 <<<")
            print("-" * 60)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("-" * 60 + "\n")

            # blocking模式直接返回结果
            outputs = result.get('data', {}).get('outputs', {})
            # 获取返回的text
            output_text = outputs.get('text') or outputs.get('result') or outputs.get('output') or ""

            logger.info(f"工单提交返回: {output_text}")

            # 解析返回的JSON，获取status_code
            try:
                if isinstance(output_text, str):
                    output_data = json.loads(output_text)
                else:
                    output_data = output_text

                status_code = output_data.get('status_code')

                if status_code == 200:
                    return True, "200"
                elif status_code == 600:
                    return False, "600"
                else:
                    return False, f"状态码: {status_code}"
            except json.JSONDecodeError:
                # 如果不是JSON，直接判断
                if "200" in str(output_text):
                    return True, "200"
                if "600" in str(output_text):
                    return False, "600"
                return False, f"返回: {output_text}"

        except Exception as e:
            logger.error(f"工单提交AI调用异常: {e}")
            return False, f"工单提交失败: {str(e)}"

    def clear_conversation(self, user_id):
        """清空用户的会话上下文"""
        if user_id in self._conversation_ids:
            del self._conversation_ids[user_id]
            logger.info(f"已清空用户会话上下文: {user_id}")