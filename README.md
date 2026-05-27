# 🎯 skin-market-tracker

Rozproszony scraper i agregator danych z rynków skinów (CS2, Dota 2 i inne).  
Aplikacja pobiera, porównuje i składuje dane rynkowe z wielu platform jednocześnie – m.in. Steam Community Market.

---

## 📌 Funkcjonalności

- **Scraping wieloźródłowy** – Steam Market, oraz kolejne platformy w przyszłości (Skinport, CS.Money, Buff163)
- **4 grupy danych**: przedmioty, ceny historyczne, aktywne oferty, logi scrapowania
- **Silnik rozproszony** – `multiprocessing` + `asyncio`, skalowalny na rdzenie / maszyny / klastry
- **Parsowanie** – BeautifulSoup + nieoficjalne API Steam
- **Interfejs webowy** – Flask
- **Baza danych** – MongoDB
- **Kolejka zadań i cache** – Redis

---

## 🏗️ Architektura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   INTERFEJS     │     │     SILNIK      │     │       BD        │
│     Flask       │────▶│ multiprocessing │────▶│    MongoDB      │
│  (kontener 1)   │     │    + asyncio    │     │  (kontener 4)   │
└─────────────────┘     │  (kontener 2)   │     └─────────────────┘
                        └────────┬────────┘              │
                                 │                        │
                        ┌────────▼────────┐              │
                        │      Redis      │◀─────────────┘
                        │  (kontener 3)   │
                        └─────────────────┘
```

Komunikacja: Flask → Redis (kolejka zadań) → Silnik → MongoDB → Flask (odczyt danych)

---

## 📁 Struktura projektu

```
skin-market-tracker/
│
├── interface/                  # Moduł interfejsu (Flask)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── templates/
│   │   └── static/
│   ├── Dockerfile
│   └── requirements.txt
│
├── engine/                     # Moduł silnika scrapera
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── worker.py           # Procesy robocze (multiprocessing)
│   │   ├── fetcher.py          # Requesty HTTP (asyncio)
│   │   └── parsers/
│   │       ├── steam.py        # Parser Steam Market
│   │       └── base.py         # Klasa bazowa parsera
│   ├── queue/
│   │   └── redis_client.py     # Obsługa kolejki Redis
│   ├── Dockerfile
│   └── requirements.txt
│
├── database/                   # Konfiguracja MongoDB
│   ├── models/
│   │   ├── item.py
│   │   ├── price.py
│   │   ├── listing.py
│   │   └── scrape_log.py
│   └── init/
│       └── mongo-init.js
│
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## 🗄️ Model danych (MongoDB)

| Kolekcja | Opis | Przykładowe pola |
|---|---|---|
| `items` | Przedmioty rynkowe | `name`, `game`, `type`, `wear`, `float` |
| `prices` | Historia cen | `item_id`, `timestamp`, `price`, `volume`, `source` |
| `listings` | Aktywne oferty | `item_id`, `price`, `quantity`, `scraped_at`, `market` |
| `scrape_logs` | Logi zadań | `status`, `errors`, `duration`, `worker_id` |

---

## 🚀 Uruchomienie (development)

> Wymagania: Docker, Docker Compose

```bash
# Klonowanie repozytorium
git clone https://github.com/<your-username>/skin-market-tracker.git
cd skin-market-tracker

# Konfiguracja środowiska
cp .env.example .env

# Uruchomienie wszystkich kontenerów
docker-compose up --build
```

Interfejs dostępny pod: `http://localhost:5000`

---

## 🔧 Zmienne środowiskowe (`.env.example`)

```env
# MongoDB
MONGO_URI=mongodb://mongo:27017
MONGO_DB=skin_market

# Redis
REDIS_URL=redis://redis:6379

# Silnik
WORKER_COUNT=4          # liczba procesów roboczych
REQUEST_DELAY=1.5       # opóźnienie między requestami (s)
```

---

## 📦 Technologie

| Warstwa | Technologia |
|---|---|
| Interfejs | Python, Flask |
| Silnik | Python, multiprocessing, asyncio, aiohttp |
| Parsowanie | BeautifulSoup4 |
| Baza danych | MongoDB (pymongo / motor) |
| Kolejka / cache | Redis |
| Konteneryzacja | Docker, Docker Compose |

---

## 📄 Licencja

MIT © 2025

