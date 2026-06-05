"""
app/app.py — Streamlit interface for searching and viewing financial variables.

Run with:
    streamlit run app/app.py
"""

import os
import sys
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = os.environ.get("FINDATA_DB", str(Path(__file__).parent.parent / "data" / "findata.duckdb"))

st.set_page_config(
    page_title="Financial Data Explorer",
    page_icon="📊",
    layout="wide",
)

# ── DB connection (cached) ─────────────────────────────────────────────────────

@st.cache_resource
def get_con():
    return duckdb.connect(DB_PATH, read_only=True)


def q(sql: str, params=None):
    con = get_con()
    if params:
        return con.execute(sql, params).df()
    return con.execute(sql).df()


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📊 FinData Explorer")
    st.caption("Powered by Refinitiv CF Exports")
    st.divider()

    mode = st.radio(
        "View mode",
        ["🔍 Variable Search", "🏢 Company View", "📋 Cross-Company"],
        label_visibility="collapsed",
    )

    st.divider()

    # Stats
    try:
        n_companies = q("SELECT COUNT(DISTINCT ric) AS n FROM facts")["n"].iloc[0]
        n_variables = q("SELECT COUNT(DISTINCT variable) AS n FROM facts")["n"].iloc[0]
        st.metric("Companies", f"{int(n_companies):,}")
        st.metric("Variables", f"{int(n_variables):,}")
    except Exception:
        st.warning("Database not found.")

    st.divider()
    st.caption(f"DB: `{DB_PATH}`")


# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_year(series: pd.Series) -> pd.Series:
    """Normalize any date-like string to a 4-digit year for consistent pivot alignment."""
    s = series.astype(str)
    # Extract the 4-digit year from any format: '30-06-2024', '31-12-2022', '2013', etc.
    return s.str.extract(r"(\d{4})", expand=False).fillna(s)


def build_variable_options() -> tuple[list[str], dict[str, str]]:
    """
    Returns (options, label_to_var) where options are formatted as
    'ALIAS — Full Variable Name' for aliased vars and 'Full Variable Name'
    for the rest. Both alias code and full name are searchable in one field.
    """
    vars_list = q("SELECT DISTINCT variable FROM facts ORDER BY variable")["variable"].tolist()
    try:
        alias_rows = q("SELECT alias, variable FROM aliases ORDER BY alias")
        var_to_alias = {}
        for _, row in alias_rows.iterrows():
            if row["variable"] not in var_to_alias:
                var_to_alias[row["variable"]] = row["alias"]
    except Exception:
        var_to_alias = {}

    aliased, unaliased, label_to_var = [], [], {}
    for var in vars_list:
        if var in var_to_alias:
            label = f"{var_to_alias[var]} — {var}"
            aliased.append(label)
        else:
            label = var
            unaliased.append(label)
        label_to_var[label] = var

    return aliased + unaliased, label_to_var


def resolve_variable(search: str) -> list[str]:
    """
    Given a search string, return matching variable names.
    Priority: 1) exact alias match, 2) fuzzy variable name match.
    """
    term = search.strip().upper()
    if not term:
        return []

    # Exact alias
    alias_match = q(
        "SELECT variable FROM aliases WHERE upper(alias) = ?", [term]
    )
    if not alias_match.empty:
        return alias_match["variable"].tolist()

    # Fuzzy match on variable name
    fuzzy = q(
        "SELECT DISTINCT variable FROM facts WHERE upper(variable) LIKE ? ORDER BY variable LIMIT 30",
        [f"%{term}%"],
    )
    return fuzzy["variable"].tolist() if not fuzzy.empty else []


# ─────────────────────────────────────────────────────────────────────────────
# MODE 1: Variable Search
# ─────────────────────────────────────────────────────────────────────────────

