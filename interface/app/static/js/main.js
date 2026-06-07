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

// ── Browse / Scraper Page ─────────────────────────────────────────────────

const WEAPON_SUBS = {
    'Rifle': [
        {label:'AK-47',     tag:'tag_weapon_ak47'},
        {label:'M4A4',      tag:'tag_weapon_m4a1'},
        {label:'M4A1-S',    tag:'tag_weapon_m4a1_silencer'},
        {label:'AWP',       tag:'tag_weapon_awp'},
        {label:'SSG 08',    tag:'tag_weapon_ssg08'},
        {label:'SG 553',    tag:'tag_weapon_sg556'},
        {label:'AUG',       tag:'tag_weapon_aug'},
        {label:'FAMAS',     tag:'tag_weapon_famas'},
        {label:'Galil AR',  tag:'tag_weapon_galilar'},
        {label:'G3SG1',     tag:'tag_weapon_g3sg1'},
        {label:'SCAR-20',   tag:'tag_weapon_scar20'},
    ],
    'Pistol': [
        {label:'USP-S',         tag:'tag_weapon_usp_silencer'},
        {label:'Desert Eagle',  tag:'tag_weapon_deagle'},
        {label:'Glock-18',      tag:'tag_weapon_glock'},
        {label:'Five-SeveN',    tag:'tag_weapon_fiveseven'},
        {label:'P250',          tag:'tag_weapon_p250'},
        {label:'Tec-9',         tag:'tag_weapon_tec9'},
        {label:'P2000',         tag:'tag_weapon_hkp2000'},
        {label:'CZ75-Auto',     tag:'tag_weapon_cz75a'},
        {label:'Dual Berettas', tag:'tag_weapon_elite'},
        {label:'R8 Revolver',   tag:'tag_weapon_revolver'},
    ],
    'SMG': [
        {label:'MP9',    tag:'tag_weapon_mp9'},
        {label:'MAC-10', tag:'tag_weapon_mac10'},
        {label:'MP7',    tag:'tag_weapon_mp7'},
        {label:'PP-Bizon',tag:'tag_weapon_bizon'},
        {label:'P90',    tag:'tag_weapon_p90'},
        {label:'UMP-45', tag:'tag_weapon_ump45'},
        {label:'MP5-SD', tag:'tag_weapon_mp5sd'},
    ],
    'Shotgun,Machine Gun': [
        {label:'Nova',     tag:'tag_weapon_nova'},
        {label:'XM1014',   tag:'tag_weapon_xm1014'},
        {label:'Sawed-Off',tag:'tag_weapon_sawedoff'},
        {label:'MAG-7',    tag:'tag_weapon_mag7'},
        {label:'M249',     tag:'tag_weapon_m249'},
        {label:'Negev',    tag:'tag_weapon_negev'},
    ],
};

let browseState = {
    type:    '',
    weapon:  '',       // Steam weapon tag e.g. 'tag_weapon_ak47'
    wears:   new Set(['Factory New','Minimal Wear','Field-Tested','Well-Worn','Battle-Scarred']),
    quality: '',       // '' | 'tag_strange' | 'tag_tournament'
    start:   0,
    perPage: 48,
};

function initBrowse() {
    if (!document.getElementById('browse-grid')) return;

    document.querySelectorAll('.cat-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            browseState.type   = btn.dataset.type;
            browseState.weapon = '';
            browseState.start  = 0;
            updateWeaponTabs(btn.dataset.type);
            fetchBrowse();
        });
    });

    document.querySelectorAll('.wear-filter').forEach(cb => {
        cb.addEventListener('change', () => {
            browseState.wears = new Set(
                [...document.querySelectorAll('.wear-filter:checked')].map(c => c.value)
            );
            browseState.start = 0;
            fetchBrowse();
        });
    });

    document.querySelectorAll('.quality-filter').forEach(r => {
        r.addEventListener('change', () => {
            browseState.quality = r.value;
            browseState.start   = 0;
            fetchBrowse();
        });
    });

    document.getElementById('browse-prev').addEventListener('click', () => {
        if (browseState.start >= browseState.perPage) {
            browseState.start -= browseState.perPage;
            fetchBrowse();
        }
    });
    document.getElementById('browse-next').addEventListener('click', () => {
        browseState.start += browseState.perPage;
        fetchBrowse();
    });

    fetchBrowse();
}

