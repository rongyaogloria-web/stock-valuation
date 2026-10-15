"""Download quarterly reports straight from companies' official investor-relations
websites into data/reports/TICKER/, so scripts/extract_reports.py can read them.

Which companies and which document: data/report_sources.json, e.g.
  {
    "TSM": {
      "page": "https://investor.tsmc.com/english/quarterly-results/{year}/q{q}",
      "file": "FS.pdf",
      "from": "2025Q1"
    }
  }
  page  - the company's quarterly-results page; {year} and {q} are filled in
  file  - the document to take from that page (the link's file name, e.g. FS.pdf
          = TSMC's consolidated financial statements)
  from  - first quarter to collect (include the year before, so Q4 can be
          worked out as the annual report minus Q1-Q3)

Already-downloaded reports are skipped. Quarters not published yet are skipped.
Runs in the GitHub Action; also works on any computer: python scripts/fetch_ir_reports.py
"""
import json, os, re, time, urllib.parse, urllib.request
from datetime import date

ROOT = os.path.join(os.path.dirname(__file__), "..")
CFG = os.path.join(ROOT, "data", "report_sources.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36 StockValuationWorkbook",
      "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8"}


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.geturl()


def quarters(start):
    y, q = int(start[:4]), int(start[-1])
    today = date.today()
    cy, cq = today.year, (today.month - 1) // 3 + 1
    while (y, q) <= (cy, cq):
        yield y, q
        q += 1
        if q == 5:
            y, q = y + 1, 1


def main():
    if not os.path.exists(CFG):
        print("ir: no data/report_sources.json - nothing to download")
        return
    cfg = json.load(open(CFG))
    for tk, c in cfg.items():
        if tk.startswith("_"):
            continue
        folder = os.path.join(ROOT, "data", "reports", tk.upper())
        os.makedirs(folder, exist_ok=True)
        src_path = os.path.join(folder, "_sources.json")
        sources = json.load(open(src_path)) if os.path.exists(src_path) else {}
        want = c.get("file", "FS.pdf").lower()
        for y, q in quarters(c.get("from", "2025Q1")):
            name = f"{y}-Q{q}-{os.path.basename(want)}"
            if os.path.exists(os.path.join(folder, name)):
                continue
            page = c["page"].format(year=y, q=q, Q=q)
            try:
                html, final = get(page)
            except Exception as e:
                print(f"ir: {tk} {y}Q{q}: page not available ({e})")
                continue
            html = html.decode("utf-8", "replace")
            links = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, re.I)
            hit = [l for l in links if urllib.parse.unquote(l).lower().rsplit("/", 1)[-1] == want]
            if not hit:
                print(f"ir: {tk} {y}Q{q}: {want} not on the page yet (not published?)")
                continue
            url = urllib.parse.urljoin(final, hit[0])
            try:
                pdf, _ = get(url, timeout=120)
            except Exception as e:
                print(f"ir: {tk} {y}Q{q}: download failed ({e})")
                continue
            if not pdf.startswith(b"%PDF"):
                print(f"ir: {tk} {y}Q{q}: link did not return a PDF - skipped")
                continue
            open(os.path.join(folder, name), "wb").write(pdf)
            sources[name] = {"url": url, "page": page, "downloaded": date.today().isoformat()}
            print(f"ir: {tk} {y}Q{q}: saved data/reports/{tk.upper()}/{name} ({len(pdf) // 1024} KB)")
            time.sleep(1)
        with open(src_path, "w") as f:
            json.dump(sources, f, indent=1)


if __name__ == "__main__":
    main()
