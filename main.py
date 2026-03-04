# -*- coding: utf-8 -*-
"""
main.py - 主服务入口（双端口）
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import threading
from datetime import datetime
from flask import Flask, request, make_response, jsonify

from config import (
    CORP_ID, CORP_SECRET, CONTACTS_SECRET, TOKEN, ENCODING_AES_KEY, AGENT_ID,
    AI_API_URL, AI_API_KEY, OAUTH_SIGN_KEY, OAUTH_REDIRECT_URI,
    MAIN_PORT, OAUTH_PORT, DB_CONFIG
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
ai_client = AIClient(AI_API_URL, AI_API_KEY)

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

@oauth_app.route("/upload", methods=["GET"])
def upload_page():
    """文件上传页面"""
    return """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>上传文件</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #f5f5f5;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 2px 20px rgba(0,0,0,0.1);
                text-align: center;
                max-width: 350px;
                width: 90%;
            }
            h1 { font-size: 20px; color: #333; margin-bottom: 20px; }
            .upload-area {
                border: 2px dashed #ddd;
                border-radius: 8px;
                padding: 40px 20px;
                margin-bottom: 20px;
                cursor: pointer;
                transition: all 0.3s;
            }
            .upload-area:hover, .upload-area.dragover {
                border-color: #07c160;
                background: #f0fff4;
            }
            .upload-area .icon { font-size: 48px; margin-bottom: 10px; }
            .upload-area p { color: #666; font-size: 14px; }
            .file-input { display: none; }
            .file-info {
                background: #f5f5f5;
                padding: 12px;
                border-radius: 6px;
                margin-bottom: 20px;
                display: none;
                text-align: left;
            }
            .file-info .name { font-weight: 500; color: #333; word-break: break-all; }
            .file-info .size { color: #999; font-size: 12px; }
            .btn {
                width: 100%;
                padding: 14px;
                background: #07c160;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                cursor: pointer;
                display: none;
            }
            .btn:disabled { background: #ccc; }
            .btn:active { background: #06ad56; }
            .status {
                margin-top: 15px;
                padding: 12px;
                border-radius: 6px;
                display: none;
            }
            .status.success { background: #f0fff4; color: #07c160; }
            .status.error { background: #fff0f0; color: #f00; }
            .loading { display: none; margin-top: 15px; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📁 上传文件</h1>
            <div class="upload-area" id="uploadArea">
                <div class="icon">📄</div>
                <p>点击选择文件<br>或拖拽文件到这里</p>
            </div>
            <input type="file" class="file-input" id="fileInput">
            <div class="file-info" id="fileInfo">
                <div class="name" id="fileName"></div>
                <div class="size" id="fileSize"></div>
            </div>
            <button class="btn" id="uploadBtn">上传文件</button>
            <div class="loading" id="loading">⏳ 上传中...</div>
            <div class="status" id="status"></div>
        </div>
        <script>
            const uploadArea = document.getElementById('uploadArea');
            const fileInput = document.getElementById('fileInput');
            const fileInfo = document.getElementById('fileInfo');
            const fileName = document.getElementById('fileName');
            const fileSize = document.getElementById('fileSize');
            const uploadBtn = document.getElementById('uploadBtn');
            const loading = document.getElementById('loading');
            const status = document.getElementById('status');

            let selectedFile = null;

            uploadArea.onclick = () => fileInput.click();

            uploadArea.ondragover = (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            };
            uploadArea.ondragleave = () => uploadArea.classList.remove('dragover');
            uploadArea.ondrop = (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                if (e.dataTransfer.files.length) {
                    handleFile(e.dataTransfer.files[0]);
                }
            };

            fileInput.onchange = () => {
                if (fileInput.files.length) {
                    handleFile(fileInput.files[0]);
                }
            };

            function handleFile(file) {
                selectedFile = file;
                fileName.textContent = file.name;
                fileSize.textContent = formatSize(file.size);
                fileInfo.style.display = 'block';
                uploadBtn.style.display = 'block';
                status.style.display = 'none';
            }

            function formatSize(bytes) {
                if (bytes < 1024) return bytes + ' B';
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
                return (bytes / 1024 / 1024).toFixed(1) + ' MB';
            }

            uploadBtn.onclick = async () => {
                if (!selectedFile) return;

                uploadBtn.disabled = true;
                loading.style.display = 'block';
                status.style.display = 'none';

                const formData = new FormData();
                formData.append('file', selectedFile);

                try {
                    const resp = await fetch('/upload', {
                        method: 'POST',
                        body: formData
                    });
                    const result = await resp.json();

                    loading.style.display = 'none';
                    status.style.display = 'block';

                    if (result.success) {
                        status.className = 'status success';
                        status.textContent = '✅ 上传成功！';
                        setTimeout(() => {
                            if (window.WeixinJSBridge) {
                                WeixinJSBridge.call('closeWindow');
                            } else {
                                window.close();
                            }
                        }, 1500);
                    } else {
                        status.className = 'status error';
                        status.textContent = '❌ ' + (result.error || '上传失败');
                        uploadBtn.disabled = false;
                    }
                } catch (e) {
                    loading.style.display = 'none';
                    status.style.display = 'block';
                    status.className = 'status error';
                    status.textContent = '❌ 网络错误，请重试';
                    uploadBtn.disabled = false;
                }
            };
        </script>
    </body>
    </html>
    """

@oauth_app.route("/upload", methods=["POST"])
def upload_file():
    """文件上传接口"""
    try:
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
        save_filename = f"{timestamp}_{name}{ext}"
        save_path = os.path.join(FILE_SAVE_DIR, save_filename)

        # 保存文件
        file.save(save_path)

        logger.info(f"文件上传成功: {save_path}")

        return jsonify({
            "success": True,
            "filename": original_name,
            "saved_as": save_filename
        })

    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@oauth_app.route("/health", methods=["GET"])
def oauth_health():
    return {"service": "oauth", "port": OAUTH_PORT, "status": "running"}, 200


def run_main():
    logger.info(f"主服务启动: 0.0.0.0:{MAIN_PORT}")
    main_app.run(host="0.0.0.0", port=MAIN_PORT, threaded=True)


def run_oauth():
    logger.info(f"OAuth服务启动: 0.0.0.0:{OAUTH_PORT}")
    oauth_app.run(host="0.0.0.0", port=OAUTH_PORT, threaded=True)


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 企业微信AI助手（优化版）")
    print("=" * 60)
    print(f"📍 消息服务: http://0.0.0.0:{MAIN_PORT}/yjcallback")
    print(f"📍 OAuth服务: http://0.0.0.0:{OAUTH_PORT}/oauth_callback")
    print(f"📍 对外授权: {OAUTH_REDIRECT_URI}")
    print("=" * 60)

    t1 = threading.Thread(target=run_main, daemon=True)
    t2 = threading.Thread(target=run_oauth, daemon=True)

    t1.start()
    t2.start()

    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\n服务已停止0000")