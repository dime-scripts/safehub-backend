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
        if (!fs.existsSync(KEYS_FILE)) {
            fs.writeFileSync(KEYS_FILE, JSON.stringify({}));
            console.log('[Safe Hub] Created new keys.json file');
            return {};
        }
        const data = fs.readFileSync(KEYS_FILE, 'utf8');
        return JSON.parse(data);
    } catch (error) {
        console.error('[Safe Hub] Error loading keys:', error);
        return {};
    }
}

function saveKeys(keys) {
    try {
        fs.writeFileSync(KEYS_FILE, JSON.stringify(keys, null, 4));
    } catch (error) {
        console.error('[Safe Hub] Error saving keys:', error);
    }
}

function validateKey(key) {
    const keys = loadKeys();
    
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

app.get('/test', (req, res) => {
    res.json({
        status: 'Server is running',
        port: PORT,
        keysFile: KEYS_FILE,
        environment: process.env.RAILWAY_ENVIRONMENT ? 'Railway' : 'Local'
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
    console.log('  Endpoints:');
    console.log(`    POST /api/validate - Validate a key`);
    console.log(`    GET  /api/servers  - Get server data`);
    console.log(`    POST /api/update   - Update server data`);
    console.log(`    GET  /api/keys     - List all keys`);
    console.log(`    GET  /test         - Test endpoint`);
    console.log('═══════════════════════════════════════════════════════');
});
