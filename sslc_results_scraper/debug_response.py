"""
Debug: See what the TN results site actually returns
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://tnresults.nic.in/2026_SSLCtnresults/2026_8022sslc.htm"
FORM_URL = "https://tnresults.nic.in/2026_SSLCtnresults/2026_7669sslc.asp"

SESSION = requests.Session()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Referer": BASE_URL,
    "Origin": "https://tnresults.nic.in",
}

# First fetch the base page to get cookies
print("[*] Fetching base page for session cookies...")
r0 = SESSION.get(BASE_URL, headers=HEADERS, timeout=20)
print(f"    Status: {r0.status_code}, Cookies: {dict(SESSION.cookies)}")

# Try Keerthana's known register number with a random DOB
# (we don't know her DOB, so we use the boy's DOB — it should still show SOMETHING or a specific error)
test_cases = [
    ("5866669", "21/02/2011"),   # Keerthana's reg with the boy's DOB
    ("5866669", "21-02-2011"),   # Different date format
    ("5866669", "2011-02-21"),   # ISO format
    ("5866669", "21022011"),     # No separators
]

for reg, dob in test_cases:
    print(f"\n{'='*60}")
    print(f"[*] Trying reg={reg} dob={dob}")
    
    payload = {
        "regno": reg,
        "dob": dob,
        "B1": "Get Marks",
    }
    
    r = SESSION.post(FORM_URL, data=payload, headers=HEADERS, timeout=15)
    print(f"    Status: {r.status_code}")
    print(f"    Response length: {len(r.text)} chars")
    print(f"    Content-Type: {r.headers.get('Content-Type', 'unknown')}")
    
    # Save raw HTML
    fname = f"response_{reg}_{dob.replace('/', '_')}.html"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(r.text)
    print(f"    Saved to {fname}")
    
    # Show text content
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    print(f"\n    --- TEXT CONTENT (first 1500 chars) ---")
    print(text[:1500])
    print(f"    --- END ---")
