let currentApis = [];
let networkData = null;
let initialZombieCount = null;

async function startScan() {
    // UI states Update
    const btn = document.getElementById('scanBtn');
    btn.disabled = true;
    btn.querySelector('.btn-text').innerText = 'SCANNING...';
    
    document.getElementById('loadingOverlay').classList.remove('hidden');
    document.getElementById('statsGrid').classList.add('hidden');
    document.getElementById('dashboardGrid').classList.add('hidden');
    document.getElementById('newApiBanner').classList.add('hidden');
    document.getElementById('newApiCount').innerText = '0';
    
    try {
        const response = await fetch('/scan', { method: 'POST' });
        const result = await response.json();
        
        if (result.status === 'success') {
            currentApis = result.data;
            renderDashboard();
            showToast('Scan completed. Risks identified.');
        } else {
            showToast('Scan failed: ' + result.message, true);
        }
    } catch (e) {
        showToast('Connection Error. Ensure Backend is running.', true);
    } finally {
        btn.disabled = false;
        btn.querySelector('.btn-text').innerText = 'INITIATE DEEP SCAN';
        document.getElementById('loadingOverlay').classList.add('hidden');
    }
}

function renderDashboard() {
    document.getElementById('statsGrid').classList.remove('hidden');
    document.getElementById('dashboardGrid').classList.remove('hidden');
    
    const zombies = currentApis.filter(a => a.category === 'Zombie');
    const orphaned = currentApis.filter(a => a.category === 'Orphaned');
    
    if (initialZombieCount === null) {
        initialZombieCount = zombies.length;
    }
    
    // Calculate financial exposure using the AI/ML backend scores instead of static math
    const totalExposure = zombies.reduce((sum, api) => sum + (api.financial_exposure || 0), 0);
    const inMillions = totalExposure / 1000000;
    
    // As a fun hackathon aesthetic, pre-exposure is what we started with
    if (!window.initialExposureMillions) {
        window.initialExposureMillions = inMillions > 0 ? inMillions : (initialZombieCount * 4.45);
    }
    
    const preExposure = window.initialExposureMillions;
    const postExposureSecured = Math.max(0, preExposure - inMillions);

    // Animate numbers
    document.getElementById('statDiscovered').innerText = currentApis.length;
    document.getElementById('statZombies').innerText = zombies.length;
    document.getElementById('statPreExposure').innerText = `$${preExposure.toFixed(1)}M`;
    document.getElementById('statPostExposure').innerText = `$${postExposureSecured.toFixed(1)}M`;
    
    renderGraph();
    
    // Show highest risk items in list (Zombies + Top Orphaned)
    const riskyApis = currentApis.filter(a => a.ghost_score >= 5.0).sort((a,b) => b.ghost_score - a.ghost_score);
    renderList(riskyApis.slice(0, 50)); 
}

function renderList(apis) {
    const container = document.getElementById('zombieList');
    container.innerHTML = '';
    
    if(apis.length === 0) {
        container.innerHTML = '<p style="color: grey; padding: 1rem;">No critical risks found. Infrastructure secure.</p>';
        return;
    }
    
    apis.forEach(api => {
        const div = document.createElement('div');
        const isCritical = api.ghost_score >= 8.0;
        
        div.className = `list-item ${isCritical ? 'risk-critical' : 'risk-high'}`;
        div.onclick = () => openModal(api.id);
        
        div.innerHTML = `
            <div class="item-score">${api.ghost_score.toFixed(1)}</div>
            <div class="item-details">
                <h4>${api.method} ${api.endpoint}</h4>
                <div class="item-meta">Category: ${api.category} | Team: ${api.owner_team}</div>
            </div>
        `;
        container.appendChild(div);
    });
}

