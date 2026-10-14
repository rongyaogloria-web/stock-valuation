# Stock Valuation Workbook

A one-page, no-install tool for long-term stock analysis. It walks you through six questions and does the maths for you:

1. **Company**: today's price, shares, cash and debt
2. **Business & moat**: is it a good business?
3. **The numbers**: 5–10 years of history and the key ratios
4. **Cash & red flags**: is the profit real cash? Automatic warning checks
5. **Value**: bear / base / bull DCF, reverse DCF, sensitivity table
6. **Decision**: margin of safety, buy-below and expensive-above prices, thesis-breakers

Everything runs in your browser. No account, no server, no AI needed. A Marvell (MRVL) example is pre-loaded so you can see how a finished analysis looks.

> Educational tool, not financial advice. The output is only as good as the numbers and assumptions you put in.

---

## 1. Open the tool (this repo is private)

Because the repo is **private**, only you can see it, and the tool runs from your own computer rather than from a website:

1. On the repo page click **Code → Download ZIP** (or `git clone` it), and unzip.
2. Double-click **`index.html`**. It opens in your browser and works offline.
3. To get updates later, download again (or `git pull`).

To edit files directly on GitHub: open a file → pencil icon → **Commit changes**. To add files: **Add file → Upload files**.

> Want a shareable web link instead? Either make the repo **Public** (Settings → General → Danger Zone → Change visibility), then turn on **Settings → Pages → Deploy from a branch → `main` / `(root)`**; or keep it private on a paid GitHub plan, which allows Pages on private repos.

---

## 2. Fill the history automatically (no typing)

There are three ways, from most to least automatic. All of them appear under **Step 3 → Auto-fill from a report**.

### A. Official SEC data via GitHub (best: years of quarters in one click)

The SEC does not allow web pages to download its data directly, so a small program runs **on GitHub's servers** instead (a "GitHub Action"). It fetches the official EDGAR data and saves it into your repo.

**One-time setup**
1. In the repo: **Settings → Secrets and variables → Actions → Variables tab → New repository variable**.
   Name: `SEC_USER_AGENT` · Value: your name and email, e.g. `Jeffri Chiam you@example.com`. (The SEC requires automated users to identify themselves. It is only sent to sec.gov.)
2. **Settings → Actions → General → Workflow permissions → "Read and write permissions" → Save** (lets the Action save files).

**Each time you want data**
1. **Actions** tab → **Fetch SEC data** → **Run workflow** → type tickers, e.g. `MRVL, MU, GOOGL` → **Run**. It takes about 30 seconds.
   *Or do nothing:* every **Monday** it refreshes the tickers listed in `data/watchlist.txt` (edit that file to change the list).
2. The files appear in `data/sec/` (e.g. `data/sec/MRVL.json`). Download them (open the file → download icon) or pull the repo.
3. In the tool: drop `MRVL.json` on the Auto-fill box. Choose **Quarterly / Annual** and **how many periods**, check the preview, then click **Replace history with these periods**.

What you get: revenue, operating income, GAAP net income, operating cash flow, capex, stock-based pay and diluted shares for every quarter. The tool works out Q4 and the cash-flow quarters automatically from year-to-date totals. Cash, debt, earn-outs, company name and last-12-month revenue fill into step 1, and the card links to the latest 10-Q / 10-K on sec.gov.

Not included in SEC data: **adjusted (non-GAAP) net income**. Type it from the earnings press release (existing values are kept when you refresh). Foreign companies filing 20-F (e.g. TSMC) usually have **annual** data only.

Private repos get 2,000 free Action minutes a month, and each run uses about 1 minute.

### B. Manual SEC download (no setup)
In the Auto-fill box open **"Get years of quarterly data straight from the SEC"**:
1. Type the ticker and click **find its CIK number on SEC**. The CIK is the number shown next to the company name.
2. Type the CIK and click **open SEC data**. Your browser shows a page of data; save it with **Cmd+S** (Mac) / **Ctrl+S**, keeping the `.json` ending.
3. Drop that file on the Auto-fill box.

