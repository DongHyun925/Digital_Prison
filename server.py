import os
import traceback
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from ai_engine import session_manager

app = Flask(__name__)
# 표준 flask-cors 설정을 사용하여 브라우저 호환성 확보
CORS(app, resources={r"/*": {"origins": "*"}})

@app.route('/')
def health_check():
    return "🕸️ 404: THE DIGITAL PRISON - BACKEND SYSTEM ONLINE 🕸️"

@app.route('/api/ping')
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
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

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
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route('/api/hint', methods=['POST'])
def hint():
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        session_manager.state['api_key'] = api_key
        ui_data = session_manager.get_hint()
        return jsonify(ui_data)
    except Exception as e:
        print(f"HINT ERROR: {traceback.format_exc()}")
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    # 전역 에러 핸들러: 어떤 오류가 나도 JSON과 CORS를 보장
    response = jsonify({
        "error": "Internal Server Error",
        "message": str(e),
        "traceback": traceback.format_exc()
    })
    return response, 500

if __name__ == '__main__':
    # 런타임 오류 방지를 위해 os.environ 사용 시 os 임포트 확인 완료
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
