from flask import Flask, request, jsonify
import pymysql
import json
from contextlib import contextmanager

app = Flask(__name__)

# 数据库配置
DB_CONFIG = {
    'host': '8.153.198.194',
    'port': 63306,
    'user': 'wx_qa',
    'password': 'cKXF45BLSHW68ynk',
    'database': 'wx_qa',
    'charset': 'utf8mb4'
}

@contextmanager
def get_db():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        yield conn
    finally:
        conn.close()

def parse_ticket_data(data):
    """
    兼容多种输入格式：
    1. {"ticket_json": "字符串"} 
    2. {"text": "字符串"}  # Dify LLM节点常见格式
    3. 直接就是对象
    4. 原始字符串在 body 中
    """
    ticket_data = None
    
    # 情况1：标准格式 {"ticket_json": "..."}
    if isinstance(data, dict) and 'ticket_json' in data:
        try:
            ticket_data = json.loads(data['ticket_json'])
        except:
            pass
    
    # 情况2：Dify LLM节点格式 {"text": "..."}
    if ticket_data is None and isinstance(data, dict) and 'text' in data:
        try:
            ticket_data = json.loads(data['text'])
        except:
            pass
    
    # 情况3：直接是对象（已经解析好的）
    if ticket_data is None and isinstance(data, dict) and 'title' in data:
        ticket_data = data
    
    # 情况4：尝试把整个 data 当字符串解析
    if ticket_data is None:
        try:
            if isinstance(data, str):
                ticket_data = json.loads(data)
        except:
            pass
    
    return ticket_data

@app.route('/insert_ticket', methods=['POST'])
def insert_ticket():
    try:
        # 获取数据
        data = request.get_json()
        
        # 记录原始请求用于调试
        print(f"收到请求: {json.dumps(data, ensure_ascii=False)[:500]}")
        
        if not data:
            # 尝试从原始 body 读取
            raw_body = request.get_data(as_text=True)
            print(f"原始 body: {raw_body[:500]}")
            try:
                data = json.loads(raw_body)
            except:
                return jsonify({
                    "success": False,
                    "message": "无法解析请求体",
                    "raw": raw_body[:200]
                }), 400
        
        # 解析工单数据
        ticket_data = parse_ticket_data(data)
        
        if ticket_data is None:
            return jsonify({
                "success": False,
                "message": "无法解析 ticket 数据",
                "received": data,
                "hint": "请确保发送的是JSON字符串或包含 ticket_json/text 字段的对象"
            }), 400
        
        print(f"解析后的数据: {json.dumps(ticket_data, ensure_ascii=False)[:500]}")
        
        # 检查必填字段
        required_fields = ['title', 'category', 'priority', 'contact_name']
        missing = [f for f in required_fields if not ticket_data.get(f)]
        if missing:
            return jsonify({
                "success": False,
                "message": f"缺少必填字段: {', '.join(missing)}",
                "received_fields": list(ticket_data.keys())
            }), 400
        
        # 准备数据
        sql = """INSERT INTO tickets 
        (title, category, priority, contact_name, department, contact_phone,
         problem_desc, impact_scope, tried_solutions, status) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, '待处理')"""
        
        params = (
            ticket_data.get('title'),
            ticket_data.get('category'),
            ticket_data.get('priority'),
            ticket_data.get('contact_name'),
            ticket_data.get('department') if ticket_data.get('department') else None,
            ticket_data.get('contact_phone') if ticket_data.get('contact_phone') else None,
            ticket_data.get('problem_desc'),
            ticket_data.get('impact_scope'),
            ticket_data.get('tried_solutions')
        )
        
        # 执行插入
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                ticket_id = cursor.lastrowid
                conn.commit()
        
        return jsonify({
            "success": True,
            "ticket_id": ticket_id,
            "message": f"工单创建成功，ID: {ticket_id}",
            "title": ticket_data.get('title')
        })
        
    except Exception as e:
        import traceback
        print(f"错误: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "message": f"服务器错误: {str(e)}"
        }), 500

@app.route('/insert_ticket_raw', methods=['POST'])
def insert_ticket_raw():
    """
    备用接口：直接接收原始 JSON 字符串（不是包装在对象里）
    """
    try:
        raw_body = request.get_data(as_text=True)
        print(f"原始 body: {raw_body[:500]}")
        
        try:
            ticket_data = json.loads(raw_body)
        except json.JSONDecodeError as e:
            return jsonify({
                "success": False,
                "message": f"JSON解析失败: {str(e)}",
                "raw": raw_body[:200]
            }), 400
        
        # 同样的插入逻辑...
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
            ticket_data.get('department') if ticket_data.get('department') else None,
            ticket_data.get('contact_phone') if ticket_data.get('contact_phone') else None,
            ticket_data.get('problem_desc'),
            ticket_data.get('impact_scope'),
            ticket_data.get('tried_solutions')
        )
        
        with get_db() as conn:
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
        return jsonify({
            "success": False,
            "message": f"服务器错误: {str(e)}"
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    try:
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
        return jsonify({"status": "ok", "database": "connected"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
