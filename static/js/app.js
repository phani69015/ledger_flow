/**
 * LedgerFlow Frontend - API Client & UI Logic
 */

const API_BASE = '/api/v1';
let authToken = localStorage.getItem('ledgerflow_token');
let currentUser = null;

// ========================
// API Helper
// ========================
async function api(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = options.headers || {};
    
    if (authToken && !headers['Authorization']) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }
    
    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(url, { ...options, headers });
    
    if (response.status === 401) {
        logout();
        throw new Error('Session expired');
    }
    
    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || 'Request failed');
    }
    
    if (response.status === 204) return null;
    return response.json();
}

// ========================
// Auth Functions
// ========================
async function register(email, username, password) {
    const data = await api('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, username, password }),
    });
    showToast('Account created successfully! Please log in.', 'success');
    showLoginForm();
}

async function login(email, password) {
    const data = await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
    });
    authToken = data.access_token;
    localStorage.setItem('ledgerflow_token', authToken);
    await loadUser();
    showApp();
}

function logout() {
    authToken = null;
    currentUser = null;
    localStorage.removeItem('ledgerflow_token');
    showAuth();
}

async function loadUser() {
    try {
        currentUser = await api('/auth/me');
        updateUserUI();
    } catch (e) {
        logout();
    }
}

function updateUserUI() {
    if (!currentUser) return;
    document.getElementById('user-name').textContent = currentUser.username;
    document.getElementById('user-email').textContent = currentUser.email;
    document.getElementById('user-avatar').textContent = currentUser.username[0].toUpperCase();
}

// ========================
// Navigation
// ========================
function showAuth() {
    document.getElementById('auth-page').style.display = 'flex';
    document.getElementById('app-container').style.display = 'none';
}

function showApp() {
    document.getElementById('auth-page').style.display = 'none';
    document.getElementById('app-container').style.display = 'block';
    navigateTo('dashboard');
}

function showLoginForm() {
    document.getElementById('login-form').style.display = 'block';
    document.getElementById('register-form').style.display = 'none';
}

function showRegisterForm() {
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('register-form').style.display = 'block';
}

function navigateTo(page) {
    // Update nav
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    document.querySelector(`[data-page="${page}"]`)?.classList.add('active');
    
    // Show page section
    document.querySelectorAll('.page-section').forEach(el => el.classList.remove('active'));
    document.getElementById(`page-${page}`)?.classList.add('active');
    
    // Load page data
    switch (page) {
        case 'dashboard': loadDashboard(); break;
        case 'transactions': loadTransactions(); break;
        case 'upload': break;
        case 'anomalies': loadAnomalies(); break;
    }
}

// ========================
// Dashboard
// ========================
async function loadDashboard() {
    try {
        const [summary, trends] = await Promise.all([
            api('/analytics/summary?days=365'),
            api('/analytics/trends?months=6'),
        ]);
        
        renderStats(summary);
        renderTrendChart(trends);
        renderCategoryChart(summary.top_categories);
    } catch (e) {
        console.error('Dashboard load error:', e);
    }
}

function renderStats(summary) {
    document.getElementById('stat-total').textContent = summary.total_transactions.toLocaleString();
    document.getElementById('stat-income').textContent = `$${summary.total_income.toLocaleString()}`;
    document.getElementById('stat-expenses').textContent = `$${summary.total_expenses.toLocaleString()}`;
    document.getElementById('stat-balance').textContent = `$${summary.net_balance.toLocaleString()}`;
    
    const balanceEl = document.getElementById('stat-balance');
    balanceEl.style.color = summary.net_balance >= 0 ? 'var(--success)' : 'var(--danger)';
}

let trendChart = null;
function renderTrendChart(trends) {
    const ctx = document.getElementById('trend-chart').getContext('2d');
    
    if (trendChart) trendChart.destroy();
    
    trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: trends.map(t => t.month),
            datasets: [
                {
                    label: 'Income',
                    data: trends.map(t => t.income),
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.4,
                },
                {
                    label: 'Expenses',
                    data: trends.map(t => t.expenses),
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    fill: true,
                    tension: 0.4,
                },
            ],
        },
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: '#94a3b8' } },
            },
            scales: {
                x: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } },
                y: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } },
            },
        },
    });
}

let categoryChart = null;
function renderCategoryChart(categories) {
    const ctx = document.getElementById('category-chart').getContext('2d');
    
    if (categoryChart) categoryChart.destroy();
    
    if (!categories || categories.length === 0) {
        ctx.font = '14px Inter';
        ctx.fillStyle = '#94a3b8';
        ctx.textAlign = 'center';
        ctx.fillText('No data yet', ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }
    
    const colors = [
        '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316',
        '#eab308', '#22c55e', '#14b8a6', '#06b6d4', '#3b82f6',
    ];
    
    categoryChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: categories.map(c => c.category),
            datasets: [{
                data: categories.map(c => c.total_amount),
                backgroundColor: colors.slice(0, categories.length),
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#94a3b8', padding: 12, font: { size: 11 } },
                },
            },
        },
    });
}

