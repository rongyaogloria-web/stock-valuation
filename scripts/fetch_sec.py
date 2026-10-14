"""Download official SEC EDGAR data for a list of tickers.

Runs inside GitHub Actions (see .github/workflows/fetch-sec.yml), but you can
also run it on any computer with Python 3:  python scripts/fetch_sec.py MRVL,MU

For each ticker it writes data/sec/TICKER.json containing:
  - the XBRL facts the workbook needs (revenue, profit, cash flow, shares,
    cash, debt...) from https://data.sec.gov/api/xbrl/companyfacts/
  - links to the latest 10-Q / 10-K / 20-F filings from
    https://data.sec.gov/submissions/
Open that file in the workbook (step 3 > Auto-fill) to fill years of history.

The SEC asks every automated user to identify themselves. Set a repository
variable SEC_USER_AGENT such as "Jane Doe jane@example.com"
(Settings > Secrets and variables > Actions > Variables).
"""
import gzip, json, os, sys, time, urllib.request, urllib.error, zlib
from datetime import datetime, timezone

UA = os.environ.get("SEC_USER_AGENT", "").strip() or "StockValuationWorkbook (personal research)"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "sec")

# Same XBRL tags the workbook reads (keep in sync with index.html XC / XBG)
CONCEPTS = {
    "us-gaap": [
        "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet",
        "OperatingIncomeLoss", "NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss",
        "NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets", "PaymentsForCapitalImprovements",
        "ShareBasedCompensation", "AllocatedShareBasedCompensationExpense",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
        "LongTermDebt", "DebtInstrumentCarryingAmount", "ShortTermBorrowings", "CommercialPaper",
        "LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations", "SeniorNotes", "ConvertibleNotesPayable",
        "LongTermDebtCurrent", "DebtCurrent",
        "BusinessCombinationContingentConsiderationLiability",
        "BusinessCombinationContingentConsiderationLiabilityCurrent",
        "BusinessCombinationContingentConsiderationLiabilityNoncurrent",
    ],
    "ifrs-full": [
        "Revenue", "RevenueFromContractsWithCustomers", "ProfitLossFromOperatingActivities",
        "ProfitLossAttributableToOwnersOfParent", "ProfitLoss", "CashFlowsFromUsedInOperatingActivities",
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", "PurchaseOfPropertyPlantAndEquipment",
        "AdjustmentsForSharebasedPayments", "AdjustedWeightedAverageShares", "CashAndCashEquivalents",
        "CurrentFinancialAssetsAtFairValueThroughProfitOrLoss", "NoncurrentPortionOfNoncurrentBorrowings",
        "LongtermBorrowings", "CurrentPortionOfNoncurrentBorrowings", "ShorttermBorrowings",
    ],
    "dei": ["EntityCommonStockSharesOutstanding"],
}
FORMS = {"10-Q", "10-K", "20-F", "40-F", "10-Q/A", "10-K/A", "20-F/A"}


def get(url):
    """Download JSON from the SEC. Handles compressed (gzip) replies and retries."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Encoding": "gzip, deflate", "Accept": "application/json"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                body = r.read()
                enc = (r.headers.get("Content-Encoding") or "").lower()
            if enc == "gzip" or body[:2] == b"\x1f\x8b":
                body = gzip.decompress(body)
            elif enc == "deflate":
                body = zlib.decompress(body)
            return json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 404):
                raise RuntimeError(f"HTTP {e.code} from SEC for {url}"
                                   + (" (check SEC_USER_AGENT is set to your name and email)" if e.code == 403 else ""))
        except Exception as e:  # timeouts, cut-off downloads, bad JSON
            last = e
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"{type(last).__name__}: {last} ({url})")


def finally_sleep():
    time.sleep(0.25)  # stay well under the SEC limit of 10 requests/second


def get_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (StockValuationWorkbook)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def get_price(ticker):
    """Latest closing price (delayed). Tries Stooq, then Yahoo. Returns dict or None."""
    try:
        csv = get_text(f"https://stooq.com/q/l/?s={ticker.lower().replace('.', '-')}.us&f=sd2t2ohlcv&h&e=csv")
        row = csv.strip().splitlines()[-1].split(",")
        if len(row) >= 7 and row[6] not in ("N/D", ""):
            return {"price": round(float(row[6]), 2), "date": row[1], "source": "stooq.com (delayed close)"}
    except Exception as e:
        print(f"{ticker}: Stooq price failed ({e})")
    try:
        j = json.loads(get_text(f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1d"))
        m = j["chart"]["result"][0]["meta"]
        d = datetime.fromtimestamp(m.get("regularMarketTime", 0), timezone.utc).date().isoformat()
        return {"price": round(float(m["regularMarketPrice"]), 2), "date": d, "source": "Yahoo Finance (delayed)"}
    except Exception as e:
        print(f"{ticker}: Yahoo price failed ({e})")
    return None


def build_bundle(root):
    """Pack every data/sec/*.json and data/workbooks/*.json into data/sec-data.js,
    which index.html loads automatically (works on GitHub Pages and offline)."""
    sec, wbs = {}, {}
    sdir, wdir = os.path.join(root, "data", "sec"), os.path.join(root, "data", "workbooks")
    for fn in sorted(os.listdir(sdir)) if os.path.isdir(sdir) else []:
        if fn.endswith(".json"):
            try:
                sec[fn[:-5].upper()] = json.load(open(os.path.join(sdir, fn)))
            except Exception as e:
                print(f"bundle: skipped {fn} ({e})")
    for fn in sorted(os.listdir(wdir)) if os.path.isdir(wdir) else []:
        if fn.endswith(".json"):
            try:
                wbs[fn[:-5].upper()] = json.load(open(os.path.join(wdir, fn)))
            except Exception as e:
                print(f"bundle: skipped workbook {fn} ({e})")
    out = os.path.join(root, "data", "sec-data.js")
    with open(out, "w") as f:
        f.write("/* Built automatically by scripts/fetch_sec.py - do not edit by hand. */\n")
        f.write("window.SEC_DATA=" + json.dumps(sec, separators=(",", ":")) + ";\n")
        f.write("window.WORKBOOKS=" + json.dumps(wbs, separators=(",", ":")) + ";\n")
        f.write("window.SEC_BUILT=" + json.dumps(datetime.now(timezone.utc).isoformat(timespec="seconds")) + ";\n")
    print(f"bundle: data/sec-data.js with {len(sec)} companies, {len(wbs)} saved workbooks")


