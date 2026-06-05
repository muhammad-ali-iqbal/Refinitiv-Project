"""
ingestion/aliases.py

Maps common shorthand codes → full Refinitiv variable names as they appear
in the CF Export sheets. Extend this freely.
"""

ALIASES = {
    # Valuation
    "MV":           "Market Capitalization",
    "MKTCAP":       "Market Capitalization",
    "EV":           "Enterprise Value",
    "PTBV":         "Price to Tangible Book Value per Share",
    "PBV":          "Price to Book Value per Share - Issue Specific",
    "PB":           "Price to Book Value per Share - Issue Specific",
    "PE":           "Price to EPS - Diluted - excluding Extraordinary Items Applicable to Common - Total",
    "P/E":          "Price to EPS - Diluted - excluding Extraordinary Items Applicable to Common - Total",
    "PS":           "Price to Revenue from Business Activities - Total per Share",
    "P/S":          "Price to Revenue from Business Activities - Total per Share",
    "PCF":          "Price to Cash Flow per Share",
    "P/CF":         "Price to Cash Flow per Share",
    "PFCF":         "Price to Free Cash Flow per Share",
    "P/FCF":        "Price to Free Cash Flow per Share",
    "EV/EBITDA":    "Enterprise Value to Earnings before Interest, Taxes, Depreciation & Amortization (EBITDA)",
    "EV/SALES":     "Enterprise Value to Revenue from Business Activities - Total",
    "EV/CFO":       "Enterprise Value to Net Cash Flow from Operating Activities",
    "DY":           "Dividend Yield - Common Stock - Net - Issue Specific - %",
    "DIV YIELD":    "Dividend Yield - Common Stock - Net - Issue Specific - %",
    "FCF YIELD":    "Free Cash Flow Yield - %",
    "PEG":          "PE Growth Ratio",
    "PRICE":        "Price Close (End of Period)",

    # Income Statement
    "REV":          "Revenue from Business Activities - Total",
    "REVENUE":      "Revenue from Business Activities - Total",
    "SALES":        "Revenue from Business Activities - Total",
    "GP":           "Gross Profit - Industrials/Property - Total",
    "EBITDA":       "Earnings before Interest, Taxes, Depreciation & Amortization (EBITDA)",
    "EBIT":         "Operating Profit before Non-Recurring Income/Expense",
    "NI":           "Income before Discontinued Operations & Extraordinary Items",
    "NET INCOME":   "Income before Discontinued Operations & Extraordinary Items",
    "EPS":          "EPS - Diluted - excluding Extraordinary Items Applicable to Common - Total",

    # Balance Sheet
    "CASH":         "Cash & Cash Equivalents",
    "TA":           "Total Assets",
    "TOTAL ASSETS": "Total Assets",
    "DEBT":         "Debt - Total",
    "EQUITY":       "Common Equity - Total",
    "BV":           "Common Equity - Total",

    # Cash Flow
    "CFO":          "Net Cash Flow from Operating Activities",
    "CAPEX":        "Capital Expenditures - Net - Cash Flow",
    "FCF":          "Free Cash Flow",

    # Returns / Profitability (Financial Summary)
    "ROE":          "Return on Average Common Equity - % (Income available to Common excluding Extraordinary Items)",
    "ROA":          "Return on Average Total Assets - % (Income before Discontinued Operations & Extraordinary Items)",
    "ROIC":         "Return on Invested Capital - %",
    "GPM":          "Gross Profit Margin - %",
    "EBITDA MARGIN":"EBITDA Margin - %",
    "EBIT MARGIN":  "Operating Margin - %",
    "NET MARGIN":   "Net Margin - %",

    # RI — Total Return Index (appears in some CF exports as a price-relative series)
    "RI":           "Price Close (End of Period)",

    # ESG
    "ESG":          "ESG Score",
    "ESGC":         "ESG Combined Score (with Controversies)",
    "ENV":          "Environment Pillar Score",
    "SOC":          "Social Pillar Score",
    "GOV":          "Governance Pillar Score",
    "RESOURCE":     "Resource Use Score",
    "EMISSIONS":    "Emissions Score",
    "INNOVATION":   "Innovation Score",
    "WORKFORCE":    "Workforce Score",
    "HUMAN RIGHTS": "Human Rights Score",
    "COMMUNITY":    "Community Score",
    "PRODUCT RESP": "Product Responsibility Score",
    "MGMT SCORE":   "Management Score",
    "SHAREHOLDERS": "Shareholders Score",
    "CSR":          "CSR Strategy Score",

    # Estimates
    "REV EST":      "Revenue Estimate (Consensus Mean)",
    "EBITDA EST":   "EBITDA Estimate (Consensus Mean)",
    "NI EST":       "Net Income Estimate (Consensus Mean)",
    "EPS EST":      "EPS Estimate (Consensus Mean)",
    "PT":           "Price Target (Consensus Mean)",
    "PRICE TARGET": "Price Target (Consensus Mean)",
}
