from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime, timedelta
import threading
import time
import io
import sys

app = Flask(__name__)
CORS(app)

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
    except Exception as e:
        print(f'Error saving servers: {e}')

# Store pending commands for each server
pending_commands = {}
# Store script execution results
script_results = {}

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
                <li>POST /api/addkey - Add a new key (Bot uses this)</li>
                <li>POST /api/revokekey - Revoke a specific key</li>
                <li>POST /api/revokeuserkeys - Revoke all keys for a user</li>
                <li>POST /api/execute - Execute script on server (queues for Roblox)</li>
                <li>POST /api/execute/direct - Execute script directly on API server (for testing)</li>
                <li>GET /api/command/pending - Get pending commands for a server</li>
            </ul>
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

@app.route('/api/validate', methods=['POST'])
def validate_key():
    try:
        data = request.json
        key = data.get('key')
        
        if not key:
            return jsonify({'valid': False, 'message': 'No key provided'})
        
        keys = load_keys()
        if key in keys:
            key_data = keys[key]
            expiry = datetime.fromisoformat(key_data['expires_at'])
            if expiry < datetime.now():
                return jsonify({'valid': False, 'message': 'Key expired'})
            if not key_data.get('active', True):
                return jsonify({'valid': False, 'message': 'Key inactive'})
            
            key_data['uses'] = key_data.get('uses', 0) + 1
            save_keys(keys)
            
            return jsonify({
                'valid': True,
                'message': 'Key valid',
                'key_data': key_data
            })
        else:
            return jsonify({'valid': False, 'message': 'Invalid key'})
    except Exception as e:
        return jsonify({'valid': False, 'message': str(e)}), 500

# ========================================================
# BOT ENDPOINTS
# ========================================================

@app.route('/api/addkey', methods=['POST'])
def add_key():
    try:
        data = request.json
        key = data.get('key')
        user_id = data.get('userId')
        username = data.get('username')
        max_uses = data.get('maxUses', 1)
        duration_days = data.get('durationDays', 30)
        
        if not key or not user_id:
            return jsonify({'success': False, 'reason': 'Missing key or userId'}), 400
        
        keys = load_keys()
        
        if key in keys:
            return jsonify({'success': False, 'reason': 'Key already exists'}), 400
        
        now = datetime.now()
        keys[key] = {
            'created_by': username or str(user_id),
            'user_id': str(user_id),
            'created_at': now.isoformat(),
            'expires_at': (now + timedelta(days=duration_days)).isoformat(),
            'max_uses': max_uses,
            'uses': 0,
            'active': True,
            'duration_days': duration_days
        }
        
        save_keys(keys)
        print(f'[Safe Hub] Key {key} added for user {user_id}')
        
        return jsonify({'success': True, 'message': 'Key added successfully'})
    except Exception as e:
        print(f'[Safe Hub] Error in add_key: {e}')
        return jsonify({'success': False, 'reason': str(e)}), 500

@app.route('/api/revokekey', methods=['POST'])
def revoke_key():
    try:
        data = request.json
        key = data.get('key')
        
        if not key:
            return jsonify({'success': False, 'reason': 'Missing key'}), 400
        
        keys = load_keys()
        
        if key not in keys:
            return jsonify({'success': False, 'reason': 'Key not found'}), 404
        
        keys[key]['active'] = False
        save_keys(keys)
        
        print(f'[Safe Hub] Key {key} revoked')
        return jsonify({'success': True, 'message': 'Key revoked successfully'})
    except Exception as e:
        print(f'[Safe Hub] Error in revoke_key: {e}')
        return jsonify({'success': False, 'reason': str(e)}), 500

@app.route('/api/revokeuserkeys', methods=['POST'])
def revoke_user_keys():
    try:
        data = request.json
        user_id = data.get('userId')
        
        if not user_id:
            return jsonify({'success': False, 'reason': 'Missing userId'}), 400
        
        keys = load_keys()
        revoked_count = 0
        
        for key, key_data in keys.items():
            if key_data.get('user_id') == str(user_id) and key_data.get('active', False):
                keys[key]['active'] = False
                revoked_count += 1
        
        save_keys(keys)
        print(f'[Safe Hub] Revoked {revoked_count} keys for user {user_id}')
        
        return jsonify({
            'success': True,
            'message': f'Revoked {revoked_count} keys',
            'count': revoked_count
        })
    except Exception as e:
        print(f'[Safe Hub] Error in revoke_user_keys: {e}')
        return jsonify({'success': False, 'reason': str(e)}), 500

# ========================================================
# EXECUTOR ENDPOINTS
# ========================================================