### C. Drop a single report (10-Q, 10-K or PDF)
- **SEC filing as .htm (exact):** on sec.gov open the filing and click the main document (Type 10-Q or 10-K). The address starts `https://www.sec.gov/ix?doc=/Archives/...`. Delete `ix?doc=/` from the address and press Enter, then save the page (**Cmd/Ctrl+S → "Web Page, HTML only"** or "Page Source"). Drop the `.htm` file in. The numbers come from the official XBRL tags.
- **PDF (any company, best guess):** drop the quarterly or annual report PDF. For each item the tool shows the line it found and the page number; use the dropdowns to pick a different line or column if needed. Check the "Income statement covers" and "Cash-flow statement covers" months boxes. The PDF reader loads from the internet the first time. Scanned (image) PDFs cannot be read.
- **Year-to-date figures:** 10-Qs report cash flow as year-to-date (e.g. 6 months), and 10-Ks give full-year totals. The tool turns these into a single quarter by subtracting the earlier quarters of the same fiscal year that are **already in your table**. So add reports **oldest first** (you can drop several at once and click **Add all**).
- Every number appears in a review table with its source before anything is saved. Untick **Use** or overwrite **Will insert** to correct it.

---

## 3. Analyse a new company

1. Open the tool → click **New blank**.
2. Use **Auto-fill** (section 2 above) for the history, then fill every remaining box with a red outline. The blue **"Data still needed"** box at the top lists what is missing.
3. Read the results in steps 4–6.
4. Click **Save file**. It downloads e.g. `NVDA-2026-11-02.json`.
5. Keep it in your repo: on GitHub open the **`data`** folder → **Add file → Upload files** → drop the JSON → **Commit**.
6. Re-open a saved analysis any time:
   - Click **Open file…** in the tool and pick the JSON from the `data` folder.
   - (Only if the tool is hosted on GitHub Pages: a link ending `?data=data/NVDA-2026-11-02.json` opens it directly.)

The tool also auto-saves in your browser, but browser storage can be wiped. **Save file** is your permanent copy.

To update after a new quarterly report: open the saved file, change the numbers, **Save file** with the new date. Keeping the old file lets you see how your view changed.

---

## 4. The data you need to insert, and where to find it

**Where to get filings (free):**
- US companies: **SEC EDGAR** (sec.gov → "Search filings" → company name). The **10-K** is the annual report and the **10-Q** is the quarterly report.
- Any company: the **Investor Relations** page on its website, which has the earnings press release (with "non-GAAP" / "adjusted" tables), slides and call transcripts.
- Share price: any quote site (this is the only number not in a filing).

**Units:** all money in **millions** (US$2.7 billion = `2700`). Share price in dollars. Shares in **millions** (921,200,000 shares = `921.2`). Percentages as plain numbers (`10` = 10%).

### Step 1 · Company basics

| Field | Required | Where to find it |
|---|---|---|
| Ticker, Company name | ✔ (ticker) | You know these |
| Analysis date | | Date of your price / filings |
| Share price | ✔ | Any quote site |
| Diluted shares outstanding | ✔ | Latest 10-Q income statement → "weighted-average shares, diluted". Add large convertibles/preferred shares if they will convert |
| Revenue, last 12 months | ✔ | Add the last 4 quarters' revenue (10-Qs or press releases), or the latest 10-K if it was just released |
| Cash & short-term investments | ✔ | Latest balance sheet |
| Total debt | ✔ | Balance sheet: short-term + long-term debt |
| Other debt-like items | | Earn-outs / "contingent consideration", pension deficit, large legal claims. `0` if none |

### Step 2 · Business & moat (your judgment)
A one-line description of how it makes money (10-K Item 1 "Business"), and Yes / Partly / No answers to six moat questions. Each question shows a hint on where to look.

### Step 3 · History (5–10 years, oldest first; or recent quarters)

| Column | Where to find it |
|---|---|
| Period | e.g. `FY2025` or `Q2 FY27`. Set "Periods are" to Annual or Quarterly |
| Revenue | Income statement, top line |
| Operating income | Income statement, "operating income" (GAAP) |
| Net income (GAAP) | Income statement, bottom line |
| Adjusted net income | Earnings press release → "non-GAAP net income" (leave blank if none) |
| Operating cash flow | Cash-flow statement → "net cash provided by operating activities" |
| Capex | Cash-flow statement → "purchases of property and equipment" (enter as positive) |
| Stock-based comp | Cash-flow statement → "stock-based compensation" |
| Diluted shares (M) | Income statement → weighted-average diluted shares |