function updateWeaponTabs(type) {
    const tabsEl = document.getElementById('weapon-tabs');
    const innerEl = document.getElementById('weapon-tab-inner');
    const subs = WEAPON_SUBS[type] || [];

    if (!subs.length) {
        tabsEl.style.display = 'none';
        browseState.weapon = '';
        return;
    }

    tabsEl.style.display = '';
    innerEl.innerHTML = [
        `<button class="weapon-tab active" data-tag="">Wszystko</button>`,
        ...subs.map(w => `<button class="weapon-tab" data-tag="${escHtml(w.tag)}">${escHtml(w.label)}</button>`)
    ].join('');

    innerEl.querySelectorAll('.weapon-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            innerEl.querySelectorAll('.weapon-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            browseState.weapon = tab.dataset.tag;
            browseState.start  = 0;
            fetchBrowse();
        });
    });
}

async function fetchBrowse() {
    const grid    = document.getElementById('browse-grid');
    const countEl = document.getElementById('browse-count');
    if (!grid) return;

    grid.innerHTML = '<div class="browse-loading"><span class="spinner"></span> Ładowanie...</div>';

    const params = new URLSearchParams({
        type:    browseState.type,
        weapon:  browseState.weapon,
        quality: browseState.quality,
        start:   browseState.start,
        count:   browseState.perPage,
    });
    [...browseState.wears].forEach(w => params.append('wear', w));

    try {
        const resp = await fetch(`/api/browse?${params}`);
        const data = await resp.json();
        const items = data.items || [];
        const total = data.total || 0;
        const currentPage = Math.floor((data.start || 0) / browseState.perPage) + 1;
        const totalPages  = Math.max(1, Math.ceil(total / browseState.perPage));

        countEl.textContent = `${total.toLocaleString('pl-PL')} wyników · Strona ${currentPage} / ${totalPages}`;

        if (!items.length) {
            grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><div class="empty-icon">🔍</div><p>Brak wyników. Wybierz inną kategorię lub zmień filtry.</p></div>';
            document.getElementById('browse-pagination').style.display = 'none';
            return;
        }

        grid.innerHTML = items.map(item => `
            <div class="skin-card browse-skin-card" onclick="openSkinModal(${escHtml(JSON.stringify(item.name))}, ${escHtml(JSON.stringify(item.icon_url || ''))})"
                 data-name="${escHtml(item.name)}" style="cursor:pointer;">
                ${item.icon_url
                    ? `<img src="${escHtml(item.icon_url)}" alt="${escHtml(item.name)}" loading="lazy">`
                    : '<div style="height:78px;display:flex;align-items:center;justify-content:center;color:var(--text-muted)">?</div>'
                }
                <div class="skin-name">${escHtml(item.name)}</div>
                <div class="skin-meta">${escHtml(item.wear || item.item_type || '')}</div>
            </div>
        `).join('');

        // Pagination
        const pagEl   = document.getElementById('browse-pagination');
        const prevBtn = document.getElementById('browse-prev');
        const nextBtn = document.getElementById('browse-next');
        pagEl.style.display = totalPages > 1 ? '' : 'none';
        prevBtn.disabled = browseState.start === 0;
        nextBtn.disabled = currentPage >= totalPages;
        document.getElementById('browse-page-info').textContent = `${currentPage} / ${totalPages}`;

    } catch (e) {
        grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><p style="color:var(--accent)">Błąd ładowania. Sprawdź połączenie.</p></div>';
    }
}

async function queueSkin(itemName) {
    // Queue all 3 scraping actions
    const actions = ['search', 'history', 'listings'];
    const card = document.querySelector(`.browse-skin-card[data-name="${CSS.escape(itemName)}"]`);
    if (card) card.classList.add('queued');

    try {
        await Promise.all(actions.map(action =>
            fetch('/api/queue/push', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({source: 'steam', action, item_name: itemName}),
            })
        ));
        showToast(`✓ Dodano do kolejki: ${itemName}`, 'success');
    } catch (e) {
        showToast('Błąd dodawania do kolejki', 'error');
        if (card) card.classList.remove('queued');
    }
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('queue-toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = `queue-toast queue-toast-${type}`;
    toast.style.display = 'block';
    clearTimeout(toast._hideTimeout);
    toast._hideTimeout = setTimeout(() => { toast.style.display = 'none'; }, 3500);
}

// ── Skin Detail Modal ─────────────────────────────────────────────────────

let modalCurrentSkin = null;

