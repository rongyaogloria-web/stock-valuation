"""Read the quarterly / annual reports you upload to data/reports/TICKER/ and
extract the key numbers, so the workbook can use them (mainly for foreign
companies whose quarterly numbers are not in SEC data).

Runs inside the GitHub Action (see .github/workflows/fetch-sec.yml); you can
also run it yourself:  python scripts/extract_reports.py

For each ticker folder it writes data/reports/TICKER.json with, per report:
  period end, fiscal year/quarter, currency, units, and for every item the
  value found, the page and the exact line it came from.
Single-quarter figures are worked out from year-to-date totals using the
other reports of the same fiscal year (upload every quarter, oldest first or
in any order).

Supported files: PDF with selectable text (not scans), and .htm/.html/.txt.
"""
import json, os, re, sys
from datetime import date, datetime, timezone

ROOT = os.path.join(os.path.dirname(__file__), "..")
RDIR = os.path.join(ROOT, "data", "reports")

# ---- what to look for (keep in sync with index.html PRX) ----
FIELDS = {
    "revenue": [r"^(total\s+)?(net\s+)?(operating\s+)?(revenues?|sales|turnover)(,?\s+net)?$", r"^total net (revenues?|sales)$",
                r"^revenue from contracts with customers$"],
    "opInc": [r"^(total\s+)?(operating (income|profit|loss)( \((loss|income)\))?|(\(loss\) )?income( \(loss\))? from operations|"
              r"(income )?\(?loss\)? from operations|operating income \(loss\)|profit from operations)$"],
    "gaapNI": [r"^net (income|earnings|loss|profit)( \((loss|income)\))?( for the (period|year))?( attributable to [a-z .,&'-]+)?$",
               r"^profit (for|attributable to)( the)? (period|year|owners[a-z ]*)$"],
    "ocf": [r"net cash.*operating activities", r"cash (generated|flows?) (from|by) operat"],
    "capex": [r"^(purchases?|acquisitions?|additions?|payments?)( of| to| for)? (property|plant|capital assets|fixed assets|premises)",
              r"^capital expenditures?"],
    "sbc": [r"(stock|share|equity)[- ]based (compensation|payments?)( expense)?$", r"^stock compensation"],
    "shares": [r"^(diluted|weighted[- ]average.*diluted.*|shares used in.*diluted.*|diluted (weighted|shares).*)$"],
    "cash": [r"^cash and (cash )?equivalents$"],
    "sti": [r"^(short-term investments|marketable securities|short-term marketable securities|"
            r"financial assets at fair value through profit or loss)$"],
    "debtLT": [r"^(long-term debt|long-term borrowings|non-?current borrowings|senior notes|bonds payable|long-term bank loans|corporate bonds)([ ,a-z-]*)$"],
    "debtST": [r"^(current portion of (long-term )?(debt|bonds payable|liabilities)|short-term (debt|borrowings|loans)|current borrowings|commercial paper)$"],
}
KIND = {"revenue": "is", "opInc": "is", "gaapNI": "is", "shares": "is", "ocf": "cf", "capex": "cf", "sbc": "cf",
        "cash": "bs", "sti": "bs", "debtLT": "bs", "debtST": "bs"}
PTYPE = {
    "is": re.compile(r"statements? of (consolidated )?(operations|income|earnings|comprehensive income|profit or loss)|income statements?", re.I),
    "cf": re.compile(r"statements? of (consolidated )?cash flows?|cash flow statements?", re.I),
    "bs": re.compile(r"balance sheets?|statements? of (consolidated )?financial position", re.I),
}
NUMRE = re.compile(r"\(\s*\$?\s*\d[\d,]*(?:\.\d+)?\s*\)|\$?\s*\d{1,3}(?:,\d{3})+(?:\.\d+)?|\$?\s*\d+(?:\.\d+)?|(?:^|\s)[—–-](?=\s|$)")
NOTE = re.compile(r"\((?:notes?|附註)\s*[\d,\sand&]+\)", re.I)
MONTHS = {"three": 3, "six": 6, "nine": 9, "twelve": 12, "13": 3, "26": 6, "39": 9, "52": 12}
CURRENCY = [(r"new taiwan dollars?|nt\$", "TWD"), (r"japanese yen|in (millions|billions) of yen", "JPY"),
            (r"hong kong dollars?|hk\$", "HKD"), (r"renminbi|rmb", "CNY"), (r"euros?\b|€", "EUR"),
            (r"korean won", "KRW"), (r"indian rupees?", "INR"), (r"danish kron", "DKK"), (r"swiss francs?", "CHF"),
            (r"pounds? sterling|£", "GBP"), (r"u\.?s\.? dollars?|us\$", "USD")]


