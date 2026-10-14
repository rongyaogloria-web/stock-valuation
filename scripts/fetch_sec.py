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
import json, os, sys, time, urllib.request, urllib.error
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
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 2:
                time.sleep(5 * (attempt + 1)); continue
            raise


def finally_sleep():
    time.sleep(0.25)  # stay well under the SEC limit of 10 requests/second


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
    failed = []
    for t in tickers:
        cik = lookup.get(t) or lookup.get(t.replace(".", "-"))
        if not cik:
            print(f"{t}: not found in SEC ticker list (foreign or delisted?)"); failed.append(t); continue
        try:
            cf = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"); finally_sleep()
            sub = get(f"https://data.sec.gov/submissions/CIK{cik}.json"); finally_sleep()
        except Exception as e:
            print(f"{t}: download failed: {e}"); failed.append(t); continue
        doc = {
            "source": "SEC EDGAR (data.sec.gov companyfacts + submissions)",
            "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ticker": t, "cik": cik, "entityName": cf.get("entityName", ""),
            "filings": recent_filings(sub, cik),
            "facts": slim_facts(cf.get("facts", {})),
        }
        with open(os.path.join(OUT, f"{t}.json"), "w") as f:
            json.dump(doc, f, separators=(",", ":"))
        print(f"{t}: saved data/sec/{t}.json ({doc['entityName']}, {len(doc['filings'])} recent filings)")
    if failed and len(failed) == len(tickers):
        sys.exit(1)


if __name__ == "__main__":
    main()
