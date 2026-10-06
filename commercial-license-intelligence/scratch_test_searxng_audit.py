"""
Diagnostic script for testing SearXNG Search Provider against software license queries.
"""

from backend.sources.discovery.search_provider import SearxngSearchProvider

searcher = SearxngSearchProvider()

test_queries = [
    ("Antigravity", "Google Antigravity licensing pricing plans free paid"),
    ("Clipchamp", "Microsoft Clipchamp video editor pricing free premium plan"),
    ("Power Automate", "Microsoft Power Automate desktop licensing free paid subscription"),
    ("Outlook for Windows", "Microsoft Outlook for Windows free personal commercial license"),
    ("OneDrive", "Microsoft OneDrive cloud storage free paid plans"),
    ("SSMS", "SQL Server Management Studio free license pricing Microsoft"),
    ("App Installer", "Windows App Installer winget free open source Microsoft"),
]

print("=== SEARXNG SEARCH DISCOVERY AUDIT ===")
print(f"SearXNG Base URL: {searcher.base_url}")
print(f"SearXNG Available: {searcher.is_available()}")

for label, q in test_queries:
    print(f"\n--- Searching for: {label} ({q}) ---")
    results = searcher.search(q, num_results=3)
    for r in results:
        print(f"  Title:   {r.title}")
        print(f"  URL:     {r.url}")
        print(f"  Engine:  {r.engine}")
        print(f"  Snippet: {r.snippet[:150] if r.snippet else ''}...")
