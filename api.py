from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'safehub-secret-key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

KEYS_FILE = 'keys.json'
SERVER_DATA_FILE = 'servers.json'

def load_keys():
    try:
        if not os.path.exists(KEYS_FILE):
            return create_default_keys()
        with open(KEYS_FILE, 'r') as f:
            data = f.read()
            if not data or data.strip() == '':
                return create_default_keys()
            return json.loads(data)
    except:
        return create_default_keys()

def create_default_keys():
    default_keys = {
        "TESTMB2ZUJ": {
            "created_by": "system",
            "user_id": "system",
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(days=365)).isoformat(),
            "max_uses": 999,
            "uses": 0,
            "active": True,
            "duration_days": 365
        }
    }
    save_keys(default_keys)
    return default_keys

def save_keys(keys):
    try:
        with open(KEYS_FILE, 'w') as f:
            json.dump(keys, f, indent=4)
    except Exception as e:
        print(f'Error saving keys: {e}')

def load_servers():
    try:
        if not os.path.exists(SERVER_DATA_FILE):
            return {'servers': []}
        with open(SERVER_DATA_FILE, 'r') as f:
            return json.loads(f.read())
    except:
        return {'servers': []}

def save_servers(data):
    try:
        with open(SERVER_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        print(f'[Safe Hub] Servers saved: {len(data.get("servers", []))} servers')
        # Broadcast update to all connected clients
        socketio.emit('server_update', data)
    except Exception as e:
        print(f'Error saving servers: {e}')

@app.route('/')
def serve_dashboard():
    return '''
    <html>
        <head><title>Safe Hub API</title></head>
        <body>
            <h1>Safe Hub API is running</h1>
            <p>Endpoints:</p>
            <ul>
                <li>POST /api/update - Update server data</li>
                <li>GET /api/servers - Get server data</li>
                <li>GET /api/keys - List keys</li>
                <li>POST /api/validate - Validate a key</li>
            </ul>
            <p>WebSocket: wss://safehub-backend-production.up.railway.app</p>
        </body>
    </html>
    '''

@app.route('/api/update', methods=['POST'])
def update_server():
    try:
        data = request.json
        print(f'[Safe Hub] Received update from: {data.get("gameName", "Unknown")}')
        print(f'[Safe Hub] Players: {data.get("players", 0)} Server: {data.get("serverId", "Unknown")}')
        
        server_data = load_servers()
        servers = server_data['servers']
        
        existing_index = next((i for i, s in enumerate(servers) if str(s.get('serverId')) == str(data.get('serverId'))), -1)
        
        if existing_index != -1:
            servers[existing_index] = data
        else:
            servers.append(data)
        
        save_servers(server_data)
        
        return jsonify({'status': 'ok', 'message': 'Data received'})
    except Exception as e:
        print(f'[Safe Hub] Error in update_server: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/servers', methods=['GET'])
def get_servers():
    try:
        server_data = load_servers()
        return jsonify(server_data)
    except Exception as e:
        return jsonify({'servers': [], 'error': str(e)}), 500

@app.route('/api/keys', methods=['GET'])
def list_keys():
    try:
        keys = load_keys()
        key_list = [{'key': k, **v} for k, v in keys.items()]
        return jsonify({'keys': key_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug', methods=['GET'])
def debug():
    server_data = load_servers()
    return jsonify({
        'servers': server_data,
        'server_count': len(server_data.get('servers', [])),
        'keys': list(load_keys().keys())
    })

@app.route('/test', methods=['GET'])
def test():
    return jsonify({
        'status': 'Server is running',
        'port': 8080,
        'server_count': len(load_servers().get('servers', [])),
        'keys': list(load_keys().keys())
    })

@socketio.on('connect')
def handle_connect():
    print('[Safe Hub] Client connected via WebSocket')
    # Send current server data on connection
    server_data = load_servers()
    emit('server_update', server_data)

@socketio.on('disconnect')
def handle_disconnect():
    print('[Safe Hub] Client disconnected')

@socketio.on('command')
def handle_command(data):
    print(f'[Safe Hub] Command received: {data}')
    # Process command and emit response
    response = {
        'status': 'received',
        'command': data,
        'timestamp': datetime.now().isoformat()
    }
    emit('command_result', response)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080, debug=False)
