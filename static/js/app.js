/**
 * app.js — Shared Alpine.js utilities and helpers
 */

// ─── Utility: debounce ──────────────────────────────────────────────────────
function debounce(fn, ms = 300) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), ms);
    };
}

// ─── Utility: format datetime ────────────────────────────────────────────────
function formatTime(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// ─── Utility: ability modifier ──────────────────────────────────────────────
function abilityMod(score) {
    return Math.floor((score - 10) / 2);
}

function formatMod(score) {
    const m = abilityMod(score);
    return (m >= 0 ? '+' : '') + m;
}

// ─── Dice roller helper ─────────────────────────────────────────────────────
async function quickRoll(notation = 'd20') {
    const res = await fetch('/api/dice/roll', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notation }),
    });
    return await res.json();
}

// ─── Toast notification helper ──────────────────────────────────────────────
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    const colors = {
        info:    'bg-blue-800 border-blue-600',
        success: 'bg-green-800 border-green-600',
        error:   'bg-red-800 border-red-600',
        warning: 'bg-yellow-800 border-yellow-600',
    };
    toast.className = `fixed bottom-4 right-4 z-50 px-4 py-3 rounded-lg border text-white text-sm shadow-lg
                       transition-opacity duration-300 ${colors[type] || colors.info}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
