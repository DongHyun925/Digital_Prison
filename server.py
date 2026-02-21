import os
import traceback
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from ai_engine import session_manager

app = Flask(__name__)

# flask-cors를 사용하여 CORS 정책을 표준 방식으로 적용
# 모든 오리진과 모든 헤더를 허용하여 브라우저 차단 방지
CORS(app, resources={r"/*": {"origins": "*", "allow_headers": "*", "methods": "*"}})

@app.route('/')
def health_check():
    return "🕸️ 404: THE DIGITAL PRISON - BACKEND SYSTEM ONLINE 🕸️"

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "pong", "message": "Connection stable"})

@app.route('/api/init', methods=['POST'])
def init_game():
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        session_manager.reset()
        session_manager.state['api_key'] = api_key
        return jsonify(session_manager.format_state_for_ui())
    except Exception as e:
        print(f"INIT ERROR: {traceback.format_exc()}")
        return jsonify({
            "error": "Init Failure",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route('/api/action', methods=['POST'])
def game_action():
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        data = request.get_json(silent=True) or {}
        user_input = data.get('command', '')
        
        print(f"ACTION REQUEST: {user_input}")
        session_manager.state['api_key'] = api_key
        ui_data = session_manager.process_action(user_input)
        return jsonify(ui_data)
    except Exception as e:
        print(f"ACTION ERROR: {traceback.format_exc()}")
        return jsonify({
            "error": "Action Failure",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route('/api/hint', methods=['POST'])
def hint():
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        session_manager.state['api_key'] = api_key
        ui_data = session_manager.get_hint()
        return jsonify(ui_data)
    except Exception as e:
        print(f"HINT ERROR: {traceback.format_exc()}")
        return jsonify({
            "error": "Hint Failure",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500

@app.route('/api/load', methods=['POST'])
def load_game():
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        data = request.get_json(silent=True) or {}
        state_data = data.get('state')
        if not state_data:
            return jsonify({"error": "No save data"}), 400
        
        session_manager.state = state_data
        session_manager.state['api_key'] = api_key
        return jsonify(session_manager.format_state_for_ui())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(500)
def handle_500(e):
    # 500 에러 발생 시에도 JSON 응답과 CORS 헤더를 유지함 (flask-cors가 자동 처리)
    return jsonify({
        "error": "Internal Server Error",
        "message": "서버 내부에서 예상치 못한 오류가 발생했습니다.",
        "traceback": traceback.format_exc()
    }), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