Blanks are fine: any ratio that needs a missing number shows "–". Tip: older years are all in one place in the 10-K's "Selected financial data", or on free sites like macrotrends or stockanalysis.com. Check a couple of numbers against the filing.

### Step 4 · Manual red-flag checks (tick if true)
Auditor change · unusual revenue recognition · related-party dealings · customer over 10% of sales · receivables/inventory outgrowing sales · goodwill over 40% of assets · receivables factoring · large purchase commitments. Each one shows which filing note to read.

### Step 5 · Valuation assumptions (your judgment, informed by step 3)

| Field | Typical value | How to choose it |
|---|---|---|
| Return you demand | 8–12% | Your hurdle rate; higher for riskier companies |
| Tax rate | 15–21% (US) | 10-K income-tax note, "effective tax rate" |
| Net interest cost | | Interest expense − interest income (negative if net cash) |
| Cash conversion | 90–100% | Look at "FCF ÷ GAAP net income" in step 3 |
| Forecast years | 5 | Standard |
| Years until first forecast year ends | 1–1.5 | e.g. today is Oct and the first fiscal year ends in Jan the year after next ⇒ ~1.3 |
| Name of first forecast year | | e.g. `FY28`; later years count up automatically |
| Shares to divide by | | Today's diluted shares, rounded up for expected dilution |
| Margin of safety you want | 20–30% | More for less certain businesses |

**For each of Bear / Base / Bull:**

| Field | How to choose it |
|---|---|
| Probability | Your odds; the three should add up to 100 |
| Revenue, first forecast year | Start from company guidance or analyst consensus (Yahoo Finance "Analysis" tab, etc.), then adjust |
| Revenue, final forecast year | Your view of sales at the end. **This drives most of the value** |
| Owner margin, first/final year | Operating margin minus stock-based pay as % of sales. Check "FCF − SBC margin" in step 3 for what the business really earns |
| Selling P/E at the end | What a buyer would pay then for a now-mature business: usually 15–25x |

---

## 5. How the maths works (in plain words)

For each future (bear / base / bull):

1. **Revenue** grows smoothly from your first-year to your final-year number.
2. **Owner earnings** = revenue × owner margin × (1 − tax) − net interest.
3. **Per share** = owner earnings ÷ shares.
4. You **collect** cash each year (per-share earnings × cash conversion).
5. At the end you **sell** at your selling P/E × final-year earnings.
6. Every amount is **shrunk back to today** (divided by (1 + your required return) ^ years away).
7. Subtract **net debt per share**. The result is the **value per share**.

Then:
- **Weighted value** = the three values blended by your probabilities.
- **Return per year** = the yearly return you would earn buying at today's price if that future happens (IRR).
- **Reverse DCF** = the final-year revenue that makes value exactly equal today's price. In other words: what is the market already assuming?
- **Sensitivity table** = base-case value for different final revenues and selling P/Es, so you can see how fragile the answer is.
- **Buy below** = the lower of base and weighted value, minus your margin of safety.

Shortcut used: stock-based pay is treated as a real cost (via the owner margin), so the model does not also add future share dilution. Change "Shares to divide by" if you expect big acquisitions or conversions.

---

## 6. Files in this repo

```
index.html                        the whole tool (open it in any browser)
README.md                         this guide
data/TEMPLATE.json                blank workbook
data/MRVL-2026-10-14.json         worked Marvell example
data/watchlist.txt                tickers refreshed from the SEC every Monday
data/sec/                         SEC data saved by the GitHub Action
scripts/fetch_sec.py              the downloader the Action runs (also runs on any PC: python scripts/fetch_sec.py MRVL)
.github/workflows/fetch-sec.yml   the GitHub Action schedule / Run button
```

## 7. Good habits

- Write the **source and page** for each number in "Notes & sources".
- Keep **facts** (from filings), **management claims** (from calls/press releases) and **your assumptions** separate.
- If the **bear case** would cause a loss you can't stomach, size the position small or pass.
- Re-run the workbook each quarter and compare it with the **thesis-breakers** you wrote down.