// ========================
// Transactions
// ========================
async function loadTransactions(filters = {}) {
    try {
        let query = '?limit=50';
        if (filters.category) query += `&category=${encodeURIComponent(filters.category)}`;
        if (filters.type) query += `&transaction_type=${filters.type}`;
        if (filters.anomalies) query += `&anomalies_only=true`;
        
        const transactions = await api(`/transactions/${query}`);
        renderTransactions(transactions);
    } catch (e) {
        console.error('Transactions load error:', e);
    }
}

function renderTransactions(transactions) {
    const tbody = document.getElementById('transactions-tbody');
    
    if (!transactions || transactions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:2rem;color:var(--text-secondary)">No transactions found. Upload a CSV or JSON file to get started.</td></tr>`;
        return;
    }
    
    tbody.innerHTML = transactions.map(txn => `
        <tr>
            <td>${new Date(txn.date).toLocaleDateString()}</td>
            <td>${txn.description}</td>
            <td style="color: ${txn.transaction_type === 'credit' ? 'var(--success)' : 'var(--danger)'}; font-weight: 600;">
                ${txn.transaction_type === 'credit' ? '+' : '-'}$${txn.amount.toLocaleString()}
            </td>
            <td><span class="badge badge-category">${txn.category || 'N/A'}</span></td>
            <td><span class="badge badge-${txn.transaction_type}">${txn.transaction_type}</span></td>
            <td>${txn.is_anomaly ? '<span class="badge badge-anomaly">Anomaly</span>' : '-'}</td>
        </tr>
    `).join('');
}

// ========================
// File Upload (Two-Step Flow)
// ========================
let selectedFile = null;

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function showUploadStep(step) {
    document.getElementById('upload-step1').style.display = step === 1 ? 'block' : 'none';
    document.getElementById('upload-step2').style.display = step === 2 ? 'block' : 'none';
    document.getElementById('upload-step3').style.display = step === 3 ? 'block' : 'none';
    document.getElementById('upload-step4').style.display = step === 4 ? 'block' : 'none';
}

function onFileSelected(file) {
    if (!file) return;
    
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['csv', 'json', 'xlsx', 'xls'].includes(ext)) {
        showToast('Unsupported file format. Use CSV, JSON, or XLSX.', 'error');
        return;
    }
    
    selectedFile = file;
    document.getElementById('file-name').textContent = file.name;
    document.getElementById('file-size').textContent = formatFileSize(file.size);
    showUploadStep(2);
}

function resetUpload() {
    selectedFile = null;
    document.getElementById('file-input').value = '';
    showUploadStep(1);
    // Reset progress steps
    const steps = ['step-parse', 'step-validate', 'step-categorize', 'step-anomaly', 'step-done'];
    steps.forEach(id => {
        const el = document.getElementById(id);
        el.classList.remove('active', 'completed');
        el.querySelector('.step-icon').className = 'step-icon step-pending';
    });
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('progress-percent').textContent = '0%';
}

function setStepState(stepId, state) {
    const el = document.getElementById(stepId);
    const icon = el.querySelector('.step-icon');
    
    el.classList.remove('active', 'completed');
    icon.className = 'step-icon';
    
    if (state === 'active') {
        el.classList.add('active');
        icon.classList.add('step-active');
    } else if (state === 'done') {
        el.classList.add('completed');
        icon.classList.add('step-done');
    } else {
        icon.classList.add('step-pending');
    }
}

function setProgress(percent, title) {
    document.getElementById('progress-bar').style.width = percent + '%';
    document.getElementById('progress-percent').textContent = percent + '%';
    if (title) document.getElementById('progress-title').textContent = title;
}

