# -*- coding: utf-8 -*-
"""
user_manager.py - 用户管理模块
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class UserManager:
    """用户管理器"""

    def __init__(self, wechat_api, db_manager):
        self.wechat_api = wechat_api
        self.db = db_manager

    def check_user_authorized(self, userid):
        """检查用户是否已授权（数据库中是否存在且有效）"""
        user = self.db.get_user(userid)
        if user and user.get('mobile'):
            self.db.update_last_active(userid)
            return True, user
        return False, None

    def get_and_save_user_info(self, userid, mobile):
        """
        从企微API获取用户信息并保存（姓名、部门、职位等）
        mobile从OAuth授权获取
        """
        # 1. 获取用户基本信息（含部门ID）
        user_info = self.wechat_api.get_user_info(userid)
        if not user_info or user_info.get('errcode') != 0:
            logger.error(f"获取用户信息失败: {userid}")
            return None

        # 2. 获取部门名称
        dept_names = []
        dept_ids = user_info.get('department', [])
        logger.info(f"用户 {userid} 部门ID: {dept_ids}")

        if dept_ids:
            # 获取部门列表
            dept_list = self.wechat_api.get_department_list()
            logger.info(f"部门列表: {dept_list}")
            for dept_id in dept_ids:
                if dept_id in dept_list:
                    dept_names.append(dept_list[dept_id])
            logger.info(f"用户 {userid} 部门名称: {dept_names}")

        # 3. 组装数据
        user_data = {
            'userid': userid,
            'name': user_info.get('name', ''),
            'mobile': mobile,  # 从OAuth获取的手机号
            'department': ','.join(map(str, dept_ids)) if dept_ids else '',
            'department_names': ','.join(dept_names) if dept_names else '',
            'position': user_info.get('position', ''),
            'email': user_info.get('email', ''),
            'avatar': user_info.get('avatar', ''),
            'gender': user_info.get('gender', 0),
            'auth_time': datetime.now(),
            'last_active_time': datetime.now()
        }

        # 4. 保存到数据库
        success = self.db.save_user(user_data)
        return user_data if success else None

    def get_user_context(self, userid):
        """获取用户上下文信息（用于AI对话）"""
        user = self.db.get_user(userid)

        if not user:
            return None

        return {
            'userid': user['userid'],
            'name': user['name'],
            'mobile': user['mobile'],
            'department': user.get('department_names', '')
        }

    def format_user_info_for_display(self, user_context):
        """格式化用户信息用于显示"""
        if not user_context:
            return "【未获取用户信息】"

        lines = [
            "=" * 60,
            "【用户身份信息】",
            "=" * 60,
            f"  姓名: {user_context['name']}",
            f"  手机号: {user_context['mobile']}",
            f"  部门: {user_context.get('department', '') or '未知'}",
            "=" * 60
        ]
        return "\n".join(lines)

    def format_user_info_for_ai(self, user_context, message):
        """格式化用户信息给AI"""
        if not user_context:
            return message

        dept = user_context.get('department', '') or '未知'
        identity = f"[用户身份] 姓名:{user_context['name']} 手机号:{user_context['mobile']} 部门:{dept}"

        return f"{identity}\n[用户消息] {message}"