# -*- coding: utf-8 -*-
"""
ai_client.py - AI接口客户端（原文件提取）
"""

import json
import logging
import requests
import base64

logger = logging.getLogger(__name__)


def _log_request(api_name, url, headers, payload):
    """统一打印请求日志"""
    print("\n" + "=" * 70)
    print(f"【{api_name}】 请求")
    print("=" * 70)
    print(f"接口地址: {url}")
    print("-" * 70)
    print("请求头 (Headers):")
    # 隐藏Authorization中的token，只显示前10位
    safe_headers = headers.copy()
    if 'Authorization' in safe_headers:
        token = safe_headers['Authorization']
        if len(token) > 20:
            safe_headers['Authorization'] = token[:20] + "..."
    print(json.dumps(safe_headers, ensure_ascii=False, indent=2))
    print("-" * 70)
    print("请求体 (Payload):")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("=" * 70 + "\n")


def _log_response(api_name, response_data, extra_info=None):
    """统一打印响应日志"""
    print("\n" + "-" * 70)
    print(f"【{api_name}】 响应")
    print("-" * 70)
    print("响应数据 (Response):")
    print(json.dumps(response_data, ensure_ascii=False, indent=2))
    if extra_info:
        print("-" * 70)
        print(f"解析结果: {extra_info}")
    print("-" * 70 + "\n")


def _log_error(api_name, error):
    """统一打印错误日志"""
    print("\n" + "!" * 70)
    print(f"【{api_name}】 错误")
    print("!" * 70)
    print(f"错误信息: {error}")
    print("!" * 70 + "\n")


