async function executeScript() {
    const serverId = $('execServerSelect').value;
    const player = $('execPlayerSelect').value;
    let script = $('scriptInput').value.trim();
    
    if (!serverId) {
        addConsoleLog('ERROR: Select a target server', 'error');
        return alert('Select a target server');
    }
    if (!script) {
        addConsoleLog('ERROR: Enter a script to execute', 'error');
        return alert('Enter a script to execute');
    }
    
    const playerName = player || linkedRobloxUser || 'username';
    script = script.replace(/username/g, playerName).replace(/usernamehere/g, playerName).replace(/urusernamehere/g, playerName);
    
    addConsoleLog(`Executing script on ${serverId}`, 'info');
    
    try {
        const response = await fetch(`${API_URL}/api/execute/direct`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                serverId: serverId,
                player: player || 'ALL',
                script: script
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            addConsoleLog(`✅ Script executed successfully!`, 'success');
            if (result.output) {
                // Show the output line by line
                const lines = result.output.split('\n');
                lines.forEach(line => {
                    if (line.trim()) {
                        addConsoleLog(`📝 ${line}`, 'info');
                    }
                });
            }
            alert('✅ Script executed! Check the console for output.');
        } else {
            addConsoleLog(`❌ Script failed: ${result.message}`, 'error');
            alert(`Script failed: ${result.message}`);
        }
    } catch (error) {
        addConsoleLog(`❌ Network error: ${error.message}`, 'error');
        alert(`Script failed: ${error.message}`);
    }
}
