# -*- coding: utf-8 -*-
"""
message_processor.py - 消息处理器
"""

import os
import json
import logging
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
import time

logger = logging.getLogger(__name__)

# AI返回的工单JSON必填字段
REQUIRED_FIELDS = {
    "title": "问题标题",
    "category": "问题分类",
    "priority": "优先级",
    "contact_name": "联系人姓名",
    "department": "所属部门",
    "contact_phone": "联系电话",
    "problem_desc": "问题描述"
}

# 可选字段（不需要验证）
OPTIONAL_FIELDS = ["tried_solutions", "impact_scope"]

# 文件保存目录
FILE_SAVE_DIR = "/root/ai_work_order/doc"

# 消息关联时间窗口（秒）
MESSAGE_LINK_WINDOW = 30


class MessageProcessor:
    """消息处理器"""

    def __init__(self, wechat_api, ai_client, user_manager, auth_manager):
        self.wechat_api = wechat_api
        self.ai_client = ai_client
        self.user_manager = user_manager
        self.auth_manager = auth_manager
        # 保存用户最近的文字消息 {userid: {"content": "xxx", "time": timestamp}}
        self._pending_text = {}
        # 保存待确认的工单数据 {userid: {"data": work_order_dict, "time": timestamp}}
        self._pending_work_orders = {}

    def _parse_ai_response(self, ai_reply):
        """解析AI返回的JSON数据

        Returns:
            tuple: (is_json, data_or_text)
                - 如果是有效JSON: (True, dict)
                - 如果不是JSON: (False, original_text)
        """
        try:
            # 尝试从回复中提取JSON
            text = ai_reply.strip()

            # 尝试直接解析
            if text.startswith('{'):
                data = json.loads(text)
                return True, data

            # 尝试从markdown代码块中提取
            if '```json' in text:
                start = text.find('```json') + 7
                end = text.find('```', start)
                if end > start:
                    json_str = text[start:end].strip()
                    data = json.loads(json_str)
                    return True, data

            # 尝试从普通代码块中提取
            if '```' in text:
                start = text.find('```') + 3
                end = text.find('```', start)
                if end > start:
                    json_str = text[start:end].strip()
                    if json_str.startswith('{'):
                        data = json.loads(json_str)
                        return True, data

            return False, ai_reply

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            return False, ai_reply

    def _validate_work_order(self, data):
        """验证工单数据的必填字段

        Returns:
            tuple: (is_valid, missing_fields)
                - is_valid: 是否所有必填字段都有值
                - missing_fields: 缺失的字段列表 [(field_key, field_name), ...]
        """
        missing_fields = []

        for field_key, field_name in REQUIRED_FIELDS.items():
            value = data.get(field_key, "")
            # 检查字段是否为空（None、空字符串、或只有空白）
            if not value or (isinstance(value, str) and not value.strip()):
                missing_fields.append((field_key, field_name))

        return len(missing_fields) == 0, missing_fields

    def _format_missing_fields_message(self, missing_fields):
        """格式化缺失字段的提示消息"""
        message = "请补充以下信息：\n\n"
        for i, (field_key, field_name) in enumerate(missing_fields, 1):
            message += f"{i}. {field_name}\n"
        message += "\n请直接回复需要补充的内容，我会继续为您处理。"
        return message

    def _format_work_order_confirm(self, data):
        """格式化工单确认消息"""
        message = f"标题：{data.get('title', '')}\n"
        message += f"分类：{data.get('category', '')}\n"
        message += f"优先级：{data.get('priority', '')}\n"
        message += f"联系人：{data.get('contact_name', '')}\n"
        message += f"部门：{data.get('department', '')}\n"
        message += f"电话：{data.get('contact_phone', '')}\n"
        message += f"问题描述：{data.get('problem_desc', '')}"

        # 可选字段
        if data.get('impact_scope'):
            message += f"\n影响范围：{data.get('impact_scope')}"
        if data.get('tried_solutions'):
            message += f"\n已尝试方案：{data.get('tried_solutions')}"

        return message

    def _save_pending_work_order(self, userid, work_order_data):
        """保存待确认的工单数据"""
        self._pending_work_orders[userid] = {
            "data": work_order_data,
            "time": time.time()
        }
        logger.info(f"保存待确认工单: userid={userid}")

    def _get_pending_work_order(self, userid):
        """获取用户待确认的工单数据（5分钟有效期）"""
        pending = self._pending_work_orders.get(userid)
        if pending:
            # 检查是否在5分钟内
            if time.time() - pending["time"] <= 300:
                return pending["data"]
            else:
                # 过期，清除
                del self._pending_work_orders[userid]
                logger.info(f"待确认工单已过期: userid={userid}")
        return None

    def _clear_pending_work_order(self, userid):
        """清除用户待确认的工单数据"""
        if userid in self._pending_work_orders:
            del self._pending_work_orders[userid]

    def _submit_work_order(self, userid, work_order_data, query):
        """提交工单到AI workflow接口

        Args:
            userid: 用户ID
            work_order_data: 完整的工单数据字典
            query: 用户回复内容

        Returns:
            tuple: (success, result_message)
        """
        logger.info(f"提交工单: userid={userid}, query={query}, 数据: {json.dumps(work_order_data, ensure_ascii=False)}")

        # 调用AI workflow接口，让大模型判断是否保存
        success, result = self.ai_client.submit_work_order(userid, work_order_data, query)

        return success, result

    def process(self, plain_xml):
        """处理消息入口"""
        try:
            # 打印原始XML便于调试
            logger.info(f"收到原始消息XML: {plain_xml}")

            root = ET.fromstring(plain_xml)

            msg_type = root.findtext("MsgType", "")
            from_user = root.findtext("FromUserName", "")
            content = root.findtext("Content", "")

            logger.info(f"收到消息: 用户={from_user}, 类型={msg_type}, 内容={content}")

            # 处理文本消息
            if msg_type == "text" and content:
                threading.Thread(
                    target=self._handle_message,
                    args=(from_user, content)
                ).start()
                return True

            # 处理非文本消息（图片、语音、视频、文件）
            if msg_type in ["image", "voice", "video", "file"]:
                media_id = root.findtext("MediaId", "")
                # 文件消息还有文件名
                filename = root.findtext("FileName", "")

                if media_id:
                    threading.Thread(
                        target=self._handle_file_message,
                        args=(from_user, msg_type, media_id, filename)
                    ).start()
                    return True

            return False

        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            return False

    def _handle_message(self, userid, content):
        """处理单条消息"""
        try:
            # 检查是否是图片关联消息（#开头）
            if content.startswith("#"):
                # 保存到pending，等待图片，不立即处理
                self._pending_text[userid] = {
                    "content": content[1:].strip(),  # 去掉#号
                    "time": time.time()
                }
                logger.info(f"收到图片关联消息，等待图片: {content}")
                return

            # 检查是否有待确认的工单
            pending_order = self._get_pending_work_order(userid)
            if pending_order:
                # 把用户回复传给AI，让大模型判断是否保存工单
                self._clear_pending_work_order(userid)

                success, result = self._submit_work_order(userid, pending_order, content)

                if success:
                    # 200：成功，清空会话上下文，告诉客户
                    self.ai_client.clear_conversation(userid)
                    logger.info(f"工单提交成功，已清空用户会话上下文: {userid}")
                    self.wechat_api.send_app_message(userid, "工单已生成")
                elif result == "600":
                    # 600：用户不同意，清空上下文，回复友好消息
                    self.ai_client.clear_conversation(userid)
                    logger.info(f"用户不同意生成工单，已清空上下文: {userid}")
                    self.wechat_api.send_app_message(userid, "好的，期待下次为您服务")
                else:
                    # 其他失败情况，打印日志
                    logger.error(f"工单提交异常: {result}, userid={userid}")
                return

            # 1. 检查用户是否已授权（数据库中有手机号）
            is_authorized, user_info = self.user_manager.check_user_authorized(userid)

            if not is_authorized:
                # 首次使用，保存消息并发送授权卡片
                self._send_auth_card(userid, content)
                return

            # 2. 获取用户上下文
            user_context = self.user_manager.get_user_context(userid)

            # 3. 打印用户信息（每次消息都显示）
            info_display = self.user_manager.format_user_info_for_display(user_context)
            print(info_display)

            # 4. 构建带用户信息的消息给AI
            message_with_context = self.user_manager.format_user_info_for_ai(user_context, content)

            # 5. 发送等待提示
            self.wechat_api.send_app_message(userid, "⏳ 正在处理中，请稍候...")

            # 6. 打印发送给AI的消息
            print("\n" + "*" * 60)
            print("*" + " " * 18 + ">>> 发送给AI的消息 <<<" + " " * 17 + "*")
            print("*" * 60)
            print(message_with_context)
            print("*" * 60 + "\n")

            # 7. 调用AI
            ai_reply = self.ai_client.chat(userid, message_with_context)

            # 8. 打印AI返回的回复
            print("\n" + "#" * 60)
            print("#" + " " * 18 + "<<< AI返回的回复 >>>" + " " * 19 + "#")
            print("#" * 60)
            print(ai_reply)
            print("#" * 60 + "\n")

            # 9. 解析AI返回的JSON数据并验证必填字段
            is_json, parsed_data = self._parse_ai_response(ai_reply)

            if is_json:
                # AI返回了JSON格式的工单数据
                logger.info(f"AI返回JSON数据: {json.dumps(parsed_data, ensure_ascii=False)}")

                # 验证必填字段
                is_valid, missing_fields = self._validate_work_order(parsed_data)

                if not is_valid:
                    # 有缺失字段，提示用户补充
                    missing_msg = self._format_missing_fields_message(missing_fields)
                    print("\n" + "!" * 60)
                    print(">>> 缺失字段提示 <<<")
                    print("!" * 60)
                    print(missing_msg)
                    print("!" * 60 + "\n")
                    self.wechat_api.send_app_message(userid, missing_msg)
                else:
                    # 所有必填字段完整，保存待确认工单并询问用户
                    self._save_pending_work_order(userid, parsed_data)

                    confirm_msg = self._format_work_order_confirm(parsed_data)
                    print("\n" + "+" * 60)
                    print(">>> 工单信息完整，等待用户确认 <<<")
                    print("+" * 60)
                    print(confirm_msg)
                    print("+" * 60 + "\n")

                    # 询问用户是否生成工单（附带上传链接）
                    upload_url = f"https://yjservicetest.ike-data.com/upload?userid={userid}"
                    ask_msg = f"{confirm_msg}\n是否生成工单？<a href='{upload_url}'>上传附件</a>"
                    self.wechat_api.send_app_message(userid, ask_msg)
            else:
                # AI返回的不是JSON格式，直接发送原始回复
                upload_url = f"https://yjservicetest.ike-data.com/upload?userid={userid}"
                reply_with_upload = f"{ai_reply} <a href='{upload_url}'>上传附件</a>"
                self.wechat_api.send_app_message(userid, reply_with_upload)

        except Exception as e:
            logger.error(f"处理消息异常: {e}")
            self.wechat_api.send_app_message(userid, "系统繁忙，请稍后重试")

    def _handle_file_message(self, userid, msg_type, media_id, original_filename=None):
        """处理文件消息（图片、语音、视频、文件）"""
        try:
            # 类型名称映射
            type_names = {
                "image": "图片",
                "voice": "语音",
                "video": "视频",
                "file": "文件"
            }
            type_name = type_names.get(msg_type, "文件")

            logger.info(f"开始处理{type_name}: userid={userid}, media_id={media_id}")

            # 下载文件
            file_content, filename = self.wechat_api.download_media(media_id)

            if not file_content:
                self.wechat_api.send_app_message(userid, f"{type_name}下载失败，请重试")
                return

            # 使用原始文件名（如果有）
            if original_filename:
                filename = original_filename

            # 图片类型：发送给AI处理
            if msg_type == "image":
                # 处理图片文件名，避免乱码
                filename = self._get_image_filename(filename)
                self._handle_image_with_ai(userid, file_content, filename)
                return

            # 其他文件类型：保存到目录
            # 确保目录存在
            os.makedirs(FILE_SAVE_DIR, exist_ok=True)

            # 生成唯一文件名（避免重复）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name, ext = os.path.splitext(filename) if filename else ("file", "")
            save_filename = f"{userid}_{timestamp}_{name}{ext}"
            save_path = os.path.join(FILE_SAVE_DIR, save_filename)

            # 保存文件
            with open(save_path, "wb") as f:
                f.write(file_content)

            logger.info(f"{type_name}已保存: {save_path}")

            # 通知用户
            self.wechat_api.send_app_message(
                userid,
                f"{type_name}已接收\n文件名: {filename}\n大小: {len(file_content) / 1024:.1f} KB"
            )

        except Exception as e:
            logger.error(f"处理{msg_type}消息异常: {e}")
            self.wechat_api.send_app_message(userid, "文件处理失败，请重试")

    def _get_image_filename(self, original_filename):
        """处理图片文件名，避免乱码"""
        # 生成默认文件名：img_时间戳.png
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"img_{timestamp}.png"

        if not original_filename:
            return default_name

        # 检查是否是乱码（包含非ASCII且非中文字符）
        try:
            # 尝试判断是否是正常的文件名
            name, ext = os.path.splitext(original_filename)
            # 如果扩展名正常，保留扩展名
            if ext.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                # 检查文件名部分是否有乱码
                try:
                    name.encode('utf-8').decode('utf-8')
                    # 如果文件名太短或看起来像乱码，用默认名
                    if len(name) < 2 or name.startswith('~'):
                        return f"img_{timestamp}{ext}"
                    return original_filename
                except:
                    return f"img_{timestamp}{ext}"
            else:
                return default_name
        except:
            return default_name

    def _get_pending_text(self, userid):
        """获取用户最近的文字消息（30秒内）"""
        pending = self._pending_text.get(userid)
        if pending:
            # 检查是否在时间窗口内
            if time.time() - pending["time"] <= MESSAGE_LINK_WINDOW:
                # 清除pending，避免重复使用
                del self._pending_text[userid]
                return pending["content"]
            else:
                # 过期，清除
                del self._pending_text[userid]
        return None

    def _handle_image_with_ai(self, userid, image_data, filename):
        """处理图片消息，发送给AI解析"""
        try:
            # 1. 检查用户是否已授权
            is_authorized, user_info = self.user_manager.check_user_authorized(userid)

            if not is_authorized:
                # 未授权，发送授权卡片
                self._send_auth_card(userid)
                return

            # 2. 检查是否有关联的文字消息
            linked_text = self._get_pending_text(userid)

            # 3. 发送等待提示
            self.wechat_api.send_app_message(userid, "⏳ 正在解析图片，请稍候...")

            # 4. 上传图片到AI
            file_id = self.ai_client.upload_image(image_data, filename, userid)
            if not file_id:
                self.wechat_api.send_app_message(userid, "图片上传失败，请重试")
                return

            # 5. 打印图片信息
            print("\n" + "*" * 60)
            print("*" + " " * 16 + ">>> 处理图片消息 <<<" + " " * 17 + "*")
            print("*" * 60)
            print(f"图片文件: {filename}")
            print(f"文件ID: {file_id}")
            print(f"关联文字: {linked_text if linked_text else '(无)'}")
            print("*" * 60 + "\n")

            # 6. 调用图片解析接口（workflow），得到图片描述文本
            image_text = self.ai_client.analyze_image(userid, file_id, linked_text)

            print("\n" + "-" * 60)
            print(">>> 图片解析结果 <<<")
            print("-" * 60)
            print(image_text)
            print("-" * 60 + "\n")

            if not image_text or "服务" in image_text and "不可用" in image_text:
                self.wechat_api.send_app_message(userid, "图片解析失败，请重试")
                return

            # 9. 将图片描述+用户文字一起发给聊天AI
            # 构建完整消息
            if linked_text:
                full_message = f"[图片内容] {image_text}\n[用户问题] {linked_text}"
            else:
                full_message = f"[图片内容] {image_text}"

            # 加上用户身份信息
            user_context = self.user_manager.get_user_context(userid)
            message_with_context = self.user_manager.format_user_info_for_ai(user_context, full_message)

            # 调用聊天AI
            ai_reply = self.ai_client.chat(userid, message_with_context)

            # 10. 打印AI返回的回复
            print("\n" + "#" * 60)
            print("#" + " " * 18 + "<<< AI返回的回复 >>>" + " " * 19 + "#")
            print("#" * 60)
            print(ai_reply)
            print("#" * 60 + "\n")

            # 11. 解析AI返回的JSON数据并验证必填字段
            is_json, parsed_data = self._parse_ai_response(ai_reply)

            if is_json:
                # AI返回了JSON格式的工单数据
                logger.info(f"AI返回JSON数据: {json.dumps(parsed_data, ensure_ascii=False)}")

                # 验证必填字段
                is_valid, missing_fields = self._validate_work_order(parsed_data)

                if not is_valid:
                    # 有缺失字段，提示用户补充
                    missing_msg = self._format_missing_fields_message(missing_fields)
                    print("\n" + "!" * 60)
                    print(">>> 缺失字段提示 <<<")
                    print("!" * 60)
                    print(missing_msg)
                    print("!" * 60 + "\n")
                    self.wechat_api.send_app_message(userid, missing_msg)
                else:
                    # 所有必填字段完整，保存待确认工单并询问用户
                    self._save_pending_work_order(userid, parsed_data)

                    confirm_msg = self._format_work_order_confirm(parsed_data)
                    print("\n" + "+" * 60)
                    print(">>> 工单信息完整，等待用户确认 <<<")
                    print("+" * 60)
                    print(confirm_msg)
                    print("+" * 60 + "\n")

                    # 询问用户是否生成工单（附带上传链接）
                    upload_url = f"https://yjservicetest.ike-data.com/upload?userid={userid}"
                    ask_msg = f"{confirm_msg}\n是否生成工单？<a href='{upload_url}'>上传附件</a>"
                    self.wechat_api.send_app_message(userid, ask_msg)
            else:
                # AI返回的不是JSON格式，直接发送原始回复
                upload_url = f"https://yjservicetest.ike-data.com/upload?userid={userid}"
                reply_with_upload = f"{ai_reply} <a href='{upload_url}'>上传附件</a>"
                self.wechat_api.send_app_message(userid, reply_with_upload)

        except Exception as e:
            logger.error(f"处理图片消息异常: {e}")
            self.wechat_api.send_app_message(userid, "图片处理失败，请重试")

    def _send_auth_card(self, userid, original_message=None):
        """发送授权卡片，并保存用户原始消息"""
        auth_url = self.auth_manager.generate_auth_url(userid)

        if auth_url:
            # 保存用户原始消息，授权成功后自动处理
            if original_message:
                self.auth_manager.save_pending_message(userid, original_message)
            # 使用简洁的markdown链接格式
            message = self.auth_manager.render_auth_card_message(auth_url)
        else:
            message = "系统错误，请稍后重试"

        self.wechat_api.send_app_message(userid, message)