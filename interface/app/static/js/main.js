// ── Currency ──────────────────────────────────────────────────────────────

let exchangeRates = { USD: 1.0, EUR: 0.92, PLN: 3.95, BTC: 0 };
let currentCurrency = localStorage.getItem('smt_currency') || 'USD';
let priceChart = null;

const CURRENCY_SYMBOLS  = { USD: '$', EUR: '€', PLN: 'zł', BTC: '₿' };
const CURRENCY_DECIMALS = { USD: 2,   EUR: 2,   PLN: 2,    BTC: 6   };

function formatPrice(usdPrice) {
    const rate = exchangeRates[currentCurrency] ?? 1;
    const val  = usdPrice * rate;
    const dec  = CURRENCY_DECIMALS[currentCurrency] ?? 2;
    const sym  = CURRENCY_SYMBOLS[currentCurrency]  ?? '$';
    if (currentCurrency === 'PLN') return `${val.toFixed(dec)} ${sym}`;
    return `${sym}${val.toFixed(dec)}`;
}

function applyCurrentCurrency() {
    // big price box on item_detail
    const priceEl = document.getElementById('price-value-display');
    if (priceEl) {
        const usd = parseFloat(priceEl.dataset.usd);
        if (!isNaN(usd)) priceEl.textContent = formatPrice(usd);
    }

    // static listing price cells in item_detail
    document.querySelectorAll('.price-cell[data-usd]').forEach(td => {
        const usd = parseFloat(td.dataset.usd);
        if (!isNaN(usd)) td.textContent = formatPrice(usd);
    });

    // live listings table
    if (liveData.length) renderLiveTable();

    // chart
    if (priceChart) {
        priceChart.data.datasets[0].label = `Cena (${currentCurrency})`;
        priceChart.options.scales.y.ticks.callback = v => formatPrice(v);
        priceChart.options.plugins.tooltip.callbacks.label = ctx =>
            ctx.datasetIndex === 0 ? ` ${formatPrice(ctx.raw)}` : ` vol: ${ctx.raw}`;
        priceChart.update('none');
    }
}

async function initCurrencySelector() {
    // restore saved selection
    document.querySelectorAll('.currency-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.currency === currentCurrency);
    });

    // fetch live rates
    try {
        const resp = await fetch('/api/exchange-rates');
        if (resp.ok) Object.assign(exchangeRates, await resp.json());
    } catch (e) {
        console.warn('[currency] rate fetch failed, using defaults');
    }

    applyCurrentCurrency();

    document.querySelectorAll('.currency-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            currentCurrency = btn.dataset.currency;
            localStorage.setItem('smt_currency', currentCurrency);
            document.querySelectorAll('.currency-btn').forEach(b =>
                b.classList.toggle('active', b.dataset.currency === currentCurrency));
            applyCurrentCurrency();
        });
    });
}

// ── Skin Picker ────────────────────────────────────────────────────────────

let searchTimeout = null;
let selectedSkin  = null;

// Skin filter state
let skinWearFilter = null;    // null = all wears
let skinTypeFilter = null;    // null | 'stattrak' | 'souvenir'
let lastSearchResults = [];
const liveFloatCache = {};    // inspectUrl → {float_value, paint_seed}

function initSkinPicker() {
    const searchInput = document.getElementById('skin-search');
    if (!searchInput) return;

    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        const q = searchInput.value.trim();
        if (q.length < 2) {
            document.getElementById('skin-results').innerHTML = '';
            lastSearchResults = [];
            return;
        }
        searchTimeout = setTimeout(() => searchSkins(q), 400);
    });
}

async function searchSkins(q) {
    const grid = document.getElementById('skin-results');
    grid.innerHTML = '<div style="color:var(--text-muted);font-size:.85rem;padding:8px 0">Szukam...</div>';

    try {
        const resp    = await fetch(`/api/search/steam?q=${encodeURIComponent(q)}&count=20`);
        const results = await resp.json();

        lastSearchResults = results;

        if (!results.length) {
            grid.innerHTML = '<div style="color:var(--text-muted);font-size:.85rem;padding:8px 0">Brak wyników</div>';
            return;
        }

        renderSkinGrid(lastSearchResults);
    } catch (e) {
        grid.innerHTML = '<div style="color:var(--accent);font-size:.85rem;padding:8px 0">Błąd wyszukiwania</div>';
    }
}