if mode == "🔍 Variable Search":
    st.header("Variable Search")
    st.caption("Search by shorthand (PTBV, EV, ROE) or partial variable name.")

    var_options, label_to_var = build_variable_options()

    selected_label = st.selectbox(
        "Search variable",
        options=var_options,
        index=None,
        placeholder="Type to search — e.g. RI, Return Index, revenue",
    )

    selected_var = label_to_var.get(selected_label) if selected_label else None

    if selected_var:
        # Get all data for this variable
        df = q(
            """
            SELECT ric, company_name, year, value, currency, scaling, sheet
            FROM facts
            WHERE variable = ?
            ORDER BY company_name, year
            """,
            [selected_var],
        )
        if not df.empty:
            df["year"] = clean_year(df["year"])

        if df.empty:
            st.info("No data for this variable.")
        else:
            st.divider()

            col1, col2, col3 = st.columns(3)
            col1.metric("Companies", df["ric"].nunique())
            col2.metric("Years covered", df["year"].nunique())
            col3.metric("Data points", len(df))

            currencies = df["currency"].dropna().unique()
            currency_str = ", ".join(currencies) if len(currencies) else ""
            base_scaling = df["scaling"].dropna().iloc[0] if not df["scaling"].dropna().empty else "Millions"

            # Sheets where values are monetary (scaling applies)
            FINANCIAL_SHEETS = {"Balance Sheet", "Cash Flow", "Income Statement",
                                 "Geographic Line By Se", "Geographic Line By St", "Financial Summary"}
            sheets_in_data = set(df["sheet"].dropna().unique())
            scaling_applies = bool(sheets_in_data & FINANCIAL_SHEETS)

            SCALE_OPTIONS = {"Thousands": 1_000, "Millions": 1_000_000, "Billions": 1_000_000_000, "Trillions": 1_000_000_000_000}
            BASE_FACTOR = SCALE_OPTIONS.get(base_scaling, 1_000_000)

            if scaling_applies:
                display_unit = st.selectbox(
                    "Unit",
                    list(SCALE_OPTIONS.keys()),
                    index=list(SCALE_OPTIONS.keys()).index(base_scaling) if base_scaling in SCALE_OPTIONS else 1,
                    key="vs_unit",
                )
                scale_factor = BASE_FACTOR / SCALE_OPTIONS[display_unit]
                unit_label = f"{currency_str} {display_unit}".strip() if currency_str else display_unit
            else:
                display_unit = base_scaling
                scale_factor = 1.0
                unit_label = currency_str if currency_str else "As reported"
                st.caption(f"Unit: {unit_label} (per share / ratio — scaling not applicable)")
            st.caption("⚠️ Year labels show fiscal year — each company's value is as of its own fiscal year-end date (e.g. Jun-2022 for PSO, Dec-2022 for Engro). Use Company View to see exact period-end dates.")

            display_df = df.copy()
            display_df["value"] = display_df["value"] * scale_factor

            pivot = display_df.pivot_table(
                index=["company_name", "ric"],
                columns="year",
                values="value",
                aggfunc="first",
            )
            pivot.columns.name = None
            pivot = pivot.reset_index()

            st.subheader("Data table")
            st.dataframe(pivot, use_container_width=True, height=300)

            # Time-series chart (for single company or multi)
            st.subheader("Time series")
            companies_available = sorted(df["company_name"].unique())
            selected_companies = st.multiselect(
                "Companies to plot",
                companies_available,
                default=companies_available[:5],
            )
            if selected_companies:
                plot_df = display_df[display_df["company_name"].isin(selected_companies)].copy()
                plot_df = plot_df.sort_values("year")
                y_label = f"{selected_var} ({unit_label})"

                fig = px.line(
                    plot_df,
                    x="year",
                    y="value",
                    color="company_name",
                    markers=True,
                    title=selected_var,
                    labels={"year": "Year", "value": y_label, "company_name": "Company"},
                )
                fig.update_layout(legend_title_text="", hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

            # Download
            st.download_button(
                "Download CSV",
                display_df.to_csv(index=False),
                file_name=f"{selected_var[:40]}.csv",
                mime="text/csv",
            )


# ─────────────────────────────────────────────────────────────────────────────
# MODE 2: Company View
# ─────────────────────────────────────────────────────────────────────────────

elif mode == "🏢 Company View":
    st.header("Company View")
    st.caption("Browse all variables for a single company.")

    # Company selector
    companies_df = q(
        "SELECT DISTINCT ric, company_name FROM facts ORDER BY company_name"
    )
    if companies_df.empty:
        st.warning("No companies in database yet.")
    else:
        company_options = {
            f"{row['company_name']} ({row['ric']})": row["ric"]
            for _, row in companies_df.iterrows()
        }
        selected_label = st.selectbox("Select company", list(company_options.keys()))
        selected_ric = company_options[selected_label]

        # Sheet filter
        sheets = q(
            "SELECT DISTINCT sheet FROM facts WHERE ric = ? ORDER BY sheet",
            [selected_ric],
        )["sheet"].tolist()

        selected_sheet = st.selectbox("Sheet", ["(All)"] + sheets)

        sheet_filter = "" if selected_sheet == "(All)" else f"AND sheet = '{selected_sheet}'"

        # Variable search within company
        var_search = st.text_input("Filter variables", placeholder="e.g. revenue, margin, price")
        var_filter = f"AND upper(variable) LIKE '%{var_search.upper()}%'" if var_search else ""

        df = q(
            f"""
            SELECT sheet, section, variable, year, value, currency, scaling
            FROM facts
            WHERE ric = ? {sheet_filter} {var_filter}
            ORDER BY sheet, section, variable, year
            """,
            [selected_ric],
        )
        if not df.empty:
            df["year"] = clean_year(df["year"])

        if df.empty:
            st.info("No data found.")
        else:
            # Pivot to wide format: variable as rows, years as columns
            pivot = df.pivot_table(
                index=["sheet", "section", "variable"],
                columns="year",
                values="value",
                aggfunc="first",
            )
            pivot.columns.name = None
            pivot = pivot.reset_index()

            st.metric("Variables shown", len(pivot))
            st.dataframe(pivot, use_container_width=True, height=500)

            # Chart: pick a variable
            st.divider()
            st.subheader("Plot a variable")
            var_list = sorted(df["variable"].unique())
            chart_var = st.selectbox("Variable to chart", var_list)

            chart_df = df[df["variable"] == chart_var].copy()
            chart_df = chart_df.sort_values("year")

            fig = px.bar(
                chart_df,
                x="year",
                y="value",
                title=chart_var,
                labels={"year": "Year", "value": chart_var},
            )
            st.plotly_chart(fig, use_container_width=True)

            st.download_button(
                "Download CSV",
                df.to_csv(index=False),
                file_name=f"{selected_ric}.csv",
                mime="text/csv",
            )


# ─────────────────────────────────────────────────────────────────────────────
# MODE 3: Cross-Company (single variable, single year, ranked)
# ─────────────────────────────────────────────────────────────────────────────

elif mode == "📋 Cross-Company":
    st.header("Cross-Company Comparison")
    st.caption("Rank all companies by a variable for a given year.")

    col1, col2 = st.columns([3, 1])

    var_options, label_to_var = build_variable_options()

    with col1:
        selected_label = st.selectbox(
            "Variable",
            options=var_options,
            index=None,
            placeholder="Type to search — e.g. RI, Return Index, ROE",
        )
    with col2:
        years_df = q("SELECT DISTINCT year FROM facts ORDER BY year DESC")
        if not years_df.empty:
            years_df["year"] = clean_year(years_df["year"])
            years_df = years_df.drop_duplicates().sort_values("year", ascending=False)
        selected_year = st.selectbox("Year", years_df["year"].tolist() if not years_df.empty else [])

    selected_var = label_to_var.get(selected_label) if selected_label else None

    if selected_var and selected_year:
        df = q(
            """
            SELECT ric, company_name, value, currency, scaling
            FROM facts
            WHERE variable = ? AND year LIKE ?
            ORDER BY value DESC
            """,
            [selected_var, f"%{selected_year}%"],
        )

        if df.empty:
            st.info("No data for this variable / year combination.")
        else:
            st.success(f"**{selected_var}** · {selected_year} · {len(df)} companies")

            # Bar chart
            fig = px.bar(
                df.head(50),
                x="value",
                y="company_name",
                orientation="h",
                title=f"{selected_var} — {selected_year} (top 50)",
                labels={"value": selected_var, "company_name": ""},
                height=max(400, len(df.head(50)) * 22),
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df, use_container_width=True)
            st.download_button(
                "Download CSV",
                df.to_csv(index=False),
                file_name=f"{selected_var[:30]}_{selected_year}.csv",
                mime="text/csv",
            )
