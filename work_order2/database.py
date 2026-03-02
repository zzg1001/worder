# -*- coding: utf-8 -*-
"""
database.py - 数据库管理模块
"""

import logging
import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_config):
        self.db_config = db_config
        self._init_tables()

    @contextmanager
    def _get_connection(self):
        """获取数据库连接"""
        conn = None
        try:
            conn = pymysql.connect(**self.db_config)
            yield conn
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def _init_tables(self):
        """初始化数据表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS wx_users (
            id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增ID',
            userid VARCHAR(64) NOT NULL UNIQUE COMMENT '企业微信用户ID',
            name VARCHAR(64) NOT NULL COMMENT '用户姓名',
            mobile VARCHAR(20) NOT NULL COMMENT '手机号',
            department VARCHAR(255) DEFAULT '' COMMENT '部门ID列表',
            department_names VARCHAR(500) DEFAULT '' COMMENT '部门名称列表',
            position VARCHAR(128) DEFAULT '' COMMENT '职位',
            email VARCHAR(128) DEFAULT '' COMMENT '邮箱',
            avatar VARCHAR(500) DEFAULT '' COMMENT '头像URL',
            gender TINYINT DEFAULT 0 COMMENT '性别',
            status TINYINT DEFAULT 1 COMMENT '状态',
            auth_time DATETIME NOT NULL COMMENT '首次授权时间',
            last_active_time DATETIME NOT NULL COMMENT '最后活跃时间',
            update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            INDEX idx_mobile (mobile),
            INDEX idx_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='企业微信用户表';
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(create_table_sql)
                    conn.commit()
                    logger.info("数据库表初始化完成")
        except Exception as e:
            logger.error(f"初始化数据表失败: {e}")
            raise

    def save_user(self, user_data):
        """保存或更新用户信息"""
        sql = """
        INSERT INTO wx_users (
            userid, name, mobile, department, department_names, 
            position, email, avatar, gender, auth_time, last_active_time
        ) VALUES (
            %(userid)s, %(name)s, %(mobile)s, %(department)s, %(department_names)s,
            %(position)s, %(email)s, %(avatar)s, %(gender)s, %(auth_time)s, %(last_active_time)s
        ) ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            mobile = VALUES(mobile),
            department = VALUES(department),
            department_names = VALUES(department_names),
            position = VALUES(position),
            email = VALUES(email),
            avatar = VALUES(avatar),
            gender = VALUES(gender),
            last_active_time = VALUES(last_active_time),
            status = 1
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, user_data)
                    conn.commit()
                    logger.info(f"用户 {user_data['userid']} 信息已保存")
                    return True
        except Exception as e:
            logger.error(f"保存用户信息失败: {e}")
            return False

    def get_user(self, userid):
        """根据userid获取用户信息"""
        sql = "SELECT * FROM wx_users WHERE userid = %s AND status = 1"

        try:
            with self._get_connection() as conn:
                with conn.cursor(DictCursor) as cursor:
                    cursor.execute(sql, (userid,))
                    return cursor.fetchone()
        except Exception as e:
            logger.error(f"查询用户信息失败: {e}")
            return None

    def update_last_active(self, userid):
        """更新用户最后活跃时间"""
        sql = "UPDATE wx_users SET last_active_time = NOW() WHERE userid = %s"

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(sql, (userid,))
                    conn.commit()
        except Exception as e:
            logger.error(f"更新活跃时间失败: {e}")