async function processFile() {
    if (!selectedFile) return;
    
    showUploadStep(3);
    
    const steps = ['step-parse', 'step-validate', 'step-categorize', 'step-anomaly', 'step-done'];
    
    // Simulate progress stages while the API processes
    // (The actual API does all stages in one call, but we animate the steps)
    
    // Stage 1: Parsing
    setStepState('step-parse', 'active');
    setProgress(10, 'Parsing file...');
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    // Start a progress animation that runs while waiting for the API
    let currentProgress = 10;
    const progressInterval = setInterval(() => {
        if (currentProgress < 85) {
            currentProgress += Math.random() * 3;
            setProgress(Math.min(Math.round(currentProgress), 85));
            
            // Update step states based on progress
            if (currentProgress > 20) {
                setStepState('step-parse', 'done');
                setStepState('step-validate', 'active');
                setProgress(Math.round(currentProgress), 'Validating & cleaning data...');
            }
            if (currentProgress > 40) {
                setStepState('step-validate', 'done');
                setStepState('step-categorize', 'active');
                setProgress(Math.round(currentProgress), 'Running AI categorization...');
            }
            if (currentProgress > 65) {
                setStepState('step-categorize', 'done');
                setStepState('step-anomaly', 'active');
                setProgress(Math.round(currentProgress), 'Detecting anomalies...');
            }
        }
    }, 800);
    
    try {
        const result = await api('/transactions/upload', {
            method: 'POST',
            body: formData,
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
        
        // API finished - complete all steps
        clearInterval(progressInterval);
        
        setStepState('step-parse', 'done');
        setStepState('step-validate', 'done');
        setStepState('step-categorize', 'done');
        setStepState('step-anomaly', 'done');
        setStepState('step-done', 'done');
        setProgress(100, 'Processing complete!');
        
        // Wait a moment then show results
        await new Promise(r => setTimeout(r, 800));
        
        showUploadStep(4);
        document.getElementById('result-total').textContent = result.total_records.toLocaleString();
        document.getElementById('result-success').textContent = result.successful.toLocaleString();
        document.getElementById('result-duplicates').textContent = result.duplicates_skipped.toLocaleString();
        document.getElementById('result-anomalies').textContent = result.anomalies_detected.toLocaleString();
        document.getElementById('result-categories').textContent = result.categories_assigned.toLocaleString();
        
        showToast(result.message, 'success');
        
    } catch (e) {
        clearInterval(progressInterval);
        showUploadStep(1);
        showToast(e.message || 'Processing failed', 'error');
    }
}

// ========================
// Anomalies
// ========================
async function loadAnomalies() {
    try {
        const data = await api('/analytics/anomalies');
        renderAnomalies(data.anomalies);
    } catch (e) {
        console.error('Anomalies load error:', e);
    }
}

function renderAnomalies(anomalies) {
    const container = document.getElementById('anomalies-list');
    
    if (!anomalies || anomalies.length === 0) {
        container.innerHTML = '<p style="text-align:center;color:var(--text-secondary);padding:2rem;">No anomalies detected. Upload more transactions for analysis.</p>';
        return;
    }
    
    container.innerHTML = anomalies.map(a => `
        <div class="anomaly-item">
            <div class="anomaly-info">
                <h4>${a.description}</h4>
                <p>${new Date(a.date).toLocaleDateString()} &middot; $${a.amount.toLocaleString()} &middot; ${a.category || 'Uncategorized'}</p>
                <p style="color:var(--warning);margin-top:0.25rem;">${a.anomaly_reason}</p>
            </div>
            <div class="anomaly-score">${(a.anomaly_score * 100).toFixed(0)}%</div>
        </div>
    `).join('');
}

// ========================
// Toast Notifications
// ========================
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ========================
// Initialization
// ========================
document.addEventListener('DOMContentLoaded', () => {
    // Auth form handlers
    document.getElementById('login-submit').addEventListener('click', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        
        if (!email || !password) {
            showToast('Please fill in all fields', 'error');
            return;
        }
        
        try {
            await login(email, password);
        } catch (e) {
            showToast(e.message, 'error');
        }
    });
    
    document.getElementById('register-submit').addEventListener('click', async (e) => {
        e.preventDefault();
        const email = document.getElementById('register-email').value;
        const username = document.getElementById('register-username').value;
        const password = document.getElementById('register-password').value;
        
        if (!email || !username || !password) {
            showToast('Please fill in all fields', 'error');
            return;
        }
        
        try {
            await register(email, username, password);
        } catch (e) {
            showToast(e.message, 'error');
        }
    });
    
    // Navigation
    document.querySelectorAll('.nav-item').forEach(el => {
        el.addEventListener('click', () => navigateTo(el.dataset.page));
    });
    
    // Logout
    document.getElementById('logout-btn').addEventListener('click', logout);
    
    // File upload - drag and drop
    const uploadZone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    
    uploadZone.addEventListener('click', () => fileInput.click());
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) onFileSelected(file);
    });
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) onFileSelected(file);
    });
    
    // Process button
    document.getElementById('process-btn').addEventListener('click', processFile);
    
    // Change file button
    document.getElementById('file-change-btn').addEventListener('click', resetUpload);
    
    // Upload another button
    document.getElementById('upload-another-btn').addEventListener('click', resetUpload);
    
    // Transaction filters
    document.getElementById('filter-type').addEventListener('change', (e) => {
        loadTransactions({ type: e.target.value });
    });
    
    // Check if user is already logged in
    if (authToken) {
        loadUser().then(() => {
            if (currentUser) showApp();
            else showAuth();
        });
    } else {
        showAuth();
    }
});