@app.route('/api/execute', methods=['POST'])
def execute_script():
    """Queue a script for execution on a Roblox server"""
    try:
        data = request.json
        server_id = data.get('serverId')
        player = data.get('player', 'ALL')
        script = data.get('script', '')
        command_type = data.get('command', 'script')
        
        print(f'[Safe Hub] Execute request for server {server_id}')
        print(f'[Safe Hub] Player: {player}, Script: {script[:100] if script else "None"}...')
        
        if not server_id:
            return jsonify({'success': False, 'message': 'No server ID provided'}), 400
        
        if not script and command_type != 'shutdown':
            return jsonify({'success': False, 'message': 'No script provided'}), 400
        
        command_data = {
            'id': datetime.now().isoformat(),
            'timestamp': datetime.now().isoformat(),
            'player': player,
            'command': command_type,
            'script': script if command_type != 'shutdown' else '',
            'status': 'pending'
        }
        
        if server_id not in pending_commands:
            pending_commands[server_id] = []
        pending_commands[server_id].append(command_data)
        
        print(f'[Safe Hub] Command stored for server {server_id}')
        
        return jsonify({
            'success': True,
            'message': 'Script queued for execution',
            'command_id': command_data['id']
        })
    except Exception as e:
        print(f'[Safe Hub] Error in execute_script: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/execute/direct', methods=['POST'])
def execute_direct():
    """Execute a script directly on the API server (for testing without Roblox)"""
    try:
        data = request.json
        server_id = data.get('serverId')
        player = data.get('player', 'ALL')
        script = data.get('script', '')
        
        print(f'[Safe Hub] DIRECT EXECUTE on {server_id} for {player}')
        print(f'[Safe Hub] Script: {script}')
        
        # Execute Python code and capture output
        result = "No output"
        error_output = None
        
        try:
            # Capture stdout
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            
            # Create a safe execution environment
            exec_globals = {
                'print': print,
                'server_id': server_id,
                'player': player,
                '__builtins__': {'print': print, 'range': range, 'len': len, 'str': str, 'int': int, 'float': float, 'list': list, 'dict': dict, 'tuple': tuple}
            }
            
            # Execute the script
            exec(script, exec_globals)
            
            # Get the output
            result = sys.stdout.getvalue()
            sys.stdout = old_stdout
            
            if not result or result.strip() == '':
                result = "Script executed with no output"
                
        except Exception as e:
            error_output = str(e)
            result = f"Script error: {e}"
            sys.stdout = old_stdout
        
        # Store the result
        if server_id not in script_results:
            script_results[server_id] = []
        script_results[server_id].append({
            'timestamp': datetime.now().isoformat(),
            'player': player,
            'script': script[:200],
            'output': result,
            'error': error_output
        })
        
        return jsonify({
            'success': True,
            'message': f'Script executed on {server_id} for {player}',
            'output': result,
            'status': 'executed'
        })
    except Exception as e:
        print(f'[Safe Hub] Error in execute_direct: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/command/pending', methods=['GET'])
def get_pending_commands():
    """Get pending commands for a server (called by Roblox server)"""
    try:
        server_id = request.args.get('serverId')
        
        if not server_id:
            return jsonify({'commands': []})
        
        commands = pending_commands.get(server_id, [])
        pending_commands[server_id] = []
        
        print(f'[Safe Hub] Sent {len(commands)} commands to server {server_id}')
        
        return jsonify({'commands': commands})
    except Exception as e:
        return jsonify({'commands': [], 'error': str(e)}), 500

@app.route('/api/command/complete', methods=['POST'])
def complete_command():
    """Mark a command as completed (called by Roblox server)"""
    try:
        data = request.json
        server_id = data.get('serverId')
        command_id = data.get('commandId')
        result = data.get('result', 'success')
        
        print(f'[Safe Hub] Command {command_id} completed on {server_id}: {result}')
        
        if server_id not in script_results:
            script_results[server_id] = []
        script_results[server_id].append({
            'command_id': command_id,
            'result': result,
            'timestamp': datetime.now().isoformat()
        })
        
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/command/results', methods=['GET'])
def get_results():
    """Get command results (called by dashboard)"""
    try:
        server_id = request.args.get('serverId')
        
        if not server_id:
            return jsonify({'results': []})
        
        results = script_results.get(server_id, [])
        script_results[server_id] = []
        
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'results': [], 'error': str(e)}), 500

@app.route('/api/debug', methods=['GET'])
def debug():
    server_data = load_servers()
    return jsonify({
        'servers': server_data,
        'server_count': len(server_data.get('servers', [])),
        'keys': list(load_keys().keys()),
        'pending_commands': pending_commands,
        'script_results': script_results
    })

@app.route('/test', methods=['GET'])
def test():
    return jsonify({
        'status': 'Server is running',
        'port': 8080,
        'server_count': len(load_servers().get('servers', [])),
        'keys': list(load_keys().keys())
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