function openSkinModal(itemName, iconUrl) {
    modalCurrentSkin = { name: itemName, icon: iconUrl };

    const img = document.getElementById('modal-skin-img');
    img.src = iconUrl || '';
    img.style.display = iconUrl ? '' : 'none';

    document.getElementById('modal-skin-name').textContent = itemName;

    const wear  = extractWear(itemName);
    const isST  = itemName.includes('StatTrak');
    const isSouv = itemName.includes('Souvenir');
    const parts = [isST ? 'StatTrak™' : isSouv ? 'Souvenir' : null, wear].filter(Boolean);
    document.getElementById('modal-skin-meta').textContent = parts.join(' · ');

    document.getElementById('modal-detail-link').href = `/items/${encodeURIComponent(itemName)}`;
    document.getElementById('modal-steam-link').href  =
        `https://steamcommunity.com/market/listings/730/${encodeURIComponent(itemName)}`;

    const btn = document.getElementById('modal-track-btn');
    btn.disabled = false;
    btn.textContent = '+ Śledź ten skin';
    btn.style.background = '';

    document.getElementById('modal-listings-body').innerHTML =
        '<div class="browse-loading"><span class="spinner"></span> Ładowanie ofert...</div>';

    document.getElementById('skin-modal').style.display = 'flex';
    document.body.style.overflow = 'hidden';

    loadModalListings(itemName);
}

function closeSkinModal() {
    document.getElementById('skin-modal').style.display = 'none';
    document.body.style.overflow = '';
    modalCurrentSkin = null;
}

async function loadModalListings(itemName) {
    const body = document.getElementById('modal-listings-body');
    try {
        const resp     = await fetch(`/api/live-listings/${encodeURIComponent(itemName)}`);
        const data     = await resp.json();
        const listings = (data.listings || []).slice(0, 10);

        if (!listings.length) {
            body.innerHTML = '<p class="text-muted text-sm" style="padding:10px 0">Brak aktywnych ofert lub Steam zablokował zapytanie. Sprawdź za chwilę.</p>';
            return;
        }

        body.innerHTML = `
            <table class="listings-table" style="width:100%;font-size:.85rem;">
                <thead>
                    <tr>
                        <th>Cena</th>
                        <th>Wear</th>
                        <th>Float</th>
                        <th>Naklejki</th>
                        <th>Inspect</th>
                    </tr>
                </thead>
                <tbody>
                    ${listings.map(l => `
                        <tr>
                            <td class="text-danger text-bold text-mono">${formatPrice(l.price)}</td>
                            <td>${l.wear ? `<span class="badge ${wearClass(l.wear)}">${escHtml(l.wear)}</span>` : '–'}</td>
                            <td class="text-mono text-sm">${l.float_value != null ? l.float_value.toFixed(6) : '<span class="text-muted">–</span>'}</td>
                            <td style="font-size:.75rem;max-width:140px;">${
                                l.stickers && l.stickers.length
                                    ? l.stickers.map(s => `<span class="sticker-chip">${escHtml(s)}</span>`).join('')
                                    : '<span class="text-muted">–</span>'
                            }</td>
                            <td>${l.inspect_link ? `<a href="${escHtml(l.inspect_link)}" class="inspect-btn" target="_blank">Inspect</a>` : '–'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            ${data.count > 10 ? `<p class="text-muted text-xs" style="margin-top:8px">Pokazano 10 z ${data.count} ofert. Pełna lista w szczegółach.</p>` : ''}
        `;
    } catch (e) {
        body.innerHTML = '<p class="text-muted text-sm" style="padding:10px 0">Błąd ładowania ofert.</p>';
    }
}

async function modalQueueSkin() {
    if (!modalCurrentSkin) return;
    const btn = document.getElementById('modal-track-btn');
    btn.disabled  = true;
    btn.textContent = 'Dodawanie...';

    try {
        await Promise.all(['search', 'history', 'listings'].map(action =>
            fetch('/api/queue/push', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ source: 'steam', action, item_name: modalCurrentSkin.name }),
            })
        ));
        btn.textContent   = '✓ Dodano do kolejki';
        btn.style.background = 'rgba(34,197,94,0.2)';
        showToast(`✓ Dodano: ${modalCurrentSkin.name}`, 'success');
    } catch (e) {
        btn.disabled  = false;
        btn.textContent = '+ Śledź ten skin';
        showToast('Błąd dodawania do kolejki', 'error');
    }
}

function extractWear(name) {
    for (const w of ['Factory New', 'Minimal Wear', 'Field-Tested', 'Well-Worn', 'Battle-Scarred']) {
        if (name.includes(w)) return w;
    }
    return null;
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeSkinModal();
});