def slim_facts(facts):
    out = {}
    for tax, names in CONCEPTS.items():
        src = facts.get(tax, {})
        keep = {n: {"units": src[n]["units"]} for n in names if n in src}
        if keep:
            out[tax] = keep
    return out


def recent_filings(sub, cik):
    r = sub.get("filings", {}).get("recent", {})
    rows = []
    for i, form in enumerate(r.get("form", [])):
        if form not in FORMS:
            continue
        acc = r["accessionNumber"][i].replace("-", "")
        rows.append({
            "form": form,
            "filingDate": r["filingDate"][i],
            "reportDate": r.get("reportDate", [""] * (i + 1))[i],
            "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{r['primaryDocument'][i]}",
        })
        if len(rows) >= 12:
            break
    return rows


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--bundle-only":
        return build_bundle(os.path.join(os.path.dirname(__file__), ".."))
    raw = (sys.argv[1] if len(sys.argv) > 1 else "") or os.environ.get("TICKERS", "")
    tickers = [t.strip().upper() for t in raw.replace(";", ",").replace(" ", ",").split(",") if t.strip()]
    if not tickers:
        wl = os.path.join(os.path.dirname(__file__), "..", "data", "watchlist.txt")
        if os.path.exists(wl):
            tickers = [l.split("#")[0].strip().upper() for l in open(wl) if l.split("#")[0].strip()]
    if not tickers:
        sys.exit("No tickers given and data/watchlist.txt is empty.")
    if not os.environ.get("SEC_USER_AGENT"):
        print("WARNING: SEC_USER_AGENT is not set. The SEC may refuse requests. See README.")

    os.makedirs(OUT, exist_ok=True)
    m = get("https://www.sec.gov/files/company_tickers.json")
    finally_sleep()
    lookup = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in m.values()}
    failed, log = [], []

    def say(msg):
        print(msg); log.append(msg)

    for t in tickers:
        cik = lookup.get(t) or lookup.get(t.replace(".", "-"))
        if not cik:
            say(f"{t}: FAILED - not in the SEC ticker list (check spelling; non-US companies may not file with the SEC)"); failed.append(t); continue
        try:
            cf = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"); finally_sleep()
            sub = get(f"https://data.sec.gov/submissions/CIK{cik}.json"); finally_sleep()
        except Exception as e:
            say(f"{t}: FAILED - {e}"); failed.append(t); continue
        doc = {
            "source": "SEC EDGAR (data.sec.gov companyfacts + submissions)",
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ticker": t, "cik": cik, "entityName": cf.get("entityName", ""),
            "filings": recent_filings(sub, cik),
            "price": get_price(t),
            "facts": slim_facts(cf.get("facts", {})),
        }
        with open(os.path.join(OUT, f"{t}.json"), "w") as f:
            json.dump(doc, f, separators=(",", ":"))
        n_q = sum(len(u) for tax in doc["facts"].values() for c in tax.values() for u in c["units"].values())
        pr = doc["price"]
        say(f"{t}: OK - {doc['entityName']}, {n_q} data points, {len(doc['filings'])} recent filings, "
            + (f"price {pr['price']} on {pr['date']} ({pr['source']})" if pr else "price not found"))
    build_bundle(os.path.join(os.path.dirname(__file__), ".."))
    with open(os.path.join(OUT, "_last_run.log"), "w") as f:
        f.write(f"Run {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n" + "\n".join(log) + "\n")
    if failed:
        sys.exit(f"Failed for: {', '.join(failed)} - see the log above or data/sec/_last_run.log")


if __name__ == "__main__":
    main()
