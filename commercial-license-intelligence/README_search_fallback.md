# 3-Engine Search Fallback Chain (SearXNG + YaCy + DuckDuckGo)

This platform features a 3-tier search fallback chain for **Stage 4: Multi-Modal Research & Evidence Discovery**:

1. **SearXNG** (Primary) — Self-hosted metasearch aggregator (`http://localhost:8080`).
2. **YaCy** (Secondary) — Self-hosted peer-to-peer search engine (`http://localhost:8090`).
3. **DuckDuckGo HTML Scrape** (Tertiary) — Zero-cost, zero-setup public web fallback (`https://html.duckduckgo.com/html/`).

---

## 1. Quickstart: Starting the Docker Containers

### Option A: Docker Compose (Recommended)

Start both SearXNG and YaCy using the included `docker-compose.yml`:

```bash
docker compose up -d
```

To stop containers:
```bash
docker compose down
```

### Option B: Standalone Docker Run Commands

If not using Docker Compose, launch each container individually:

#### Start YaCy:
```bash
docker run -d \
  --name yacy \
  -p 8090:8090 \
  -v yacy_data:/opt/yacy/DATA \
  -e JAVA_ARGS="-Xms512m -Xmx1536m" \
  --restart unless-stopped \
  yacysearch/yacy:latest
```

#### Start SearXNG:
```bash
docker run -d \
  --name searxng \
  -p 8080:8080 \
  -e SEARXNG_BASE_URL="http://localhost:8080/" \
  --restart unless-stopped \
  searxng/searxng:latest
```

---

## 2. Verifying Engine Reachability

Verify all 3 engines using `curl`:

### 1. Test SearXNG (Port 8080)
```bash
curl -s "http://localhost:8080/search?q=adobe+acrobat+licensing&format=json" | grep -o '"results":\[.*\]' | head -c 100
```

### 2. Test YaCy (Port 8090)
```bash
curl -s "http://localhost:8090/yacysearch.json?query=oracle+java+licensing" | grep -o '"channels":\[.*\]' | head -c 100
```

### 3. Test DuckDuckGo HTML Scraper (Direct HTTPS)
```bash
curl -s -X POST https://html.duckduckgo.com/html/ \
  -d "q=docker+desktop+licensing" \
  -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36" \
  | grep -o 'class="result__title"' | head -n 3
```

---

## 3. YaCy Seeding & Domain Crawler Guidance

YaCy's default global P2P index is sparse for niche enterprise software terms. To optimize YaCy for software license intelligence:

### Step 1: Access YaCy Administration Console
Open `http://localhost:8090` in your web browser. Default credentials are setup during first container initialization (or default admin/admin).

### Step 2: Seed Official Vendor Domains
You can trigger YaCy's crawler directly on the domains listed in `official_domains.yaml` (`adobe.com`, `microsoft.com`, `oracle.com`, `github.com`, etc.):

1. Navigate to **Crawler / Indexing** $\rightarrow$ **Quick Crawl** (`http://localhost:8090/QuickCrawler_p.html`).
2. Input target seed URLs (e.g. `https://www.adobe.com/legal/licenses-terms.html`, `https://learn.microsoft.com/licensing/`).
3. Set **Crawling Depth** to `2` and **Filter on site** to `must match domain`.
4. Click **Start Crawling**.

### Step 3: API-Based Crawler Seeding
You can also automate seeding via YaCy's HTTP API:
```bash
curl -X POST "http://localhost:8090/Crawler_p.html" \
  -d "crawlingURL=https://www.adobe.com/legal/licenses-terms.html" \
  -d "crawlingDepth=2" \
  -d "mustmatch=.*adobe\.com.*"
```

---

## 4. How the Fallback Chain & Circuit Breaker Work

The fallback logic is implemented in `SearchEngineChain` (`backend/search_engines/chain.py`):

```
                       ┌───────────────────────────────┐
                       │   Search Request for Query    │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │ 1. SearXNG (http://...:8080)   │
                       └───────┬───────────────┬───────┘
                     Success   │               │ Fails / 0 domain matches
                               │               ▼
                               │   ┌───────────────────────────────┐
                               │   │ 2. YaCy (http://...:8090)     │
                               │   └───────┬───────────────┬───────┘
                               │ Success   │               │ Fails / 0 domain matches
                               │           │               ▼
                               │           │   ┌───────────────────────────────┐
                               │           │   │ 3. DuckDuckGo HTML Scraper    │
                               │           │   └───────┬───────────────┬───────┘
                               │           │ Success   │               │ Fails
                               ▼           ▼           ▼               ▼
                        ┌──────────────────────────────┐ ┌───────────────────────────┐
                        │ Return Authoritative Results │ │ Log Failure / DevFallback │
                        └──────────────────────────────┘ └───────────────────────────┘
```

### Key Architectural Behaviors:

1. **Domain Whitelist Filtering**:
   - Every candidate URL is filtered against `official_domains.yaml`.
   - If an engine returns 10 search results but 0 match official vendor domains, this is treated as a **failure condition** that automatically triggers fallback to the next engine!
2. **1-Retry Backoff**:
   - Before abandoning an engine, `SearchEngineChain` retries once with a `0.5s` backoff to absorb transient connection spikes.
3. **Sliding-Window Circuit Breaker**:
   - If an engine experiences 3 failures within a 5-minute window (`CIRCUIT_BREAKER_COOLDOWN_SECONDS=300`), the circuit breaker opens.
   - Subsequent queries immediately bypass that engine without wasting network roundtrips until the cooldown expires.
4. **Structured Telemetry**:
   - Every query logs which engine resolved the request (e.g. `✓ [SearchChain] Query resolved by 'searxng' (3 authoritative results found)`).
   - Engine success metrics and all-fail metrics are recorded in `chain.metrics`.
