# -*- coding: utf-8 -*-
"""
main.py - 主服务入口（双端口）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import logging
import threading
from datetime import datetime
from flask import Flask, request, make_response, jsonify

from config import (
    CORP_ID, CORP_SECRET, CONTACTS_SECRET, TOKEN, ENCODING_AES_KEY, AGENT_ID,
    AI_API_URL, AI_API_KEY, IMAGE_AI_API_URL, IMAGE_AI_API_KEY,
    WORK_ORDER_API_URL, WORK_ORDER_API_KEY,
    INTENT_API_URL, INTENT_API_KEY,
    OAUTH_SIGN_KEY, OAUTH_REDIRECT_URI,
    MAIN_PORT, OAUTH_PORT, DB_CONFIG,
    TICKET_MONITOR_ENABLED, TICKET_MONITOR_INTERVAL
)

from wechat_crypto import WXBizMsgCrypt
from wechat_api import WeChatAPI
from database import DatabaseManager
from user_manager import UserManager
from auth_manager import AuthManager
from ai_client import AIClient
from message_processor import MessageProcessor
from oauth_processor import OAuthProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化共享组件
db_manager = DatabaseManager(DB_CONFIG)
wechat_api = WeChatAPI(CORP_ID, CORP_SECRET, AGENT_ID, CONTACTS_SECRET)
user_manager = UserManager(wechat_api, db_manager)
auth_manager = AuthManager(OAUTH_SIGN_KEY, OAUTH_REDIRECT_URI, AGENT_ID, CORP_ID)
ai_client = AIClient(AI_API_URL, AI_API_KEY, IMAGE_AI_API_URL, IMAGE_AI_API_KEY,
                     WORK_ORDER_API_URL, WORK_ORDER_API_KEY,
                     INTENT_API_URL, INTENT_API_KEY)

# ========== 主服务（8091） ==========
main_app = Flask('main_app')
wxcpt = WXBizMsgCrypt(TOKEN, ENCODING_AES_KEY, CORP_ID)
message_processor = MessageProcessor(wechat_api, ai_client, user_manager, auth_manager)


@main_app.route("/yjcallback", methods=["GET", "POST"])
def main_callback():
    """企微消息回调"""
    sig = request.args.get("msg_signature", "")
    ts = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")

    logger.info(f"[主服务] 请求: method={request.method}")

    if request.method == "GET":
        echo_str = request.args.get("echostr", "")
        if not echo_str:
            return "缺少echostr", 400

        try:
            result = wxcpt.verify_url(sig, ts, nonce, echo_str)
            logger.info("[主服务] URL验证成功")
            return make_response(result)
        except Exception as e:
            logger.error(f"[主服务] 验证失败: {e}")
            return make_response(echo_str)

    try:
        raw_data = request.data
        if not raw_data:
            return make_response("success")

        plain_xml = wxcpt.decrypt_msg(sig, ts, nonce, raw_data)
        logger.info(f"[主服务] 解密成功")

        message_processor.process(plain_xml)
        return make_response("success")

    except Exception as e:
        logger.exception("[主服务] 处理失败")
        return make_response("success")


@main_app.route("/health", methods=["GET"])
def main_health():
    return {"service": "main", "port": MAIN_PORT, "status": "running"}, 200


# ========== OAuth服务（8092） ==========
oauth_app = Flask('oauth_app')
oauth_processor = OAuthProcessor(wechat_api, auth_manager, user_manager, ai_client)


@oauth_app.route("/oauth_callback", methods=["GET"])
def oauth_callback():
    """OAuth回调"""
    code = request.args.get('code', '')
    state = request.args.get('state', '')

    logger.info(f"[OAuth] 回调: code={code[:10]}****")

    if not code:
        return auth_manager.render_error_page("缺少code参数"), 400

    return oauth_processor.handle(code, state)

# 文件保存目录
FILE_SAVE_DIR = "/root/ai_work_order/doc"

@oauth_app.route("/jsapi_signature", methods=["GET"])
def jsapi_signature():
    """获取JSSDK签名"""
    url = request.args.get('url', '')
    if not url:
        return jsonify({"error": "缺少url参数"}), 400

    sign_data = wechat_api.get_jsapi_signature(url)
    if sign_data:
        return jsonify(sign_data)
    else:
        return jsonify({"error": "获取签名失败"}), 500

@oauth_app.route("/upload", methods=["GET"])
def upload_page():
    """文件上传页面 - 支持从聊天记录选择文件"""
    return f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>上传文件</title>
        <script src="https://res.wx.qq.com/wwopen/js/jsapi/jweixin-1.0.0.js"></script>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #f5f5f5;
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                background: white;
                padding: 25px;
                border-radius: 12px;
                box-shadow: 0 2px 20px rgba(0,0,0,0.1);
                max-width: 400px;
                margin: 0 auto;
            }}
            h1 {{ font-size: 18px; color: #333; margin-bottom: 20px; text-align: center; }}
            .btn-group {{ display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px; }}
            .btn {{
                width: 100%;
                padding: 16px;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }}
            .btn-primary {{ background: #07c160; color: white; }}
            .btn-primary:active {{ background: #06ad56; }}
            .btn-secondary {{ background: #f5f5f5; color: #333; border: 1px solid #ddd; }}
            .btn-secondary:active {{ background: #eee; }}
            .btn:disabled {{ background: #ccc; color: #999; }}
            .file-list {{
                background: #f9f9f9;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 15px;
                display: none;
            }}
            .file-item {{
                display: flex;
                align-items: center;
                padding: 8px 0;
                border-bottom: 1px solid #eee;
            }}
            .file-item:last-child {{ border-bottom: none; }}
            .file-item .icon {{ font-size: 24px; margin-right: 10px; }}
            .file-item .info {{ flex: 1; }}
            .file-item .name {{ font-size: 14px; color: #333; word-break: break-all; }}
            .file-item .size {{ font-size: 12px; color: #999; }}
            .status {{
                padding: 12px;
                border-radius: 6px;
                text-align: center;
                display: none;
            }}
            .status.success {{ background: #f0fff4; color: #07c160; }}
            .status.error {{ background: #fff0f0; color: #f00; }}
            .status.info {{ background: #f0f7ff; color: #1890ff; }}
            .tips {{
                margin-top: 20px;
                padding: 12px;
                background: #fffbe6;
                border-radius: 6px;
                font-size: 13px;
                color: #666;
            }}
            .tips p {{ margin-bottom: 5px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📁 上传文件</h1>

            <div class="btn-group" id="btnGroup" style="display:none">
                <button class="btn btn-primary" id="btnChatFile" onclick="chooseChatFile()">
                    💬 重新选择文件
                </button>
                <button class="btn btn-secondary" id="btnLocalFile" onclick="document.getElementById('fileInput').click()">
                    📂 从本地选择
                </button>
            </div>

            <input type="file" id="fileInput" style="display:none" onchange="handleLocalFile(this)">

            <div class="file-list" id="fileList"></div>

            <button class="btn btn-primary" id="btnUpload" style="display:none" onclick="uploadFiles()">
                ⬆️ 确认上传
            </button>

            <div class="status" id="status"></div>

            <div class="tips">
                <p>💡 <strong>从聊天记录选择</strong>：可直接选择转发给你的文件</p>
                <p>💡 <strong>从本地选择</strong>：选择手机/电脑上的文件</p>
            </div>
        </div>

        <script>
            const AGENT_ID = '{AGENT_ID}';
            let filesToUpload = [];
            let wxReady = false;

            // 初始化JSSDK
            async function initWxSDK() {{
                try {{
                    showStatus('正在初始化...', 'info');
                    const signUrl = '/jsapi_signature?url=' + encodeURIComponent(location.href.split('#')[0]);
                    console.log('请求签名:', signUrl);

                    const resp = await fetch(signUrl);
                    const config = await resp.json();
                    console.log('签名结果:', config);

                    if (config.error) {{
                        showStatus('初始化失败: ' + config.error, 'error');
                        console.error('获取签名失败:', config.error);
                        return;
                    }}

                    wx.config({{
                        beta: true,
                        debug: false,
                        appId: config.appId,
                        timestamp: config.timestamp,
                        nonceStr: config.nonceStr,
                        signature: config.signature,
                        jsApiList: ['chooseMessageFile']
                    }});

                    wx.agentConfig({{
                        corpid: config.appId,
                        agentid: config.agentId,
                        timestamp: config.timestamp,
                        nonceStr: config.nonceStr,
                        signature: config.agentSignature,
                        jsApiList: ['chooseMessageFile'],
                        success: function(res) {{
                            console.log('agentConfig success');
                            wxReady = true;
                            document.getElementById('status').style.display = 'none';
                            // 自动打开文件选择
                            setTimeout(function() {{
                                chooseChatFile();
                            }}, 300);
                        }},
                        fail: function(res) {{
                            console.error('agentConfig fail:', res);
                            if (res.errMsg) {{
                                showStatus('应用配置失败: ' + res.errMsg, 'error');
                            }}
                        }}
                    }});

                    wx.ready(function() {{
                        console.log('wx.config ready, waiting for agentConfig...');
                    }});

                    wx.error(function(res) {{
                        console.error('wx.config error:', res);
                        showStatus('配置错误: ' + (res.errMsg || JSON.stringify(res)), 'error');
                    }});
                }} catch (e) {{
                    console.error('初始化JSSDK失败:', e);
                    showStatus('初始化异常: ' + e.message, 'error');
                }}
            }}

            // 从聊天记录选择文件
            function chooseChatFile() {{
                console.log('chooseChatFile called, wxReady:', wxReady);

                if (!wxReady) {{
                    showStatus('正在初始化，请稍后再试...', 'info');
                    return;
                }}

                showStatus('正在打开文件选择...', 'info');

                // 尝试使用 ww.chooseMessageFile（企业微信专用）
                if (typeof ww !== 'undefined' && ww.chooseMessageFile) {{
                    ww.chooseMessageFile({{
                        count: 5,
                        type: 'file',
                        success: function(res) {{
                            console.log('ww.chooseMessageFile success:', res);
                            handleChatFiles(res.tempFiles || []);
                        }},
                        fail: function(res) {{
                            console.log('ww.chooseMessageFile fail:', res);
                            showStatus('选择失败: ' + (res.errMsg || JSON.stringify(res)), 'error');
                            showButtons();
                        }}
                    }});
                }} else {{
                    // 使用 wx.invoke 方式
                    wx.invoke('chooseMessageFile', {{
                        count: 5,
                        type: 'file'  // 只选择文件类型
                    }}, function(res) {{
                        console.log('chooseMessageFile result:', res);

                        if (res.err_msg === 'chooseMessageFile:ok') {{
                            handleChatFiles(res.tempFiles || []);
                        }} else if (res.err_msg === 'chooseMessageFile:cancel') {{
                            document.getElementById('status').style.display = 'none';
                            showButtons();
                        }} else {{
                            showStatus('选择失败: ' + res.err_msg, 'error');
                            showButtons();
                        }}
                    }});
                }}
            }}

            function handleChatFiles(files) {{
                files.forEach(f => {{
                    filesToUpload.push({{
                        name: f.name,
                        size: f.size,
                        path: f.tempFilePath,
                        type: 'chat'
                    }});
                }});
                renderFileList();
                document.getElementById('status').style.display = 'none';
                document.getElementById('btnGroup').style.display = 'flex';
            }}

            function showButtons() {{
                document.getElementById('btnGroup').style.display = 'flex';
            }}

            // 处理本地文件选择
            function handleLocalFile(input) {{
                const files = input.files;
                for (let i = 0; i < files.length; i++) {{
                    filesToUpload.push({{
                        name: files[i].name,
                        size: files[i].size,
                        file: files[i],
                        type: 'local'
                    }});
                }}
                renderFileList();
                input.value = '';
            }}

            // 渲染文件列表
            function renderFileList() {{
                const list = document.getElementById('fileList');
                const uploadBtn = document.getElementById('btnUpload');

                if (filesToUpload.length === 0) {{
                    list.style.display = 'none';
                    uploadBtn.style.display = 'none';
                    return;
                }}

                list.innerHTML = filesToUpload.map((f, i) => `
                    <div class="file-item">
                        <span class="icon">${{getFileIcon(f.name)}}</span>
                        <div class="info">
                            <div class="name">${{f.name}}</div>
                            <div class="size">${{formatSize(f.size)}}</div>
                        </div>
                    </div>
                `).join('');

                list.style.display = 'block';
                uploadBtn.style.display = 'block';
            }}

            // 获取文件图标
            function getFileIcon(name) {{
                const ext = name.split('.').pop().toLowerCase();
                const icons = {{
                    'pdf': '📕', 'doc': '📘', 'docx': '📘',
                    'xls': '📗', 'xlsx': '📗', 'ppt': '📙', 'pptx': '📙',
                    'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️',
                    'mp4': '🎬', 'mp3': '🎵', 'zip': '📦', 'rar': '📦',
                    'txt': '📝', 'py': '🐍', 'js': '📜', 'html': '🌐'
                }};
                return icons[ext] || '📄';
            }}

            // 格式化文件大小
            function formatSize(bytes) {{
                if (bytes < 1024) return bytes + ' B';
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
                return (bytes / 1024 / 1024).toFixed(1) + ' MB';
            }}

            // 获取URL参数中的userid
            function getUserId() {{
                const params = new URLSearchParams(window.location.search);
                return params.get('userid') || '';
            }}
            const currentUserId = getUserId();

            // 上传文件
            async function uploadFiles() {{
                if (filesToUpload.length === 0) return;

                const uploadBtn = document.getElementById('btnUpload');
                uploadBtn.disabled = true;
                uploadBtn.innerHTML = '⏳ 上传中...';

                let successCount = 0;
                let failCount = 0;

                for (const f of filesToUpload) {{
                    try {{
                        const formData = new FormData();
                        formData.append('userid', currentUserId);

                        if (f.type === 'local') {{
                            formData.append('file', f.file);
                        }} else {{
                            // 聊天文件需要先获取blob
                            const resp = await fetch(f.path);
                            const blob = await resp.blob();
                            formData.append('file', blob, f.name);
                        }}

                        const result = await fetch('/upload', {{
                            method: 'POST',
                            body: formData
                        }});
                        const data = await result.json();

                        if (data.success) {{
                            successCount++;
                        }} else {{
                            failCount++;
                        }}
                    }} catch (e) {{
                        console.error('上传失败:', e);
                        failCount++;
                    }}
                }}

                if (failCount === 0) {{
                    showStatus(`✅ 全部上传成功！共 ${{successCount}} 个文件`, 'success');
                    setTimeout(() => {{
                        if (window.WeixinJSBridge) {{
                            WeixinJSBridge.call('closeWindow');
                        }} else {{
                            window.close();
                        }}
                    }}, 1500);
                }} else {{
                    showStatus(`上传完成：成功 ${{successCount}} 个，失败 ${{failCount}} 个`, 'error');
                    uploadBtn.disabled = false;
                    uploadBtn.innerHTML = '⬆️ 重新上传';
                }}
            }}

            function showStatus(msg, type) {{
                const status = document.getElementById('status');
                status.textContent = msg;
                status.className = 'status ' + type;
                status.style.display = 'block';
            }}

            // 页面加载时初始化
            initWxSDK();
        </script>
    </body>
    </html>
    """