function renderSkinGrid(results) {
    const grid = document.getElementById('skin-results');
    if (!grid) return;

    const filtered = results.filter(skin => {
        if (skinWearFilter && skin.wear !== skinWearFilter) return false;
        const isST   = skin.name.includes('StatTrak');
        const isSouv = skin.name.includes('Souvenir');
        if (skinTypeFilter === 'stattrak' && !isST)   return false;
        if (skinTypeFilter === 'souvenir' && !isSouv) return false;
        return true;
    });

    if (!filtered.length) {
        grid.innerHTML = '<div style="color:var(--text-muted);font-size:.85rem;padding:8px 0">Brak wyników</div>';
        return;
    }

    grid.innerHTML = filtered.map(skin => `
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
}

function initWearFilters() {
    const wearFiltersEl = document.getElementById('skin-wear-filters');
    if (!wearFiltersEl) return;

    wearFiltersEl.querySelectorAll('.wear-chip[data-wear]').forEach(chip => {
        chip.addEventListener('click', () => {
            const wear = chip.dataset.wear;
            if (skinWearFilter === wear) {
                skinWearFilter = null;
                chip.classList.remove('active');
            } else {
                skinWearFilter = wear;
                wearFiltersEl.querySelectorAll('.wear-chip[data-wear]').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
            }
            updateClearBtn();
            renderSkinGrid(lastSearchResults);
        });
    });

    wearFiltersEl.querySelectorAll('.wear-chip[data-type]').forEach(chip => {
        chip.addEventListener('click', () => {
            const type = chip.dataset.type;
            if (skinTypeFilter === type) {
                skinTypeFilter = null;
                chip.classList.remove('active');
            } else {
                skinTypeFilter = type;
                wearFiltersEl.querySelectorAll('.wear-chip[data-type]').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
            }
            updateClearBtn();
            renderSkinGrid(lastSearchResults);
        });
    });

    const clearBtn = document.getElementById('clear-wear-filter');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            skinWearFilter = null;
            skinTypeFilter = null;
            wearFiltersEl.querySelectorAll('.wear-chip').forEach(c => c.classList.remove('active'));
            clearBtn.style.display = 'none';
            renderSkinGrid(lastSearchResults);
        });
    }

    function updateClearBtn() {
        const clearBtn = document.getElementById('clear-wear-filter');
        if (clearBtn) clearBtn.style.display = (skinWearFilter || skinTypeFilter) ? '' : 'none';
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
        preview.querySelector('.preview-img').src           = selectedSkin.icon || '';
        preview.querySelector('.preview-img').style.display = selectedSkin.icon ? '' : 'none';
        preview.querySelector('.preview-name').textContent  = selectedSkin.name;
        preview.querySelector('.preview-meta').textContent  = selectedSkin.wear || selectedSkin.type || '';
    }
}

function escHtml(str) {
    return String(str || '')
        .replace(/&/g,'&amp;').replace(/</g,'&lt;')
        .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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

            const labels  = data.map(p => {
                const d = new Date(p.timestamp);
                return d.toLocaleDateString('pl-PL', { day:'numeric', month:'short', year:'2-digit' });
            });
            const prices  = data.map(p => p.price);
            const volumes = data.map(p => p.volume || 0);

            priceChart = new Chart(canvas, {
                type: 'line',
                data: {
                    labels,
                    datasets: [
                        {
                            label: `Cena (${currentCurrency})`,
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
                                    ? ` ${formatPrice(ctx.raw)}`
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
                            ticks: { color: '#6b7db3', font: { size: 10 }, callback: v => formatPrice(v) },
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

let liveRefreshInterval   = null;
let liveCountdownInterval = null;
let liveRefreshSeconds    = 30;
let liveCountdown         = liveRefreshSeconds;
let livePaused            = false;
let liveSortKey           = 'price';
let liveSortAsc           = true;
let liveData              = [];
let floatFetchInProgress  = false;

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
    const tbody   = document.getElementById('live-table-body');
    const countEl = document.getElementById('live-count');

    tbody.innerHTML = `<tr class="loading-row"><td colspan="7"><span class="spinner"></span> Pobieram oferty...</td></tr>`;

    try {
        const resp = await fetch(`/api/live-listings/${encodeURIComponent(itemName)}`);
        const json = await resp.json();
        liveData = json.listings || [];

        if (countEl) countEl.textContent = liveData.length;
        liveCountdown = liveRefreshSeconds;
        updateCountdown();
        renderLiveTable();
    } catch (e) {
        tbody.innerHTML = `<tr class="loading-row"><td colspan="7" style="color:var(--accent)">Błąd pobierania ofert</td></tr>`;
    }
}

function renderLiveTable() {
    const tbody = document.getElementById('live-table-body');
    if (!liveData.length) {
        tbody.innerHTML = `<tr class="loading-row"><td colspan="7">Brak aktywnych ofert</td></tr>`;
        return;
    }

    const WEAR_ORDER = {'Factory New':0,'Minimal Wear':1,'Field-Tested':2,'Well-Worn':3,'Battle-Scarred':4};

    const sorted = [...liveData].sort((a, b) => {
        let va, vb;
        if (liveSortKey === 'float_value') {
            va = (a.inspect_link && liveFloatCache[a.inspect_link] != null)
                ? liveFloatCache[a.inspect_link]?.float_value
                : a.float_value;
            vb = (b.inspect_link && liveFloatCache[b.inspect_link] != null)
                ? liveFloatCache[b.inspect_link]?.float_value
                : b.float_value;
        } else {
            va = a[liveSortKey];
            vb = b[liveSortKey];
        }
        if (va == null) return liveSortAsc ? 1 : -1;
        if (vb == null) return liveSortAsc ? -1 : 1;
        if (liveSortKey === 'wear') {
            const oa = WEAR_ORDER[va] ?? 99, ob = WEAR_ORDER[vb] ?? 99;
            return liveSortAsc ? oa - ob : ob - oa;
        }
        return liveSortAsc ? va - vb : vb - va;
    });

    tbody.innerHTML = sorted.map(l => {
        const wearBadge    = wearClass(l.wear);
        const stickersHtml = l.stickers && l.stickers.length
            ? `<div class="sticker-list">${l.stickers.map(s => `<span class="sticker-chip">${escHtml(s)}</span>`).join('')}</div>`
            : '<span class="text-muted text-xs">–</span>';

        const inspectHtml = l.inspect_link
            ? `<a href="${escHtml(l.inspect_link)}" class="inspect-btn" title="Inspect in Game">
                   <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                   Inspect
               </a>`
            : '–';

        // Float cell
        const cachedFloat = l.inspect_link ? liveFloatCache[l.inspect_link] : undefined;
        let floatDisplay;
        if (cachedFloat != null && cachedFloat.float_value != null) {
            floatDisplay = cachedFloat.float_value.toFixed(7);
        } else if (l.float_value != null) {
            floatDisplay = l.float_value.toFixed(7);
        } else if (l.inspect_link && !(l.inspect_link in liveFloatCache)) {
            floatDisplay = '<span class="float-loading text-muted text-xs">...</span>';
        } else {
            floatDisplay = '<span class="text-muted">–</span>';
        }

        // Pattern cell
        let patternDisplay;
        if (cachedFloat != null && cachedFloat.paint_seed != null) {
            patternDisplay = cachedFloat.paint_seed;
        } else if (l.paint_seed != null) {
            patternDisplay = l.paint_seed;
        } else {
            patternDisplay = '<span class="text-muted">–</span>';
        }

        return `<tr>
            <td class="text-danger text-bold text-mono">${formatPrice(l.price)}</td>
            <td>${l.wear ? `<span class="badge ${wearBadge}">${escHtml(l.wear)}</span>` : '–'}</td>
            <td class="text-mono text-sm float-cell" data-inspect="${escHtml(l.inspect_link || '')}">${floatDisplay}</td>
            <td class="text-mono text-sm pattern-cell" data-inspect="${escHtml(l.inspect_link || '')}">${patternDisplay}</td>
            <td>${stickersHtml}</td>
            <td>${inspectHtml}</td>
            <td>
                <a href="https://steamcommunity.com/market/listings/730/${encodeURIComponent(document.getElementById('item-name-data').dataset.name)}"
                   target="_blank" class="btn btn-ghost btn-sm">Steam</a>
            </td>
        </tr>`;
    }).join('');

    // Trigger lazy float loading after rendering
    autoFetchFloats();
}

async function autoFetchFloats() {
    if (floatFetchInProgress) return;
    floatFetchInProgress = true;

    try {
        // Get listings that have inspect links but no cached float
        const pending = liveData.filter(l =>
            l.inspect_link &&
            !(l.inspect_link in liveFloatCache)
        ).slice(0, 15); // max 15 at a time

        for (const item of pending) {
            if (!item.inspect_link) continue;
            const url = item.inspect_link;
            liveFloatCache[url] = null; // mark as in-progress so we don't retry
            try {
                const resp = await fetch(`/api/inspect-float?url=${encodeURIComponent(url)}`);
                if (resp.ok) {
                    const data = await resp.json();
                    liveFloatCache[url] = data;
                    // Update DOM cells with matching data-inspect
                    document.querySelectorAll('.float-cell').forEach(el => {
                        if (el.dataset.inspect === url && data.float_value != null) {
                            el.textContent = data.float_value.toFixed(7);
                        }
                    });
                    document.querySelectorAll('.pattern-cell').forEach(el => {
                        if (el.dataset.inspect === url && data.paint_seed != null) {
                            el.textContent = data.paint_seed;
                        }
                    });
                }
            } catch {}
            await new Promise(r => setTimeout(r, 300)); // 300ms between CSFloat calls
        }
    } finally {
        floatFetchInProgress = false;
    }
}

function wearClass(wear) {
    const map = {
        'Factory New':   'badge-fn',
        'Minimal Wear':  'badge-mw',
        'Field-Tested':  'badge-ft',
        'Well-Worn':     'badge-ww',
        'Battle-Scarred':'badge-bs',
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
    initCurrencySelector();
    initWearFilters();
});
