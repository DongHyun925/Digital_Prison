from flask import Flask, request, jsonify
from flask_cors import CORS
import traceback
from ai_engine import session_manager

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

@app.route('/api/init', methods=['POST'])
def init_game():
    api_key = request.headers.get('X-Gemini-API-Key', '')
    state = session_manager.reset()
    session_manager.state['api_key'] = api_key
    return jsonify(session_manager.format_state_for_ui())

@app.route('/api/action', methods=['POST'])
def game_action():
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        data = request.json
        user_input = data.get('command', '')
        
        # Ensure session state has the current request's API key
        session_manager.state['api_key'] = api_key
        ui_data = session_manager.process_action(user_input)
        return jsonify(ui_data)
    except Exception as e:
        print(f"ERROR in /api/action: {str(e)}")
        traceback.print_exc()
        return jsonify({"logs": [{"agent": "SYSTEM", "text": f"DEBUG: {str(e)}", "type": "error"}]}), 500

@app.route('/api/hint', methods=['POST'])
def hint():
    try:
        api_key = request.headers.get('X-Gemini-API-Key', '')
        session_manager.state['api_key'] = api_key
        ui_data = session_manager.get_hint()
        return jsonify(ui_data)
    except Exception as e:
        print(f"ERROR in /api/hint: {str(e)}")
        traceback.print_exc()
        return jsonify({"logs": [{"agent": "SYSTEM", "text": f"DEBUG: {str(e)}", "type": "error"}]}), 500

@app.route('/api/upload', methods=['POST'])
def upload_image():
    # Vision Agent integration can be added here
    return jsonify({"logs": []})

@app.route('/api/save', methods=['POST'])
def save_game():
    return jsonify({"state": session_manager.state})

@app.route('/api/load', methods=['POST'])
def load_game():
    api_key = request.headers.get('X-Gemini-API-Key', '')
    data = request.json
    state_data = data.get('state')
    session_manager.state = state_data
    session_manager.state['api_key'] = api_key
    return jsonify(session_manager.format_state_for_ui())

if __name__ == '__main__':
    print("Starting Flask Server on port 5000...")
    app.run(debug=True, port=5000)
