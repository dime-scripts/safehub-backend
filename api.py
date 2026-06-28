from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

KEYS_FILE = 'keys.json'

def load_keys():
    """Load keys from file, create default if missing or corrupted"""
    try:
        if not os.path.exists(KEYS_FILE):
            print('[Safe Hub] keys.json not found, creating default...')
            return create_default_keys()
        
        with open(KEYS_FILE, 'r') as f:
            data = f.read()
            if not data or data.strip() == '':
                print('[Safe Hub] keys.json is empty, recreating...')
                return create_default_keys()
            return json.loads(data)
    except json.JSONDecodeError:
        print('[Safe Hub] keys.json is corrupted, recreating...')
        return create_default_keys()
    except Exception as e:
        print(f'[Safe Hub] Error loading keys: {e}')
        return create_default_keys()

def create_default_keys():
    """Create default keys.json with a test key"""
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
    """Save keys to file"""
    try:
        with open(KEYS_FILE, 'w') as f:
            json.dump(keys, f, indent=4)
        print(f'[Safe Hub] Keys saved successfully to {KEYS_FILE}')
    except Exception as e:
        print(f'[Safe Hub] Error saving keys: {e}')

@app.route('/api/validate', methods=['POST'])
def validate_key():
    try:
        data = request.json
        key = data.get('key')
        
        if not key:
            return jsonify({'valid': False, 'reason': 'No key provided'})
        
        keys = load_keys()
        
        if key not in keys:
            return jsonify({'valid': False, 'reason': 'Invalid key'})
        
        key_data = keys[key]
        expiry = datetime.fromisoformat(key_data['expires_at'])
        now = datetime.now()
        
        if not key_data['active']:
            return jsonify({'valid': False, 'reason': 'Key has been revoked'})
        
        if expiry < now:
            return jsonify({'valid': False, 'reason': 'Key has expired'})
        
        if key_data['uses'] >= key_data['max_uses']:
            return jsonify({'valid': False, 'reason': 'Key has reached maximum uses'})
        
        key_data['uses'] += 1
        save_keys(keys)
        
        return jsonify({'valid': True, 'message': 'Key validated successfully'})
    except Exception as e:
        print(f'[Safe Hub] Error in validate_key: {e}')
        return jsonify({'valid': False, 'reason': 'Server error'}), 500

@app.route('/api/addkey', methods=['POST'])
def add_key():
    try:
        data = request.json
        key = data.get('key')
        user_id = data.get('userId', 'unknown')
        username = data.get('username', 'api')
        max_uses = data.get('maxUses', 1)
        
        if not key:
            return jsonify({'success': False, 'reason': 'No key provided'})
        
        keys = load_keys()
        
        if key in keys:
            return jsonify({'success': False, 'reason': 'Key already exists'})
        
        expiry = datetime.now() + timedelta(days=30)
        
        keys[key] = {
            'created_by': username,
            'user_id': user_id,
            'created_at': datetime.now().isoformat(),
            'expires_at': expiry.isoformat(),
            'max_uses': max_uses,
            'uses': 0,
            'active': True,
            'duration_days': 30
        }
        
        save_keys(keys)
        print(f'[Safe Hub] Key added successfully: {key} for user {user_id}')
        return jsonify({'success': True, 'key': key})
    except Exception as e:
        print(f'[Safe Hub] Error in add_key: {e}')
        return jsonify({'success': False, 'reason': str(e)}), 500

# Add this after the other route definitions
@app.route('/api/update', methods=['POST'])
def update_server():
    try:
        data = request.json
        print(f'[Safe Hub] Received update from: {data.get("gameName", "Unknown")}')
        print(f'[Safe Hub] Players: {data.get("players", 0)} Server: {data.get("serverId", "Unknown")}')
        
        # Store server data in a global variable or file
        # For now, we'll just log it and return success
        return jsonify({'status': 'ok', 'message': 'Data received'})
    except Exception as e:
        print(f'[Safe Hub] Error in update_server: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/keys', methods=['GET'])
def list_keys():
    try:
        keys = load_keys()
        key_list = [{'key': k, **v} for k, v in keys.items()]
        return jsonify({'keys': key_list})
    except Exception as e:
        print(f'[Safe Hub] Error in list_keys: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/test', methods=['GET'])
def test():
    try:
        keys = load_keys()
        return jsonify({
            'status': 'Server is running',
            'port': 8080,
            'keyCount': len(keys),
            'keys': list(keys.keys())
        })
    except Exception as e:
        return jsonify({'status': 'Server is running', 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
