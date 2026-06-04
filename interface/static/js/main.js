// ── Skin Picker ────────────────────────────────────────────────────────────

let searchTimeout = null;
let selectedSkin = null;

function initSkinPicker() {
    const searchInput = document.getElementById('skin-search');
    if (!searchInput) return;

    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        const q = searchInput.value.trim();
        if (q.length < 2) {
            document.getElementById('skin-results').innerHTML = '';
            return;
        }
        searchTimeout = setTimeout(() => searchSkins(q), 400);
    });
}

async function searchSkins(q) {
    const grid = document.getElementById('skin-results');
    grid.innerHTML = '<div style="color:var(--text-muted);font-size:.85rem;padding:8px 0">Szukam...</div>';

    try {
        const resp = await fetch(`/api/search/steam?q=${encodeURIComponent(q)}&count=20`);
        const results = await resp.json();

        if (!results.length) {
            grid.innerHTML = '<div style="color:var(--text-muted);font-size:.85rem;padding:8px 0">Brak wyników</div>';
            return;
        }

        grid.innerHTML = results.map(skin => `
            <div class="skin-card" onclick="selectSkin(this)"
                 data-name="${escHtml(skin.name)}"
                 data-icon="${escHtml(skin.icon_url)}"
                 data-type="${escHtml(skin.item_type)}"
                 data-wear="${escHtml(skin.wear || '')}">
                ${skin.icon_url
                    ? `<img src="${escHtml(skin.icon_url)}" alt="${escHtml(skin.name)}" loading="lazy">`
                    : '<div style="height:78px;display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:1.5rem">?</div>'
                }
                <div class="skin-name">${escHtml(skin.name)}</div>
                <div class="skin-meta">${escHtml(skin.wear || skin.item_type || '')}</div>
            </div>
        `).join('');
    } catch (e) {
        grid.innerHTML = '<div style="color:var(--accent);font-size:.85rem;padding:8px 0">Błąd wyszukiwania</div>';
    }
}

function selectSkin(card) {
    document.querySelectorAll('.skin-card.selected').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');

    selectedSkin = {
        name: card.dataset.name,
        icon: card.dataset.icon,
        wear: card.dataset.wear,
        type: card.dataset.type,
    };

    document.getElementById('selected-name').value = selectedSkin.name;

    const preview = document.getElementById('selected-preview');
    if (preview) {
        preview.style.display = 'flex';
        preview.querySelector('.preview-img').src = selectedSkin.icon || '';
        preview.querySelector('.preview-img').style.display = selectedSkin.icon ? '' : 'none';
        preview.querySelector('.preview-name').textContent = selectedSkin.name;
        preview.querySelector('.preview-meta').textContent = selectedSkin.wear || selectedSkin.type || '';
    }
}

function escHtml(str) {
    return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Price History Chart ───────────────────────────────────────────────────

function initPriceChart(itemName) {
    const canvas = document.getElementById('price-chart');
    if (!canvas || typeof Chart === 'undefined') return;

    fetch(`/api/prices/${encodeURIComponent(itemName)}?limit=200`)
        .then(r => r.json())
        .then(data => {
            if (!data.length) {
                canvas.parentElement.innerHTML = '<p class="text-muted" style="padding:20px 0">Brak historii cen. Kolejkuj zadanie <em>history</em> w scraperze.</p>';
                return;
            }

            const labels = data.map(p => {
                const d = new Date(p.timestamp);
                return d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short', year: '2-digit' });
            });
            const prices = data.map(p => p.price);
            const volumes = data.map(p => p.volume || 0);

            new Chart(canvas, {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        {
                            label: 'Cena (USD)',
                            data: prices,
                            borderColor: '#e94560',
                            backgroundColor: 'rgba(233,69,96,0.08)',
                            borderWidth: 2,
                            pointRadius: data.length > 60 ? 0 : 3,
                            pointHoverRadius: 5,
                            fill: true,
                            tension: 0.3,
                            yAxisID: 'y',
                        },
                        {
                            label: 'Wolumen',
                            data: volumes,
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59,130,246,0.06)',
                            borderWidth: 1.5,
                            pointRadius: 0,
                            fill: true,
                            tension: 0.3,
                            yAxisID: 'y2',
                        },
                    ],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: {
                            labels: { color: '#6b7db3', font: { size: 11 } },
                        },
                        tooltip: {
                            backgroundColor: '#131d35',
                            borderColor: '#1e2d50',
                            borderWidth: 1,
                            titleColor: '#e8eaf6',
                            bodyColor: '#6b7db3',
                            callbacks: {
                                label: ctx => ctx.datasetIndex === 0
                                    ? ` $${ctx.raw.toFixed(2)}`
                                    : ` vol: ${ctx.raw}`,
                            },
                        },
                    },
                    scales: {
                        x: {
                            ticks: {
                                color: '#6b7db3', font: { size: 10 },
                                maxTicksLimit: 10, maxRotation: 0,
                            },
                            grid: { color: 'rgba(30,45,80,0.4)' },
                        },
                        y: {
                            position: 'left',
                            ticks: { color: '#6b7db3', font: { size: 10 }, callback: v => `$${v}` },
                            grid: { color: 'rgba(30,45,80,0.4)' },
                        },
                        y2: {
                            position: 'right',
                            ticks: { color: '#3b82f6', font: { size: 10 } },
                            grid: { drawOnChartArea: false },
                        },
                    },
                },
            });
        })
        .catch(() => {
            canvas.parentElement.innerHTML = '<p class="text-muted" style="padding:20px 0">Błąd ładowania wykresu.</p>';
        });
}