function renderGraph() {
    // Generate a Plotly Network Graph
    // 1. Core Nodes (Databases, Gateways)
    const cores = [
        { id: 'Gateway', x: 0, y: 0, type: 'core', symbol: 'diamond', size: 30, color: '#00f2fe' },
        { id: 'Users DB', x: -2, y: 2, type: 'core', symbol: 'square', size: 25, color: '#a5b4cb' },
        { id: 'Ledger DB', x: 2, y: 2, type: 'core', symbol: 'square', size: 25, color: '#a5b4cb' },
        { id: 'Auth Service', x: 0, y: -2, type: 'core', symbol: 'hexagram', size: 25, color: '#a5b4cb' }
    ];
    
    const nodesX = [];
    const nodesY = [];
    const nodesColor = [];
    const nodesSize = [];
    const nodesText = [];
    const nodesSymbol = [];
    
    // Add cores
    cores.forEach(c => {
        nodesX.push(c.x); nodesY.push(c.y); nodesColor.push(c.color); 
        nodesSize.push(c.size); nodesText.push(`[CORE] ${c.id}`); nodesSymbol.push(c.symbol);
    });
    
    const edgeX = [];
    const edgeY = [];
    
    // To avoid lag in UI, max 100 random API plotted + all zombies
    const zombies = currentApis.filter(a => a.category === 'Zombie');
    const others = currentApis.filter(a => a.category !== 'Zombie').slice(0, 100 - zombies.length);
    const plotApis = [...zombies, ...others];
    
    plotApis.forEach((api, i) => {
        // Random orbit based on category
        let radius, angle;
        let color = '#34c759'; // green via healthy
        let size = 12;
        
        if (api.category === 'Zombie') {
            radius = 3 + Math.random() * 2;
            color = '#ff3b30'; // red
            size = 20;
        } else if (api.category === 'Shadow') {
            radius = 2 + Math.random() * 2;
            color = '#ff9500'; // orange
            size = 16;
        } else {
            radius = 1 + Math.random() * 3;
        }
        
        angle = Math.random() * 2 * Math.PI;
        const nx = Math.cos(angle) * radius;
        const ny = Math.sin(angle) * radius;
        
        nodesX.push(nx); nodesY.push(ny); 
        nodesColor.push(color); nodesSize.push(size); 
        nodesText.push(`API: ${api.id}<br>Ghost Score: ${api.ghost_score}`);
        nodesSymbol.push('circle');
        
        // Connect to a random core service
        const core = cores[Math.floor(Math.random() * cores.length)];
        // Random business impact connect (Zombies connect to Ledger DB for impact!)
        const targetCore = (api.category === 'Zombie' && Math.random() > 0.5) ? cores[2] : core;
        
        edgeX.push(nx, targetCore.x, null);
        edgeY.push(ny, targetCore.y, null);
    });
    
    const edgeTrace = {
        x: edgeX, y: edgeY,
        line: { color: 'rgba(255, 255, 255, 0.1)', width: 1 },
        hoverinfo: 'none',
        type: 'scatter',
        mode: 'lines'
    };
    
    const nodeTrace = {
        x: nodesX, y: nodesY,
        text: nodesText,
        mode: 'markers',
        hoverinfo: 'text',
        marker: {
            symbol: nodesSymbol,
            size: nodesSize,
            color: nodesColor,
            line: { color: 'rgba(255, 255, 255, 0.5)', width: 1 }
        },
        type: 'scatter'
    };
    
    const layout = {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        showlegend: false,
        hovermode: 'closest',
        margin: { b: 0, l: 0, r: 0, t: 0 },
        xaxis: { showgrid: false, zeroline: false, showticklabels: false },
        yaxis: { showgrid: false, zeroline: false, showticklabels: false }
    };
    
    Plotly.newPlot('networkGraph', [edgeTrace, nodeTrace], layout, {displayModeBar: false, responsive: true});
    
    document.getElementById('networkGraph').on('plotly_click', function(data){
        var pt = (data.points || [])[0];
        if(!pt || !pt.text) return;
        var apiText = pt.text.split('<br>')[0];
        // text is "[CORE] Gateway" or "API: API_001"
        if(apiText.startsWith('API:')) {
            var id = apiText.split(': ')[1];
            if(id) openModal(id);
        }
    });
}

