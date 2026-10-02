"""Fetch full result for RITHEESH KUMAR P (5866735)"""
import requests
from bs4 import BeautifulSoup

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

# Get session cookies
SESSION.get(BASE_URL, headers=HEADERS, timeout=20)

# Fetch full result
payload = {"regno": "5866735", "dob": "21/02/2011", "B1": "Get Marks"}
r = SESSION.post(FORM_URL, data=payload, headers=HEADERS, timeout=15)

# Save raw HTML
with open("ritheesh_result.html", "w", encoding="utf-8") as f:
    f.write(r.text)

# Parse and display
soup = BeautifulSoup(r.text, "html.parser")

print("=" * 60)
print("  RITHEESH KUMAR P — SSLC March 2026 Results")
print("  Register No: 5866735 | DOB: 21/02/2011")
print("=" * 60)

# Get all table data
tables = soup.find_all("table")
for table in tables:
    rows = table.find_all("tr")
    for row in rows:
        cells = row.find_all(["td", "th"])
        if cells:
            line = " | ".join(c.get_text(strip=True) for c in cells if c.get_text(strip=True))
            if line.strip():
                print(f"  {line}")

print("\n" + "=" * 60)
# Also print full text
print("\n  FULL TEXT:")
print(soup.get_text(separator="\n", strip=True))
print("=" * 60)