def pages_of(path):
    """List of pages, each a list of text lines."""
    if path.lower().endswith(".pdf"):
        import pdfplumber
        out = []
        with pdfplumber.open(path) as pdf:
            for pg in pdf.pages:
                t = pg.extract_text() or ""
                out.append([re.sub(r"\s+", " ", l).strip() for l in t.split("\n") if l.strip()])
        return out
    raw = open(path, encoding="utf-8", errors="replace").read()
    if path.lower().endswith((".htm", ".html", ".xhtml")):
        raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
        raw = re.sub(r"(?i)</(tr|p|div|br|li|h\d)>|<br\s*/?>", "\n", raw)
        raw = re.sub(r"(?i)</t[dh]>", " ", raw)
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"&nbsp;|&#160;", " ", raw).replace("&amp;", "&")
    lines = [re.sub(r"\s+", " ", l).strip() for l in raw.split("\n") if l.strip()]
    return [lines[i:i + 60] for i in range(0, len(lines), 60)] or [[]]


def nums(line):
    out = []
    for m in NUMRE.finditer(line):
        t = m.group(0).strip()
        if re.fullmatch(r"[—–-]", t):
            v = 0.0
        else:
            v = float(re.sub(r"[^0-9.]", "", t) or "nan")
            if t.startswith("("):
                v = -v
        if v == v:
            out.append((v, m.start()))
    return out


def unit_factor(text):
    m = re.search(r"in (millions|thousands|billions)", text, re.I)
    if not m:
        return None
    return {"thousands": 1e-3, "millions": 1.0, "billions": 1e3}[m.group(1).lower()]


