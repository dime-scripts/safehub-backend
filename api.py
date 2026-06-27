# api.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

KEYS_FILE = 'keys.json'

def load_keys():
    if not os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, 'w') as f:
            json.dump({}, f)
        return {}
    with open(KEYS_FILE, 'r') as f:
        return json.load(f)

def save_keys(keys):
    with open(KEYS_FILE, 'w') as f:
        json.dump(keys, f, indent=4)

@app.route('/api/validate', methods=['POST'])
def validate_key():
    data = request.json
    key = data.get('key')
    
    if not key:
        return jsonify({'valid': False, 'reason': 'No key provided'})
    
    keys = load_keys()
    
    if key not in keys:
        return jsonify({'valid': False, 'reason': 'Invalid key'})
    
    key_data = keys[key]
    expiry = datetime.fromisoformat(key_data['expires_at'])
    
    if not key_data['active']:
        return jsonify({'valid': False, 'reason': 'Key has been revoked'})
    
    if expiry < datetime.now():
        return jsonify({'valid': False, 'reason': 'Key has expired'})
    
    if key_data['uses'] >= key_data['max_uses']:
        return jsonify({'valid': False, 'reason': 'Key has reached maximum uses'})
    
    key_data['uses'] += 1
    save_keys(keys)
    
    return jsonify({'valid': True, 'message': 'Key validated successfully'})

@app.route('/api/addkey', methods=['POST'])
def add_key():
    data = request.json
    key = data.get('key')
    user_id = data.get('userId', 'unknown')
    username = data.get('username', 'api')
    max_uses = data.get('maxUses', 1)
    
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
    return jsonify({'success': True, 'key': key})

@app.route('/api/keys', methods=['GET'])
def list_keys():
    keys = load_keys()
    key_list = [{'key': k, **v} for k, v in keys.items()]
    return jsonify({'keys': key_list})

@app.route('/test', methods=['GET'])
def test():
    keys = load_keys()
    return jsonify({
        'status': 'Server is running',
        'port': 8080,
        'keyCount': len(keys),
        'keys': list(keys.keys())
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
