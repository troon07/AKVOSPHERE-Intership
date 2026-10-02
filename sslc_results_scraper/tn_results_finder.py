"""
TN SSLC 2026 Results Finder
-----------------------------
Tries register numbers sequentially with a known DOB.
"""

import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin

# ── CONFIG ──────────────────────────────────────────────────────────────────
BASE_URL     = "https://tnresults.nic.in/2026_SSLCtnresults/2026_8022sslc.htm"
DOB          = "21/02/2011"
START_REG    = 5866419   # 250 before Keerthana S (5866669)
COUNT        = 500        # covers 5866419 to 5866918
DELAY        = 0.5        # seconds between requests
# ────────────────────────────────────────────────────────────────────────────

SESSION = requests.Session()
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Referer": BASE_URL,
    "Origin": "https://tnresults.nic.in",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_base_page():
    """Fetch the results page and detect form structure."""
    try:
        r = SESSION.get(BASE_URL, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Find all forms
        forms = soup.find_all("form")
        if forms:
            form = forms[0]
            action = form.get("action", "")
            method = form.get("method", "post").lower()
            if action and not action.startswith("http"):
                action = urljoin(BASE_URL, action)
            elif not action:
                action = BASE_URL

            # Collect all input fields
            fields = {}
            for inp in form.find_all(["input", "select"]):
                name = inp.get("name")
                value = inp.get("value", "")
                if name:
                    fields[name] = value

            return action, fields, method, r.text
        else:
            # No form found, try to detect from JS or use defaults
            return None, {}, "post", r.text
    except Exception as e:
        print(f"[!] Error fetching base page: {e}")
        return None, {}, "post", ""


def check_result(html_text):
    """Check if the response contains a valid result."""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(separator=" ", strip=True).lower()

    # Error/not-found indicators (exact phrases from TN results site)
    error_phrases = [
        "please check your registration number",
        "check your registration",
        "invalid", "not found", "no record", "wrong", "does not exist",
        "mismatch", "no result", "enter valid",
        "incorrect", "pl verify", "try again",
        "provide dob in correct format"
    ]
    for phrase in error_phrases:
        if phrase in text:
            return False, phrase

    # Positive signals — results typically show marks/grades/subjects
    positive_phrases = ["name", "total", "marks", "grade", "pass", "fail",
                        "result", "subject", "tamil", "english", "maths",
                        "mathematics", "science", "social", "obtained"]
    hits = [p for p in positive_phrases if p in text]

    if len(hits) >= 2:
        # Extract readable content
        lines = []
        for tag in soup.find_all(["td", "th", "p", "span", "div", "b", "strong"]):
            t = tag.get_text(strip=True)
            if 3 < len(t) < 120:
                lines.append(t)
        # Deduplicate while preserving order
        seen = set()
        unique_lines = []
        for line in lines:
            if line not in seen:
                seen.add(line)
                unique_lines.append(line)
        snippet = " | ".join(unique_lines[:20])
        return True, snippet

    return False, "no match"


def try_register(reg_number, form_action, base_fields, method):
    """Submit form for one register number."""
    payload = dict(base_fields)

    # Set register number field
    reg_field = None
    dob_field = None
    for k in payload:
        kl = k.lower()
        if any(x in kl for x in ["reg", "roll", "hallticket", "number"]):
            reg_field = k
        if any(x in kl for x in ["dob", "birth", "date"]):
            dob_field = k

    if reg_field:
        payload[reg_field] = str(reg_number)
    else:
        payload["regno"] = str(reg_number)

    if dob_field:
        payload[dob_field] = DOB
    else:
        payload["dob"] = DOB

    try:
        if method == "get":
            r = SESSION.get(form_action, params=payload, headers=HEADERS, timeout=15)
        else:
            r = SESSION.post(form_action, data=payload, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return check_result(r.text)
    except requests.exceptions.Timeout:
        return False, "timeout"
    except Exception as e:
        return False, f"error: {e}"


def main():
    print("=" * 65)
    print("  TN SSLC 2026 Results Finder")
    print(f"  DOB: {DOB}   Range: {START_REG} to {START_REG + COUNT - 1}")
    print("=" * 65)

    # Step 1: Fetch base page
    print("\n[*] Fetching results page...")
    form_action, base_fields, method, page_html = fetch_base_page()

    if form_action:
        print(f"[OK] Form action: {form_action}")
        print(f"[OK] Method: {method.upper()}")
        print(f"[OK] Fields: {list(base_fields.keys())}")
    else:
        print("[!] No form detected — using fallback config")
        form_action = BASE_URL
        base_fields = {}
        method = "post"

    # Print raw page snippet for debugging
    if page_html:
        print(f"\n[DEBUG] Page length: {len(page_html)} chars")
        # Show form-related HTML
        soup = BeautifulSoup(page_html, "html.parser")
        forms = soup.find_all("form")
        for i, f in enumerate(forms):
            print(f"\n[DEBUG] Form {i}: action={f.get('action')} method={f.get('method')}")
            for inp in f.find_all(["input", "select"]):
                print(f"  -> {inp.get('type','?')} name={inp.get('name')} value={inp.get('value','')}")

    # Step 2: Try register numbers
    print(f"\n[*] Scanning register numbers {START_REG} to {START_REG + COUNT - 1}...\n")
    found_list = []

    for i in range(COUNT):
        reg = START_REG + i
        found, details = try_register(reg, form_action, base_fields, method)

        if found:
            print(f"  [{i+1:3d}/{COUNT}] Reg {reg:>10} -> FOUND!")
            print(f"         {details[:200]}")
            found_list.append((reg, details))
        else:
            print(f"  [{i+1:3d}/{COUNT}] Reg {reg:>10} -> {details[:60]}")

        time.sleep(DELAY)

    # Summary
    print("\n" + "=" * 65)
    if found_list:
        print(f"  MATCHES FOUND: {len(found_list)}")
        for reg, det in found_list:
            print(f"\n  Register No: {reg}")
            print(f"  DOB: {DOB}")
            print(f"  Details: {det[:300]}")
    else:
        print("  No matches found in this range.")
        print(f"  Try adjusting START_REG (currently {START_REG}).")
        print("  Common ranges: 1001-2000, 5001-6000, 10001-11000, etc.")
    print("=" * 65)


if __name__ == "__main__":
    main()