@oauth_app.route("/upload", methods=["POST"])
def upload_file():
    """文件上传接口"""
    try:
        # 获取用户ID
        userid = request.form.get('userid') or request.args.get('userid', '')

        if 'file' not in request.files:
            return jsonify({"success": False, "error": "没有选择文件"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "文件名为空"}), 400

        # 确保目录存在
        os.makedirs(FILE_SAVE_DIR, exist_ok=True)

        # 生成唯一文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_name = file.filename
        name, ext = os.path.splitext(original_name)
        save_filename = f"{userid}_{timestamp}_{name}{ext}" if userid else f"{timestamp}_{name}{ext}"
        save_path = os.path.join(FILE_SAVE_DIR, save_filename)

        # 保存文件
        file.save(save_path)
        file_size = os.path.getsize(save_path)

        logger.info(f"文件上传成功: {save_path}, 用户: {userid}")

        # 发送消息通知用户
        if userid:
            size_str = f"{file_size / 1024:.1f}KB" if file_size < 1024 * 1024 else f"{file_size / 1024 / 1024:.1f}MB"
            wechat_api.send_app_message(userid, f"文件上传成功\n文件名: {original_name}\n大小: {size_str}")

        return jsonify({
            "success": True,
            "filename": original_name,
            "saved_as": save_filename
        })

    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ========== 工单服务（整合 httpServer.py） ==========
