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

// ── Init ──────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initSkinPicker();
});