// ── Live Listings ─────────────────────────────────────────────────────────

let liveRefreshInterval = null;
let liveCountdownInterval = null;
let liveRefreshSeconds = 30;
let liveCountdown = liveRefreshSeconds;
let livePaused = false;
let liveSortKey = 'price';
let liveSortAsc = true;
let liveData = [];

function initLiveListings(itemName) {
    if (!document.getElementById('live-table-body')) return;

    loadLiveListings(itemName);

    liveRefreshInterval = setInterval(() => {
        if (!livePaused) {
            liveCountdown--;
            updateCountdown();
            if (liveCountdown <= 0) {
                liveCountdown = liveRefreshSeconds;
                loadLiveListings(itemName);
            }
        }
    }, 1000);

    document.getElementById('btn-refresh').addEventListener('click', () => {
        liveCountdown = liveRefreshSeconds;
        loadLiveListings(itemName);
    });

    document.getElementById('btn-pause').addEventListener('click', () => {
        livePaused = !livePaused;
        document.getElementById('btn-pause').textContent = livePaused ? 'Wznów' : 'Pauza';
        document.querySelector('.refresh-dot').style.animationPlayState = livePaused ? 'paused' : 'running';
    });

    document.querySelectorAll('.sort-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const key = btn.dataset.sort;
            if (liveSortKey === key) {
                liveSortAsc = !liveSortAsc;
            } else {
                liveSortKey = key;
                liveSortAsc = key === 'price';
            }
            document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            btn.textContent = btn.dataset.label + (liveSortAsc ? ' ↑' : ' ↓');
            renderLiveTable();
        });
    });
}

async function loadLiveListings(itemName) {
    const tbody = document.getElementById('live-table-body');
    const countEl = document.getElementById('live-count');

    tbody.innerHTML = `<tr class="loading-row"><td colspan="6"><span class="spinner"></span> Pobieram oferty...</td></tr>`;

    try {
        const resp = await fetch(`/api/live-listings/${encodeURIComponent(itemName)}`);
        const json = await resp.json();
        liveData = json.listings || [];

        if (countEl) countEl.textContent = liveData.length;
        liveCountdown = liveRefreshSeconds;
        updateCountdown();
        renderLiveTable();
    } catch (e) {
        tbody.innerHTML = `<tr class="loading-row"><td colspan="6" style="color:var(--accent)">Błąd pobierania ofert</td></tr>`;
    }
}

function renderLiveTable() {
    const tbody = document.getElementById('live-table-body');
    if (!liveData.length) {
        tbody.innerHTML = `<tr class="loading-row"><td colspan="6">Brak aktywnych ofert</td></tr>`;
        return;
    }

    const WEAR_ORDER = {'Factory New':0,'Minimal Wear':1,'Field-Tested':2,'Well-Worn':3,'Battle-Scarred':4};

    const sorted = [...liveData].sort((a, b) => {
        let va = a[liveSortKey], vb = b[liveSortKey];
        if (va == null) return liveSortAsc ? 1 : -1;
        if (vb == null) return liveSortAsc ? -1 : 1;
        if (liveSortKey === 'wear') {
            const oa = WEAR_ORDER[va] ?? 99, ob = WEAR_ORDER[vb] ?? 99;
            return liveSortAsc ? oa - ob : ob - oa;
        }
        return liveSortAsc ? va - vb : vb - va;
    });

    tbody.innerHTML = sorted.map(l => {
        const wearBadge = wearClass(l.wear);
        const stickersHtml = l.stickers && l.stickers.length
            ? `<div class="sticker-list">${l.stickers.map(s => `<span class="sticker-chip">${escHtml(s)}</span>`).join('')}</div>`
            : '<span class="text-muted text-xs">–</span>';

        const inspectHtml = l.inspect_link
            ? `<a href="${escHtml(l.inspect_link)}" class="inspect-btn" title="Inspect in Game">
                   <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                   Inspect
               </a>`
            : '–';

        return `<tr>
            <td class="text-danger text-bold text-mono">$${l.price.toFixed(2)}</td>
            <td>${l.wear ? `<span class="badge ${wearBadge}">${escHtml(l.wear)}</span>` : '–'}</td>
            <td class="text-mono text-sm">${l.float_value != null ? l.float_value.toFixed(8) : '<span class="text-muted">–</span>'}</td>
            <td>${stickersHtml}</td>
            <td>${inspectHtml}</td>
            <td>
                <a href="https://steamcommunity.com/market/listings/730/${encodeURIComponent(document.getElementById('item-name-data').dataset.name)}"
                   target="_blank" class="btn btn-ghost btn-sm">Steam</a>
            </td>
        </tr>`;
    }).join('');
}

function wearClass(wear) {
    const map = {
        'Factory New': 'badge-fn',
        'Minimal Wear': 'badge-mw',
        'Field-Tested': 'badge-ft',
        'Well-Worn': 'badge-ww',
        'Battle-Scarred': 'badge-bs',
    };
    return map[wear] || 'badge-steam';
}

function updateCountdown() {
    const el = document.getElementById('countdown-val');
    if (el) el.textContent = liveCountdown;
}

// ── Init ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initSkinPicker();
});
