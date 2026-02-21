from flask import Flask, request, jsonify
from flask_cors import CORS
import traceback
from ai_engine import session_manager

app = Flask(__name__)
# 폰트엔드와의 원활한 통신을 위해 CORS 정책을 최대한 완화 (Preflight 문제 해결)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True, allow_headers="*", methods=["GET", "POST", "OPTIONS"])

@app.route('/')
def health_check():
    return "🕸️ 404: THE DIGITAL PRISON - BACKEND SYSTEM ONLINE 🕸️"

@app.route('/api/init', methods=['POST'])
def init_game():
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        state = session_manager.reset()
        session_manager.state['api_key'] = api_key
        return jsonify(session_manager.format_state_for_ui())
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"CRITICAL ERROR in /api/init: {error_trace}")
        return jsonify({
            "logs": [{
                "agent": "SYSTEM",
                "text": f"CRITICAL BOOT ERROR: {str(e)}",
                "type": "error"
            }],
            "error_detail": error_trace
        }), 500

@app.route('/api/action', methods=['POST'])
def game_action():
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        data = request.json or {}
        user_input = data.get('command', '')
        
        session_manager.state['api_key'] = api_key
        ui_data = session_manager.process_action(user_input)
        return jsonify(ui_data)
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"CRITICAL ERROR in /api/action: {error_trace}")
        return jsonify({
            "logs": [{
                "agent": "SYSTEM",
                "text": f"CORE LOGIC FAILURE: {str(e)}",
                "type": "error"
            }],
            "error_detail": error_trace
        }), 500

@app.route('/api/hint', methods=['POST'])
def hint():
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        session_manager.state['api_key'] = api_key
        ui_data = session_manager.get_hint()
        return jsonify(ui_data)
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"CRITICAL ERROR in /api/hint: {error_trace}")
        return jsonify({
            "logs": [{
                "agent": "SYSTEM",
                "text": f"GUIDE SYSTEM FAILURE: {str(e)}",
                "type": "error"
            }]
        }), 500

@app.route('/api/load', methods=['POST'])
def load_game():
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        data = request.json or {}
        state_data = data.get('state')
        if not state_data:
            return jsonify({"success": False, "logs": [{"agent": "SYSTEM", "text": "NO SAVE DATA PROVIDED", "type": "error"}]}), 400
        
        session_manager.state = state_data
        session_manager.state['api_key'] = api_key
        return jsonify(session_manager.format_state_for_ui())
    except Exception as e:
        return jsonify({"success": False, "logs": [{"agent": "SYSTEM", "text": f"LOAD ERROR: {str(e)}", "type": "error"}]}), 500

if __name__ == '__main__':
    print("Starting Flask Server on port 5000...")
    app.run(debug=True, port=5000)
