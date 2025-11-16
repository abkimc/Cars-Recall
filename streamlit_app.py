import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlencode
import plotly.express as px

# ----------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------
st.set_page_config(page_title="Vehicle Recall Dashboard", layout="wide")

st.title("📊 Israel Vehicle Recall Dashboard")
st.write("Live data fetched directly from the Israeli government open-data API.")

# ----------------------------------------------------------
# CONSTANTS – API RESOURCE IDs
# ----------------------------------------------------------
RECALLS_RID = "2c33523f-87aa-44ec-a736-edbb0a82975e"
PRIVATE_RID = "053cea08-09bc-40ec-8f7a-156f0677aff3"
UNATTENDED_RID = "36bf1404-0be4-49d2-82dc-2f1ead4a8b93"

API_BASE = "https://data.gov.il/api/3/action/datastore_search"


# ----------------------------------------------------------
# API FETCHER WITH PAGINATION
# ----------------------------------------------------------
@st.cache_data(show_spinner=True)
def fetch_full_table(resource_id, max_rows=50000):
    """Fetches up to max_rows rows from the CKAN API with pagination."""
    all_records = []
    limit = 5000
    offset = 0

    while True:
        params = {
            "resource_id": resource_id,
            "limit": limit,
            "offset": offset
        }

        url = API_BASE + "?" + urlencode(params)
        response = requests.get(url)

        if response.status_code != 200:
            st.error(f"API error: {response.text}")
            break

        data = response.json()["result"]["records"]
        if not data:
            break

        all_records.extend(data)
        offset += limit

        if len(all_records) >= max_rows:
            break

    df = pd.DataFrame(all_records)
    return df


# ----------------------------------------------------------
# LOAD DATA (LIMITED FOR STREAMLIT PERFORMANCE)
# ----------------------------------------------------------
st.sidebar.header("⚙️ Settings")
MAX_ROWS = st.sidebar.slider("Maximum rows to fetch per table:", 5000, 150000, 50000)

with st.spinner("Downloading live data from data.gov.il..."):
    recalls = fetch_full_table(RECALLS_RID, MAX_ROWS)
    private = fetch_full_table(PRIVATE_RID, MAX_ROWS)
    unattended = fetch_full_table(UNATTENDED_RID, MAX_ROWS)

st.success("Data loaded successfully.")

# ----------------------------------------------------------
# CLEAN COLUMN NAMES (normalize)
# ----------------------------------------------------------
recalls.columns = recalls.columns.str.upper()
private.columns = private.columns.str.upper()
unattended.columns = unattended.columns.str.upper()


# ----------------------------------------------------------
# PLATE LOOKUP TOOL
# ----------------------------------------------------------
st.subheader("🔍 Check if your license plate has an unattended recall")

plate_input = st.text_input("Enter license plate number (digits only):")

if plate_input:
    try:
        plate_num = int(plate_input.strip())
        match = unattended[unattended["MISPAR_RECHEV"] == plate_num]

        if len(match) > 0:
            st.error("⚠️ Your vehicle HAS an unattended recall.")

            # Merge with recalls to get SUG_TAKALA and TEUR_TAKALA
            match_with_details = match.merge(
                recalls[["RECALL_ID", "SUG_TAKALA", "TEUR_TAKALA"]],
                on="RECALL_ID",
                how="left"
            )

            st.write(match_with_details[["RECALL_ID", "SUG_RECALL", "SUG_TAKALA", "TEUR_TAKALA", "TAARICH_PTICHA"]])
        else:
            st.success("✔️ Your vehicle is NOT listed in the unattended recall database.")
    except:
        st.error("Invalid number.")


# ----------------------------------------------------------
# JOIN: For later graphs
# ----------------------------------------------------------
# Ensure numeric
private["MISPAR_RECHEV"] = pd.to_numeric(private["MISPAR_RECHEV"], errors="coerce")
unattended["MISPAR_RECHEV"] = pd.to_numeric(unattended["MISPAR_RECHEV"], errors="coerce")

