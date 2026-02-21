import os
import traceback
from flask import Flask, request, jsonify, make_response
from ai_engine import session_manager

app = Flask(__name__)

# --- Manual CORS Handling ---
def add_cors_headers(response):
    response.headers.set('Access-Control-Allow-Origin', '*')
    response.headers.set('Access-Control-Allow-Headers', 'Content-Type,X-Gemini-API-Key,Authorization')
    response.headers.set('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.after_request
def after_request(response):
    return add_cors_headers(response)

@app.route('/', methods=['GET', 'OPTIONS'])
def health_check():
    if request.method == 'OPTIONS': return make_response("", 200)
    return "🕸️ 404: THE DIGITAL PRISON - BACKEND SYSTEM ONLINE 🕸️"

@app.route('/api/ping', methods=['GET', 'OPTIONS'])
def ping():
    if request.method == 'OPTIONS': return make_response("", 200)
    return jsonify({"status": "pong", "message": "Connection stable"})

@app.route('/api/init', methods=['POST', 'OPTIONS'])
def init_game():
    if request.method == 'OPTIONS': return make_response("", 200)
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        session_manager.reset()
        session_manager.state['api_key'] = api_key
        return jsonify(session_manager.format_state_for_ui())
    except Exception as e:
        print(f"INIT ERROR: {traceback.format_exc()}")
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route('/api/action', methods=['POST', 'OPTIONS'])
def game_action():
    if request.method == 'OPTIONS': return make_response("", 200)
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

@app.route('/api/hint', methods=['POST', 'OPTIONS'])
def hint():
    if request.method == 'OPTIONS': return make_response("", 200)
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        session_manager.state['api_key'] = api_key
        ui_data = session_manager.get_hint()
        return jsonify(ui_data)
    except Exception as e:
        print(f"HINT ERROR: {traceback.format_exc()}")
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.errorhandler(500)
@app.errorhandler(Exception)
def handle_exception(e):
    response = jsonify({
        "error": "Internal Server Error",
        "message": str(e),
        "traceback": traceback.format_exc()
    })
    return add_cors_headers(make_response(response, 500))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
