const express = require('express');
const WebSocket = require('ws');
const http = require('http');
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');
const cors = require('cors');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

app.use(cors());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));
app.use(express.static('.'));

// Use /tmp directory on Railway for writable storage
let KEYS_FILE;
if (process.env.RAILWAY_ENVIRONMENT || process.env.RENDER) {
    KEYS_FILE = '/tmp/keys.json';
} else {
    KEYS_FILE = path.join(__dirname, 'keys.json');
}

console.log('[Safe Hub] Keys file path:', KEYS_FILE);

function loadKeys() {
    try {
        // Check if file exists
        if (!fs.existsSync(KEYS_FILE)) {
            console.log('[Safe Hub] keys.json does not exist, creating default');
            const defaultKeys = createDefaultKeys();
            fs.writeFileSync(KEYS_FILE, JSON.stringify(defaultKeys, null, 4));
            return defaultKeys;
        }
        
        // Read the file
        const data = fs.readFileSync(KEYS_FILE, 'utf8');
        
        // Check if file is empty or only whitespace
        if (!data || data.trim() === '') {
            console.log('[Safe Hub] keys.json is empty, creating default');
            const defaultKeys = createDefaultKeys();
            fs.writeFileSync(KEYS_FILE, JSON.stringify(defaultKeys, null, 4));
            return defaultKeys;
        }
        
        // Try to parse JSON
        try {
            const parsed = JSON.parse(data);
            console.log('[Safe Hub] Successfully loaded keys.json');
            return parsed;
        } catch (parseError) {
            console.log('[Safe Hub] Invalid JSON in keys.json, recreating file');
            const defaultKeys = createDefaultKeys();
            fs.writeFileSync(KEYS_FILE, JSON.stringify(defaultKeys, null, 4));
            return defaultKeys;
        }
    } catch (error) {
        console.error('[Safe Hub] Error loading keys:', error.message);
        const defaultKeys = createDefaultKeys();
        try {
            fs.writeFileSync(KEYS_FILE, JSON.stringify(defaultKeys, null, 4));
            console.log('[Safe Hub] Recreated keys.json with default keys');
        } catch (e) {
            console.error('[Safe Hub] Failed to recreate keys.json:', e);
        }
        return defaultKeys;
    }
}

function createDefaultKeys() {
    // Generate a default test key
    const testKey = 'TEST' + Math.random().toString(36).substring(2, 8).toUpperCase();
    const defaultKeys = {};
    defaultKeys[testKey] = {
        "created_by": "system",
        "user_id": "system",
        "created_at": new Date().toISOString(),
        "expires_at": new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),
        "max_uses": 999,
        "uses": 0,
        "active": true,
        "duration_days": 365
    };
    console.log('[Safe Hub] Created default test key:', testKey);
    return defaultKeys;
}

function saveKeys(keys) {
    try {
        fs.writeFileSync(KEYS_FILE, JSON.stringify(keys, null, 4));
        console.log('[Safe Hub] Keys saved to:', KEYS_FILE);
    } catch (error) {
        console.error('[Safe Hub] Error saving keys:', error);
    }
}

function validateKey(key) {
    const keys = loadKeys();
    
    console.log('[Safe Hub] Validating key:', key);
    console.log('[Safe Hub] Available keys:', Object.keys(keys));
    
    if (!keys[key]) {
        return { valid: false, reason: 'Invalid key' };
    }
    
    const data = keys[key];
    const expiry = new Date(data.expires_at);
    const now = new Date();
    
    if (!data.active) {
        return { valid: false, reason: 'Key has been revoked' };
    }
    
    if (expiry < now) {
        return { valid: false, reason: 'Key has expired' };
    }
    
    if (data.uses >= data.max_uses) {
        return { valid: false, reason: 'Key has reached maximum uses' };
    }
    
    return { valid: true, data: data };
}

function useKey(key) {
    const keys = loadKeys();
    
    if (!keys[key]) {
        return false;
    }
    
    keys[key].uses += 1;
    saveKeys(keys);
    return true;
}

let serverData = {
    servers: []
};