# Merge by TOZERET_CD (manufacturer) and DEGEM_NM (model)
joined = private.merge(
    recalls,
    left_on=["TOZERET_CD", "DEGEM_NM"],
    right_on=["TOZAR_CD", "DEGEM"],
    how="inner",
    suffixes=("_PR", "_RC")
)


# ----------------------------------------------------------
# DASHBOARD TABS
# ----------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Most Impactful Recalls",
    "Recalls Over Time",
    "Importer Performance",
    "Recall Severity Distribution"
])


# ----------------------------------------------------------
# TAB 1 — Which Recall Affected Most Vehicles?
# ----------------------------------------------------------
with tab1:
    st.subheader("🚗 Recalls That Affected the Most Vehicles")

    recall_counts = (
        joined.groupby(["RECALL_ID", "SUG_TAKALA_RC", "TEUR_TAKALA_RC"])
        .agg(vehicles_affected=("MISPAR_RECHEV_PR", "count"))
        .sort_values("vehicles_affected", ascending=False)
        .reset_index()
    )

    fig = px.bar(
        recall_counts.head(20),
        x="RECALL_ID",
        y="vehicles_affected",
        hover_data=["SUG_TAKALA_RC", "TEUR_TAKALA_RC"],
        title="Top Recalls by Number of Affected Vehicles"
    )
    st.plotly_chart(fig, use_container_width=True)


# ----------------------------------------------------------
# TAB 2 — Recalls Over Time
# ----------------------------------------------------------
with tab2:
    st.subheader("📈 Recalls Over Time by Manufacturer")

    if "SHNAT_RECALL" in recalls.columns:
        recalls["SHNAT_RECALL"] = pd.to_numeric(recalls["SHNAT_RECALL"], errors="coerce")

    trend = (
        recalls.groupby(["SHNAT_RECALL", "TOZAR_TEUR"])
        .size()
        .reset_index(name="count")
    )

    fig = px.line(
        trend,
        x="SHNAT_RECALL",
        y="count",
        color="TOZAR_TEUR",
        title="Number of Recalls per Manufacturer Over Time"
    )
    st.plotly_chart(fig, use_container_width=True)


# ----------------------------------------------------------
# TAB 3 — Importer Performance (Attendance Rates)
# ----------------------------------------------------------
with tab3:
    st.subheader("🏭 Importer Recall Attendance Performance")

    total_affected = (
        joined.groupby("RECALL_ID")
        .agg(total=("MISPAR_RECHEV_PR", "count"))
    )

    unattended_count = (
        unattended.groupby("RECALL_ID")
        .size()
        .to_frame("unattended")
    )

    performance = total_affected.join(unattended_count, how="left").fillna(0)
    performance["attendance_rate"] = (
        (1 - performance["unattended"] / performance["total"]) * 100
    )

    # Join importer
    performance = performance.merge(
        recalls[["RECALL_ID", "YEVUAN_TEUR"]],
        on="RECALL_ID",
        how="left"
    )

    fig = px.bar(
        performance.groupby("YEVUAN_TEUR")["attendance_rate"].mean().reset_index(),
        x="YEVUAN_TEUR",
        y="attendance_rate",
        title="Importer Performance (Average Recall Attendance Rate)"
    )
    st.plotly_chart(fig, use_container_width=True)


# ----------------------------------------------------------
# TAB 4 — Recall Severity Distribution
# ----------------------------------------------------------
with tab4:
    st.subheader("⚠️ Distribution of Recall Types (Severity)")

    if "SUG_TAKALA" in recalls.columns:
        fig = px.histogram(
            recalls,
            x="SUG_TAKALA",
            title="Distribution of Recall Types (SUG_TAKALA)"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Field SUG_TAKALA not found in API data.")


st.write("---")
st.caption("Data Source: data.gov.il | This is a personal portfolio project.")