def parse_date(s):
    s = s.replace(",", "").replace(".", "")
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def extract(path):
    pages = pages_of(path)
    texts = ["\n".join(p) for p in pages]
    full = "\n".join(texts)
    doc_unit = unit_factor(full)
    cur = next((c for rx, c in CURRENCY if re.search(rx, full[:20000], re.I)), None)
    ptype = [{k: bool(rx.search(t)) for k, rx in PTYPE.items()} for t in texts]
    # pages that are real statements have many lines with 2+ numbers (a contents page does not)
    dense = [sum(1 for l in p if len(nums(NOTE.sub(" ", l))) >= 2) >= 3 for p in pages]
    found, warn = {}, []
    for k, rxs in FIELDS.items():
        cands = []
        for pi, lines in enumerate(pages):
            for line in lines:
                clean = NOTE.sub(" ", line)
                ns = nums(clean)
                if not ns:
                    continue
                label = re.sub(r"[:$]", "", clean[:ns[0][1]]).lower()
                label = re.sub(r"\s+", " ", label).strip(" .")
                if not label or len(label) > 90 or not any(re.search(r, label) for r in rxs):
                    continue
                f = unit_factor(texts[pi]) or doc_unit or 1.0
                if k == "shares":
                    su = re.search(r"shares in (millions|thousands)", texts[pi], re.I)
                    if su:
                        f = 1e-3 if su.group(1).lower() == "thousands" else 1.0
                score = (5 if ptype[pi][KIND[k]] else 0) + (2 if dense[pi] else 0) + (1 if len(ns) >= 2 else 0)
                if k == "gaapNI" and re.search(r"attributable to .*(parent|owners|shareholders|stockholders|company)", label):
                    score += 1  # the shareholders' share, not the total including minority interests
                cands.append((score, -pi, ns[0][0] * f, pi + 1, line))
        if cands:
            cands.sort(reverse=True)
            sc, _, v, page, line = cands[0]
            if k == "capex":
                v = abs(v)
            if k in ("debtLT", "debtST"):  # add up the different debt lines on the same statement page
                same = {}
                for c in cands:
                    if c[3] == page and c[0] == sc:
                        same.setdefault(re.sub(r"[^a-z ]", "", c[4].lower())[:40], c)
                v = sum(c[2] for c in same.values())
                line = " + ".join(c[4][:70] for c in same.values())
            found[k] = {"v": round(v, 3), "page": page, "line": line[:220], "sure": sc >= 7}
            if sc < 7:
                warn.append(f"{k}: found outside the main statements (page {page}) - check it")
    quarterly = bool(re.search(r"three months ended|quarter(ly)? (period )?ended|13 weeks ended", full, re.I))
    cfp = found.get("ocf", {}).get("page")
    cf_text = texts[cfp - 1] if cfp else next((t for t, p, d in zip(texts, ptype, dense) if p["cf"] and d), "")
    m = re.search(r"(three|six|nine|twelve) months ended|(13|26|39|52) weeks ended|years? ended", cf_text, re.I)
    cfm = (MONTHS[m.group(1).lower()] if m.group(1) else MONTHS[m.group(2)]) if m and (m.group(1) or m.group(2)) else (12 if m else (3 if quarterly else 12))
    ism = 3 if quarterly else 12
    dm = re.search(r"(?:months|weeks|period|quarter|year)s? ended\s*:?\s*([A-Z][a-z]+\.? \d{1,2},? \d{4})", full) or \
         re.search(r"(?:as of|as at)\s+([A-Z][a-z]+\.? \d{1,2},? \d{4})", full, re.I)
    end = parse_date(dm.group(1)) if dm else None
    if not end:
        warn.append("period end date not found - name the file with the date, e.g. 2026-09-30.pdf")
        fm = re.search(r"(20\d\d)[-_]?(\d\d)[-_]?(\d\d)", os.path.basename(path))
        if fm:
            end = date(int(fm.group(1)), int(fm.group(2)), int(fm.group(3)))
    if doc_unit is None:
        warn.append('no "in thousands/millions" note found - assumed millions')
    if not found:
        warn.append("no statement lines recognised (scanned PDF?)")
    return {"end": end.isoformat() if end else None, "isM": ism, "cfM": cfm, "currency": cur,
            "unit": {1e-3: "thousands", 1.0: "millions", 1e3: "billions"}.get(doc_unit, "millions (assumed)"),
            "fields": found, "warnings": warn}