function openModal(id) {
    const api = currentApis.find(a => a.id === id);
    if(!api) return;
    
    document.getElementById('modalApiId').innerText = api.id + " ";
    document.getElementById('modalCategoryBadge').innerText = api.category.toUpperCase();
    
    // Category Badge Color
    const badge = document.getElementById('modalCategoryBadge');
    if (api.category === 'Zombie') { badge.style.color='red'; badge.style.borderColor='red'; badge.style.background='rgba(255,0,0,0.1)'; }
    else if (api.category === 'Orphaned') { badge.style.color='orange'; badge.style.borderColor='orange'; badge.style.background='rgba(255,165,0,0.1)'; }
    else { badge.style.color='#aaa'; badge.style.borderColor='#555'; badge.style.background='rgba(255,255,255,0.05)'; }
    
    document.getElementById('modalRiskScore').innerText = api.ghost_score.toFixed(1);
    
    // Posture UI
    document.getElementById('modalAuth').innerHTML = api.auth_type === 'None' ? '✗ None' : `✓ ${api.auth_type}`;
    document.getElementById('modalAuth').style.color = api.auth_type === 'None' ? '#ff6b81' : '#2ed573';
    
    document.getElementById('modalTls').innerHTML = api.https ? '✓ Active' : '✗ Missing';
    document.getElementById('modalTls').style.color = api.https ? '#2ed573' : '#ff6b81';
    
    document.getElementById('modalRate').innerHTML = api.rate_limited ? '✓ Active' : '✗ Missing';
    document.getElementById('modalRate').style.color = api.rate_limited ? '#2ed573' : '#ff6b81';
    
    document.getElementById('modalExposure').innerHTML = api.data_classification.includes('Confidential') ? '! PII Exposed' : `✓ ${api.data_classification}`;
    document.getElementById('modalExposure').style.color = api.data_classification.includes('Confidential') ? '#ff4757' : '#7bed9f';

    // Telemetry & Ownership
    document.getElementById('modalGit').innerText = api.git_blame || 'Unknown';
    document.getElementById('modalPipeline').innerText = api.pipeline_owner || 'Unknown';
    document.getElementById('modalSlack').innerText = api.slack_handle || 'Unknown';
    document.getElementById('modalStale').innerText = `${api.staleness_days} Days`;
    
    // Show Financial Impact
    if (api.financial_exposure) {
        document.getElementById('modalFinancial').innerText = `$${(api.financial_exposure/1e6).toFixed(2)}M`;
    } else {
        document.getElementById('modalFinancial').innerText = '$0.00M';
    }
    
    document.getElementById('modalLlmExplanation').innerText = api.llm_explanation || "No advanced context available.";
    
    // Reset animation blocks
    document.getElementById('nginxConfigSection').classList.add('hidden');
    document.getElementById('nginxConfigCode').innerText = '';
    document.getElementById('killShotAnimation').classList.add('hidden');
    ['ks-step1', 'ks-step2', 'ks-step3', 'ks-step4'].forEach(id => {
        const step = document.getElementById(id);
        step.style.color = '#888';
        step.children[0].style.borderColor = '#555';
        step.children[0].style.background = 'transparent';
        step.children[0].innerHTML = id.replace('ks-step', '');
    });
    
    document.getElementById('detailsModal').classList.remove('hidden');
}

function executeKillShot() {
    const animationBox = document.getElementById('killShotAnimation');
    animationBox.classList.remove('hidden');
    
    const steps = ['ks-step1', 'ks-step2', 'ks-step3', 'ks-step4'];
    let delay = 0;
    
    steps.forEach((stepId, index) => {
        setTimeout(() => {
            const el = document.getElementById(stepId);
            el.style.color = '#2ed573';
            el.children[0].style.borderColor = '#2ed573';
            el.children[0].style.background = 'rgba(46, 213, 115, 0.2)';
            el.children[0].innerHTML = '✓';
            
            if (index === steps.length - 1) {
                // Done animation, submit real decommission
                setTimeout(() => submitRemediation('decommission'), 500);
            }
        }, delay += 800);
    });
}

function closeModal() {
    document.getElementById('detailsModal').classList.add('hidden');
}

async function submitRemediation(action) {
    const modalText = document.getElementById('modalApiId').innerText;
    const apiId = modalText.split(" ")[0]; // ID is first part
    
    try {
        const res = await fetch(`/remediate/${action}/${apiId}`, { method: 'POST' });
        const result = await res.json();
        
        if (result.status === 'success') {
            showToast(result.message);
            
            if (action === 'decommission' || action === 'quarantine') {
                const configSect = document.getElementById('nginxConfigSection');
                const configCode = document.getElementById('nginxConfigCode');
                configCode.innerText = result.nginx_config || "Nginx Configuration Generation Failed";
                configSect.classList.remove('hidden');
                
                if (action === 'decommission') {
                    // Remove locally and re-render in background
                    currentApis = currentApis.filter(a => a.id !== apiId);
                    renderDashboard();
                } else if (action === 'whitelist') {
                    const ep = currentApis.find(a => a.id === apiId);
                    if(ep) {
                        ep.category = 'Active'; 
                        ep.ghost_score = 0;
                    }
                    renderDashboard();
                    closeModal();
                } else if (action === 'warn') {
                    closeModal();
                } else {
                    renderDashboard();
                }
            } else {
                closeModal();
            }
        }
    } catch(e) {
        showToast('Action failed: Cannot reach backend', true);
    }
}

function showToast(msg, isError=false) {
    const t = document.getElementById('toast');
    t.innerText = msg;
    t.style.borderColor = isError ? 'var(--color-zombie)' : 'var(--brand-neon)';
    t.classList.remove('hidden');
    setTimeout(() => {
        t.classList.add('hidden');
    }, 5000);
}

// Background WebSocket for Infrastructure Drift
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/diff`;
    const ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if(data.status === 'success' && data.new_apis_count > 0 && currentApis.length > 0) {
                const banner = document.getElementById('newApiBanner');
                const countSpan = document.getElementById('newApiCount');
                const currentCount = parseInt(countSpan.innerText) || 0;
                countSpan.innerText = currentCount + data.new_apis_count;
                banner.classList.remove('hidden');
            }
        } catch(e) { }
    };
    
    ws.onclose = () => {
        setTimeout(connectWebSocket, 5000); // Reconnect if dropped
    };
}
connectWebSocket();