class AIClient:
    """AI服务客户端"""

    def __init__(self, api_url, api_key, image_api_url=None, image_api_key=None,
                 work_order_api_url=None, work_order_api_key=None,
                 intent_api_url=None, intent_api_key=None):
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
        # 意图判断AI接口配置
        self.intent_api_url = intent_api_url
        self.intent_api_key = intent_api_key

    def upload_image(self, image_data, filename, user_id):
        """上传图片到Dify，返回file_id"""
        api_name = "图片上传接口"
        upload_url = f"{self.base_url}/files/upload"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        # 打印请求日志（文件上传特殊处理）
        print("\n" + "=" * 70)
        print(f"【{api_name}】 请求")
        print("=" * 70)
        print(f"接口地址: {upload_url}")
        print("-" * 70)
        print("请求参数:")
        print(json.dumps({
            "file": f"(binary data, filename={filename})",
            "user": user_id
        }, ensure_ascii=False, indent=2))
        print("=" * 70 + "\n")

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

            _log_response(api_name, result, f"file_id={file_id}")
            logger.info(f"[{api_name}] 成功: file_id={file_id}")
            return file_id

        except Exception as e:
            _log_error(api_name, str(e))
            logger.error(f"[{api_name}] 失败: {e}")
            return None

    def chat(self, user_id, message, files=None):
        """发送消息到AI并获取回复

        Args:
            user_id: 用户ID
            message: 消息内容
            files: 文件列表，格式为 [{"type": "image", "transfer_method": "local_file", "upload_file_id": "xxx"}]
        """
        api_name = "聊天对话接口 (chat-messages)"
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

        _log_request(api_name, self.api_url, headers, payload)

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

            # 打印响应日志
            response_summary = {
                "answer": full_answer[:200] + "..." if len(full_answer) > 200 else full_answer,
                "conversation_id": new_conversation_id,
                "answer_length": len(full_answer)
            }
            _log_response(api_name, response_summary, f"conversation_id={new_conversation_id}")
            logger.info(f"[{api_name}] 成功: 回复长度={len(full_answer)}, conversation_id={new_conversation_id}")

            return full_answer if full_answer else "AI未返回有效内容"

        except Exception as e:
            _log_error(api_name, str(e))
            logger.error(f"[{api_name}] 失败: {e}")
            return "AI服务暂时不可用，请稍后重试"

    def analyze_image(self, user_id, file_id, text_content=None):
        """调用图片解析workflow接口"""
        api_name = "图片解析接口 (workflow)"

        if not self.image_api_url or not self.image_api_key:
            _log_error(api_name, "接口未配置")
            logger.error(f"[{api_name}] 未配置")
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

        _log_request(api_name, self.image_api_url, headers, payload)

        try:
            resp = requests.post(
                self.image_api_url,
                headers=headers,
                json=payload,
                timeout=120
            )
            resp.raise_for_status()

            result = resp.json()

            # blocking模式直接返回结果
            outputs = result.get('data', {}).get('outputs', {})
            # 尝试获取输出文本（根据workflow配置可能是不同的key）
            full_output = outputs.get('text') or outputs.get('result') or outputs.get('output') or str(outputs)

            _log_response(api_name, result, f"解析文本长度={len(full_output)}")
            logger.info(f"[{api_name}] 成功: 解析文本长度={len(full_output)}")

            return full_output if full_output else "图片解析未返回有效内容"

        except Exception as e:
            _log_error(api_name, str(e))
            logger.error(f"[{api_name}] 失败: {e}")
            return "图片解析服务暂时不可用，请稍后重试"

    def submit_work_order(self, user_id, work_order_data):
        """调用工单提交workflow接口

        Args:
            user_id: 用户ID
            work_order_data: 工单数据字典

        Returns:
            tuple: (success, result_message)
        """
        api_name = "工单创建接口 (workflow)"

        if not self.work_order_api_url or not self.work_order_api_key:
            _log_error(api_name, "接口未配置")
            logger.error(f"[{api_name}] 未配置")
            return False, "工单提交服务未配置"

        headers = {
            "Authorization": f"Bearer {self.work_order_api_key}",
            "Content-Type": "application/json"
        }

        # 将工单数据转为JSON字符串
        text_content = json.dumps(work_order_data, ensure_ascii=False)

        # workflow的输入格式 - 只有text参数
        payload = {
            "inputs": {
                "text": text_content
            },
            "response_mode": "blocking",
            "user": user_id
        }

        _log_request(api_name, self.work_order_api_url, headers, payload)

        try:
            resp = requests.post(
                self.work_order_api_url,
                headers=headers,
                json=payload,
                timeout=120
            )
            resp.raise_for_status()

            result = resp.json()

            # blocking模式直接返回结果
            outputs = result.get('data', {}).get('outputs', {})
            # 直接获取status_code
            status_code = outputs.get('status_code')

            _log_response(api_name, result, f"status_code={status_code}")
            logger.info(f"[{api_name}] 返回 status_code={status_code}")

            if str(status_code) == "200":
                return True, "200"
            elif str(status_code) == "600":
                return False, "600"
            else:
                return False, f"状态码: {status_code}"

        except Exception as e:
            _log_error(api_name, str(e))
            logger.error(f"[{api_name}] 失败: {e}")
            return False, f"工单提交失败: {str(e)}"

    def clear_conversation(self, user_id):
        """清空用户的会话上下文"""
        if user_id in self._conversation_ids:
            del self._conversation_ids[user_id]
            print(f"\n>>> 已清空用户会话上下文: {user_id} <<<\n")
            logger.info(f"[会话管理] 已清空用户会话上下文: {user_id}")

    def check_intent(self, user_id, query):
        """调用意图判断workflow接口

        Args:
            user_id: 用户ID
            query: 用户回复内容

        Returns:
            int: 1=同意生成工单, 2=不同意, 3=想修改
        """
        api_name = "意图判断接口 (workflow)"

        if not self.intent_api_url or not self.intent_api_key:
            _log_error(api_name, "接口未配置")
            logger.error(f"[{api_name}] 未配置")
            return 3  # 默认当作想修改

        headers = {
            "Authorization": f"Bearer {self.intent_api_key}",
            "Content-Type": "application/json"
        }

        # 输入参数是 decision
        payload = {
            "inputs": {
                "decision": query
            },
            "response_mode": "blocking",
            "user": user_id
        }

        _log_request(api_name, self.intent_api_url, headers, payload)

        try:
            resp = requests.post(
                self.intent_api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            resp.raise_for_status()

            result = resp.json()

            outputs = result.get('data', {}).get('outputs', {})
            intent = outputs.get('decision') or ""

            # 解析意图
            intent_desc = {1: "同意生成工单", 2: "不同意", 3: "想修改"}
            try:
                intent_value = int(str(intent).strip())
            except ValueError:
                intent_value = 3  # 解析失败默认当作想修改

            _log_response(api_name, result, f"意图={intent_value} ({intent_desc.get(intent_value, '未知')})")
            logger.info(f"[{api_name}] 返回 intent={intent_value} ({intent_desc.get(intent_value, '未知')})")

            return intent_value

        except Exception as e:
            _log_error(api_name, str(e))
            logger.error(f"[{api_name}] 失败: {e}")
            return 3  # 异常默认当作想修改