def fiscal_label(end, fye):
    """(fiscal year, quarter 'Q1'..'Q4') for a period ending `end`, given a fiscal-year-end date string."""
    e = date.fromisoformat(end)
    if not fye:
        return str(e.year), "Q%d" % ((e.month - 1) // 3 + 1)
    fm, fd = int(fye[5:7]), int(fye[8:10])
    F = date(e.year, fm, min(fd, 28 if fm == 2 else fd))
    if (F - e).days < -15:
        F = date(e.year + 1, fm, F.day)
    months = round((F - e).days / 30.44)
    q = max(1, min(4, 4 - round(months / 3)))
    return str(F.year), "Q%d" % q


def sec_fye(ticker):
    p = os.path.join(ROOT, "data", "sec", f"{ticker}.json")
    if not os.path.exists(p):
        return None
    try:
        facts = json.load(open(p)).get("facts", {})
    except Exception:
        return None
    ends = []
    for tax in facts.values():
        for c in ("Revenues", "Revenue", "RevenueFromContractWithCustomerExcludingAssessedTax"):
            for lst in tax.get(c, {}).get("units", {}).values():
                for e in lst:
                    if e.get("start") and round((date.fromisoformat(e["end"]) - date.fromisoformat(e["start"])).days / 30.44) == 12:
                        ends.append(e["end"])
    return max(ends) if ends else None


def single_quarters(reps):
    """Work out one-quarter figures. Income items: the 3-month column, or for an annual
    report the year minus Q1-Q3. Cash-flow items are year-to-date: subtract the earlier
    report of the same fiscal year."""
    by_fy = {}
    for r in reps:
        if r.get("fy"):
            by_fy.setdefault(r["fy"], []).append(r)
    for r in reps:
        r["quarter"], r["how"] = {}, {}
        for k, f in r["fields"].items():
            if KIND[k] == "bs":
                continue
            v = f["v"]
            if k == "shares":
                r["quarter"][k] = v
                continue
            if KIND[k] == "is":
                if r["isM"] == 3:
                    r["quarter"][k], r["how"][k] = v, "3-month column"
                else:
                    prior = [x for x in by_fy.get(r["fy"], []) if x["fp"] in ("Q1", "Q2", "Q3") and k in x.get("quarter", {})]
                    if len({x["fp"] for x in prior}) == 3:
                        r["quarter"][k] = round(v - sum(x["quarter"][k] for x in prior), 3)
                        r["how"][k] = "full year minus Q1-Q3"
                    else:
                        r["how"][k] = "needs the Q1, Q2 and Q3 reports of this year"
            else:
                m = r["cfM"]
                if m == 3:
                    r["quarter"][k], r["how"][k] = v, "3-month cash flow"
                else:
                    prev = [x for x in by_fy.get(r["fy"], []) if x["cfM"] == m - 3 and k in x["fields"]]
                    if prev:
                        r["quarter"][k] = round(v - prev[0]["fields"][k]["v"], 3)
                        r["how"][k] = f"{m}-month minus {m - 3}-month cash flow"
                    else:
                        r["how"][k] = f"needs the report with the {m - 3}-month cash flow"
    return reps


def main():
    if not os.path.isdir(RDIR):
        print("reports: no data/reports folder")
        return
    for t in sorted(os.listdir(RDIR)):
        folder = os.path.join(RDIR, t)
        if not os.path.isdir(folder):
            continue
        tk = t.upper()
        fye = sec_fye(tk)
        reps = []
        for fn in sorted(os.listdir(folder)):
            if fn.lower().startswith("readme") or not fn.lower().endswith((".pdf", ".htm", ".html", ".xhtml", ".txt")):
                continue
            try:
                r = extract(os.path.join(folder, fn))
            except Exception as e:
                print(f"reports: {tk}/{fn} could not be read ({e})")
                reps.append({"file": fn, "path": f"data/reports/{t}/{fn}", "error": str(e), "fields": {}, "warnings": [str(e)]})
                continue
            r["file"], r["path"] = fn, f"data/reports/{t}/{fn}"
            if r["end"]:
                r["fy"], r["fp"] = fiscal_label(r["end"], fye)
                if r["isM"] == 12 and r["cfM"] == 12:
                    r["fp"] = "Q4"
            reps.append(r)
        good = sorted([r for r in reps if r.get("end")], key=lambda r: r["end"])
        single_quarters(good)
        out = {"ticker": tk, "extracted": datetime.now(timezone.utc).isoformat(timespec="seconds"), "fiscalYearEnd": fye,
               "reports": good + [r for r in reps if not r.get("end")]}
        with open(os.path.join(RDIR, f"{tk}.json"), "w") as f:
            json.dump(out, f, indent=1)
        print(f"reports: {tk}: {len(good)} report(s) read -> data/reports/{tk}.json")
        for r in out["reports"]:
            print(f"   {r['file']}: end {r.get('end')} {r.get('fp', '')} FY{r.get('fy', '')} "
                  f"items {sorted(r['fields'])} {('WARN: ' + '; '.join(r['warnings'])) if r.get('warnings') else ''}")


if __name__ == "__main__":
    main()