import pymysql
from contextlib import contextmanager

# 工单数据库配置
TICKET_DB_CONFIG = {
    'host': '8.153.198.194',
    'port': 63306,
    'user': 'wx_qa',
    'password': 'cKXF45BLSHW68ynk',
    'database': 'wx_qa',
    'charset': 'utf8mb4'
}

@contextmanager
def get_ticket_db():
    conn = pymysql.connect(**TICKET_DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()

def parse_ticket_data(data):
    """兼容多种输入格式"""
    ticket_data = None

    if isinstance(data, dict) and 'ticket_json' in data:
        try:
            ticket_data = json.loads(data['ticket_json'])
        except:
            pass

    if ticket_data is None and isinstance(data, dict) and 'text' in data:
        try:
            ticket_data = json.loads(data['text'])
        except:
            pass

    if ticket_data is None and isinstance(data, dict) and 'title' in data:
        ticket_data = data

    if ticket_data is None:
        try:
            if isinstance(data, str):
                ticket_data = json.loads(data)
        except:
            pass

    return ticket_data

@oauth_app.route('/insert_ticket', methods=['POST'])
def insert_ticket():
    """工单创建接口"""
    try:
        data = request.get_json()

        print(f"\n[工单接口] 收到请求: {json.dumps(data, ensure_ascii=False)[:500]}")

        if not data:
            raw_body = request.get_data(as_text=True)
            try:
                data = json.loads(raw_body)
            except:
                return jsonify({"success": False, "message": "无法解析请求体"}), 400

        ticket_data = parse_ticket_data(data)

        if ticket_data is None:
            return jsonify({
                "success": False,
                "message": "无法解析 ticket 数据",
                "received": data
            }), 400

        print(f"[工单接口] 解析后数据: {json.dumps(ticket_data, ensure_ascii=False)[:500]}")

        required_fields = ['title', 'category', 'priority', 'contact_name']
        missing = [f for f in required_fields if not ticket_data.get(f)]
        if missing:
            return jsonify({
                "success": False,
                "message": f"缺少必填字段: {', '.join(missing)}"
            }), 400

        sql = """INSERT INTO tickets
        (title, category, priority, contact_name, department, contact_phone,
         problem_desc, impact_scope, tried_solutions, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '待处理')"""

        params = (
            ticket_data.get('title'),
            ticket_data.get('category'),
            ticket_data.get('priority'),
            ticket_data.get('contact_name'),
            ticket_data.get('department') or None,
            ticket_data.get('contact_phone') or None,
            ticket_data.get('problem_desc'),
            ticket_data.get('impact_scope'),
            ticket_data.get('tried_solutions')
        )

        with get_ticket_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                ticket_id = cursor.lastrowid
                conn.commit()

        print(f"[工单接口] 创建成功: ID={ticket_id}")
        return jsonify({
            "success": True,
            "ticket_id": ticket_id,
            "message": f"工单创建成功，ID: {ticket_id}"
        })

    except Exception as e:
        import traceback
        print(f"[工单接口] 错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"success": False, "message": f"服务器错误: {str(e)}"}), 500

@oauth_app.route('/insert_ticket_raw', methods=['POST'])
def insert_ticket_raw():
    """备用接口：直接接收原始 JSON 字符串"""
    try:
        raw_body = request.get_data(as_text=True)

        try:
            ticket_data = json.loads(raw_body)
        except json.JSONDecodeError as e:
            return jsonify({"success": False, "message": f"JSON解析失败: {str(e)}"}), 400

        required_fields = ['title', 'category', 'priority', 'contact_name']
        missing = [f for f in required_fields if not ticket_data.get(f)]
        if missing:
            return jsonify({"success": False, "message": f"缺少必填字段: {', '.join(missing)}"}), 400

        sql = """INSERT INTO tickets
        (title, category, priority, contact_name, department, contact_phone,
         problem_desc, impact_scope, tried_solutions, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '待处理')"""

        params = (
            ticket_data.get('title'),
            ticket_data.get('category'),
            ticket_data.get('priority'),
            ticket_data.get('contact_name'),
            ticket_data.get('department') or None,
            ticket_data.get('contact_phone') or None,
            ticket_data.get('problem_desc'),
            ticket_data.get('impact_scope'),
            ticket_data.get('tried_solutions')
        )

        with get_ticket_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                ticket_id = cursor.lastrowid
                conn.commit()

        return jsonify({
            "success": True,
            "ticket_id": ticket_id,
            "message": f"工单创建成功，ID: {ticket_id}"
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"服务器错误: {str(e)}"}), 500

@oauth_app.route("/health", methods=["GET"])
def oauth_health():
    """健康检查（包含数据库连接）"""
    db_status = "unknown"
    try:
        with get_ticket_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "service": "oauth+ticket",
        "port": OAUTH_PORT,
        "status": "running",
        "database": db_status
    }, 200


def run_main():
    logger.info(f"主服务启动: 0.0.0.0:{MAIN_PORT}")
    main_app.run(host="0.0.0.0", port=MAIN_PORT, threaded=True)


def run_oauth():
    logger.info(f"OAuth服务启动: 0.0.0.0:{OAUTH_PORT}")
    oauth_app.run(host="0.0.0.0", port=OAUTH_PORT, threaded=True)


# ========== 工单状态监控（轮询） ==========
import time

def ticket_status_monitor():
    """监控工单状态变化，完成时通知用户"""
    logger.info(f"工单状态监控启动，轮询间隔: {TICKET_MONITOR_INTERVAL}秒")

    while True:
        try:
            # 查询已解决但未通知的工单，同时关联用户表获取 userid
            sql = """
            SELECT t.id, t.title, t.contact_name, t.contact_phone, t.problem_desc,
                   t.resolved_at, t.updated_at, u.userid
            FROM tickets t
            LEFT JOIN wx_users u ON t.contact_phone = u.mobile
            WHERE t.status = '已解决' AND (t.notified IS NULL OR t.notified = 0)
            """

            with get_ticket_db() as conn:
                with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(sql)
                    completed_tickets = cursor.fetchall()

            if completed_tickets:
                print(f"\n[工单监控] 发现 {len(completed_tickets)} 个已完成待通知的工单")

            for ticket in completed_tickets:
                ticket_id = ticket['id']
                title = ticket['title'] or '未命名工单'
                contact_name = ticket['contact_name'] or '用户'
                userid = ticket.get('userid')
                # 优先用 resolved_at，没有则用 updated_at
                resolved_time = ticket.get('resolved_at') or ticket.get('updated_at')

                # 格式化完成时间
                if resolved_time:
                    complete_time = resolved_time.strftime('%Y-%m-%d %H:%M')
                else:
                    complete_time = datetime.now().strftime('%Y-%m-%d %H:%M')

                if not userid:
                    print(f"[工单监控] 工单 {ticket_id} 无法找到对应用户，跳过通知")
                    # 仍然标记为已通知，避免重复查询
                    mark_ticket_notified(ticket_id)
                    continue

                # 构建通知消息（紧凑格式，无图标）
                message = f"""{contact_name}，您好！
您的工单「{title}」已处理完成。
完成时间：{complete_time}
如有问题请随时联系我们。"""

                # 发送消息
                try:
                    wechat_api.send_app_message(userid, message)
                    print(f"[工单监控] 已通知用户 {userid}，工单ID: {ticket_id}")
                    logger.info(f"工单完成通知已发送: ticket_id={ticket_id}, userid={userid}")
                except Exception as e:
                    print(f"[工单监控] 发送通知失败: {e}")
                    logger.error(f"工单完成通知发送失败: ticket_id={ticket_id}, error={e}")

                # 标记为已通知
                mark_ticket_notified(ticket_id)

        except Exception as e:
            logger.error(f"工单状态监控异常: {e}")
            print(f"[工单监控] 异常: {e}")

        # 等待下一次轮询
        time.sleep(TICKET_MONITOR_INTERVAL)


def mark_ticket_notified(ticket_id):
    """标记工单已通知"""
    try:
        sql = "UPDATE tickets SET notified = 1 WHERE id = %s"
        with get_ticket_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (ticket_id,))
                conn.commit()
    except Exception as e:
        logger.error(f"标记工单已通知失败: ticket_id={ticket_id}, error={e}")


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 企业微信AI助手（优化版）")
    print("=" * 60)
    print(f"📍 消息服务: http://0.0.0.0:{MAIN_PORT}/yjcallback")
    print(f"📍 OAuth服务: http://0.0.0.0:{OAUTH_PORT}/oauth_callback")
    print(f"📍 工单接口: http://0.0.0.0:{OAUTH_PORT}/insert_ticket")
    if TICKET_MONITOR_ENABLED:
        print(f"📍 工单监控: 每{TICKET_MONITOR_INTERVAL}秒轮询")
    else:
        print(f"📍 工单监控: 已关闭")
    print(f"📍 对外授权: {OAUTH_REDIRECT_URI}")
    print("=" * 60)

    t1 = threading.Thread(target=run_main, daemon=True)
    t2 = threading.Thread(target=run_oauth, daemon=True)

    t1.start()
    t2.start()

    if TICKET_MONITOR_ENABLED:
        t3 = threading.Thread(target=ticket_status_monitor, daemon=True)
        t3.start()

    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\n服务已停止0000")