app.post('/api/validate', (req, res) => {
    const { key } = req.body;
    
    console.log('[Safe Hub] Key validation attempt:', key);
    
    if (!key) {
        return res.json({ valid: false, reason: 'No key provided' });
    }
    
    const validation = validateKey(key);
    
    if (validation.valid) {
        useKey(key);
        console.log('[Safe Hub] Key validated successfully:', key);
        res.json({ valid: true, message: 'Key validated successfully' });
    } else {
        console.log('[Safe Hub] Key validation failed:', key, validation.reason);
        res.json({ valid: false, reason: validation.reason });
    }
});

app.get('/api/validate', (req, res) => {
    res.json({ valid: false, reason: 'Use POST method to validate keys' });
});

app.post('/api/update', (req, res) => {
    const data = req.body;
    const existingIndex = serverData.servers.findIndex(s => s.serverId === data.serverId);
    
    if (existingIndex !== -1) {
        serverData.servers[existingIndex] = data;
    } else {
        serverData.servers.push(data);
    }
    
    broadcastData();
    res.json({ status: 'ok' });
});

app.get('/api/servers', (req, res) => {
    res.json(serverData);
});

app.get('/api/command', (req, res) => {
    const serverId = req.query.serverId;
    const commands = [];
    
    res.json({ commands: commands });
});

app.post('/api/command/result', (req, res) => {
    res.json({ status: 'ok' });
});

app.get('/api/keys', (req, res) => {
    try {
        const keys = loadKeys();
        const keyList = Object.keys(keys).map(key => ({
            key: key,
            ...keys[key]
        }));
        res.json({ keys: keyList });
    } catch (error) {
        res.status(500).json({ error: 'Failed to load keys' });
    }
});

app.post('/api/addkey', (req, res) => {
    try {
        const { key, userId, maxUses } = req.body;
        const keys = loadKeys();
        
        if (keys[key]) {
            return res.json({ success: false, reason: 'Key already exists' });
        }
        
        const expiry = new Date();
        expiry.setDate(expiry.getDate() + 30);
        
        keys[key] = {
            'created_by': 'api',
            'user_id': userId || 'unknown',
            'created_at': new Date().toISOString(),
            'expires_at': expiry.toISOString(),
            'max_uses': maxUses || 1,
            'uses': 0,
            'active': true,
            'duration_days': 30
        };
        
        saveKeys(keys);
        res.json({ success: true, key: key });
    } catch (error) {
        res.status(500).json({ success: false, error: error.message });
    }
});

app.get('/test', (req, res) => {
    const keys = loadKeys();
    res.json({
        status: 'Server is running',
        port: PORT,
        keysFile: KEYS_FILE,
        environment: process.env.RAILWAY_ENVIRONMENT ? 'Railway' : 'Local',
        keyCount: Object.keys(keys).length,
        keys: Object.keys(keys)
    });
});

function broadcastData() {
    const message = JSON.stringify(serverData);
    wss.clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(message);
        }
    });
}

wss.on('connection', (ws) => {
    console.log('[Safe Hub] WebSocket client connected');
    ws.send(JSON.stringify(serverData));
});

const PORT = process.env.PORT || 8080;

server.listen(PORT, '0.0.0.0', () => {
    console.log('═══════════════════════════════════════════════════════');
    console.log('  SAFE HUB - Backend Server');
    console.log('═══════════════════════════════════════════════════════');
    console.log(`  Server listening on port ${PORT}`);
    console.log(`  Keys file: ${KEYS_FILE}`);
    console.log(`  Environment: ${process.env.RAILWAY_ENVIRONMENT ? 'Railway' : 'Local'}`);
    const keys = loadKeys();
    console.log(`  Total keys: ${Object.keys(keys).length}`);
    if (Object.keys(keys).length > 0) {
        console.log(`  Default test key: ${Object.keys(keys)[0]}`);
    }
    console.log('  Endpoints:');
    console.log(`    POST /api/validate - Validate a key`);
    console.log(`    GET  /api/servers  - Get server data`);
    console.log(`    POST /api/update   - Update server data`);
    console.log(`    GET  /api/keys     - List all keys`);
    console.log(`    POST /api/addkey   - Add a key manually`);
    console.log(`    GET  /test         - Test endpoint`);
    console.log('═══════════════════════════════════════════════════════');
});
