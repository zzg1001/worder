# -*- coding: utf-8 -*-
"""
message_processor.py - 消息处理器
"""

import os
import logging
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
import time

logger = logging.getLogger(__name__)

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

            # 9. 发送回复（附带上传链接，带用户ID）
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
                self.wechat_api.send_app_message(userid, f"❌ {type_name}下载失败，请重试")
                return

            # 使用原始文件名（如果有）
            if original_filename:
                filename = original_filename

            # 图片类型：发送给AI处理
            if msg_type == "image":
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
                f"✅ {type_name}已接收\n📁 文件名: {filename}\n💾 大小: {len(file_content) / 1024:.1f} KB"
            )

        except Exception as e:
            logger.error(f"处理{msg_type}消息异常: {e}")
            self.wechat_api.send_app_message(userid, "❌ 文件处理失败，请重试")

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
                self.wechat_api.send_app_message(userid, "❌ 图片上传失败，请重试")
                return

            # 5. 获取用户上下文
            user_context = self.user_manager.get_user_context(userid)

            # 6. 构建消息（有关联文字就用关联文字，没有就空）
            user_message = linked_text if linked_text else ""
            message_with_context = self.user_manager.format_user_info_for_ai(
                user_context,
                user_message
            ) if user_message else ""

            # 7. 打印发送给AI的消息
            print("\n" + "*" * 60)
            print("*" + " " * 16 + ">>> 发送给AI的图片消息 <<<" + " " * 15 + "*")
            print("*" * 60)
            print(f"图片文件: {filename}")
            print(f"文件ID: {file_id}")
            print(f"关联文字: {linked_text if linked_text else '(无)'}")
            if message_with_context:
                print(message_with_context)
            print("*" * 60 + "\n")

            # 8. 调用AI（带图片）
            files = [{
                "type": "image",
                "transfer_method": "local_file",
                "upload_file_id": file_id
            }]
            # 如果没有文字，query传空字符串
            query = message_with_context if message_with_context else ""
            ai_reply = self.ai_client.chat(userid, query, files=files)

            # 9. 打印AI返回的回复
            print("\n" + "#" * 60)
            print("#" + " " * 18 + "<<< AI返回的回复 >>>" + " " * 19 + "#")
            print("#" * 60)
            print(ai_reply)
            print("#" * 60 + "\n")

            # 10. 发送回复（附带上传链接）
            upload_url = f"https://yjservicetest.ike-data.com/upload?userid={userid}"
            reply_with_upload = f"{ai_reply} <a href='{upload_url}'>上传附件</a>"
            self.wechat_api.send_app_message(userid, reply_with_upload)

        except Exception as e:
            logger.error(f"处理图片消息异常: {e}")
            self.wechat_api.send_app_message(userid, "❌ 图片处理失败，请重试")

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