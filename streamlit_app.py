import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlencode
import plotly.express as px

# ----------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------
st.set_page_config(page_title="לוח בקרה - ריקולים לרכבים", layout="wide")

st.title("📊 לוח בקרה - ריקולים לרכבים בישראל")
st.write("נתונים חיים ישירות מ-API של נתוני הממשלה הפתוחים.")

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
            st.error(f"שגיאת API: {response.text}")
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
st.sidebar.header("⚙️ הגדרות")
MAX_ROWS = st.sidebar.slider("מקסימום שורות לטעינה לכל טבלה:", 5000, 150000, 50000)

with st.spinner("מוריד נתונים חיים מ-data.gov.il..."):
    recalls = fetch_full_table(RECALLS_RID, MAX_ROWS)
    private = fetch_full_table(PRIVATE_RID, MAX_ROWS)
    unattended = fetch_full_table(UNATTENDED_RID, MAX_ROWS)

st.success("הנתונים נטענו בהצלחה.")

# ----------------------------------------------------------
# CLEAN COLUMN NAMES (normalize to lowercase to match API)
# ----------------------------------------------------------
recalls.columns = recalls.columns.str.lower()
private.columns = private.columns.str.lower()
unattended.columns = unattended.columns.str.lower()

# Hebrew column mapping
HEBREW_COLUMNS = {
    # Unattended table
    "mispar_rechev": "מספר רכב",
    "recall_id": "מזהה ריקול",
    "sug_recall": "סוג ריקול",
    "sug_takala": "סוג תקלה",
    "teur_takala": "תיאור תקלה",
    "taarich_pticha": "תאריך פתיחה",
    
    # Recalls table
    "tozar_cd": "קוד יצרן",
    "tozar_teur": "יצרן",
    "degem": "דגם",
    "shnat_recall": "שנת ריקול",
    "build_begin_a": "תחילת ייצור",
    "build_end_a": "סוף ייצור",
    "ofen_tikun": "אופן תיקון",
    "tkina_eu": "תקנה EU",
    "yevuan_teur": "יבואן",
    "telephone": "טלפון",
    "website": "אתר",
    
    # Private vehicles table
    "tozeret_cd": "קוד יצרן",
    "sug_degem": "סוג דגם",
    "tozeret_nm": "יצרן",
    "degem_cd": "קוד דגם",
    "degem_nm": "דגם",
    "ramat_gimur": "רמת גימור",
    "shnat_yitzur": "שנת ייצור",
    "tzeva_rechev": "צבע רכב",
    "sug_delek_nm": "סוג דלק",
    "kinuy_mishari": "כינוי מסחרי"
}


# ----------------------------------------------------------
# PLATE LOOKUP TOOL
# ----------------------------------------------------------
st.subheader("🔍 בדיקת מספר רישוי לריקולים שלא טופלו")

plate_input = st.text_input("הזן מספר רישוי (ספרות בלבד):")

if plate_input:
    try:
        plate_num = int(plate_input.strip())
        match = unattended[unattended["mispar_rechev"] == plate_num]

        if len(match) > 0:
            st.error("⚠️ לרכב שלך יש ריקול שלא טופל!")

            # Merge with recalls to get SUG_TAKALA and TEUR_TAKALA
            match_with_details = match.merge(
                recalls[["recall_id", "sug_takala", "teur_takala"]],
                on="recall_id",
                how="left"
            )

            # Rename columns to Hebrew for display
            display_match = match_with_details[["recall_id", "sug_recall", "sug_takala", "teur_takala", "taarich_pticha"]].copy()
            display_match.columns = [HEBREW_COLUMNS.get(col, col) for col in display_match.columns]
            
            st.write(display_match)
        else:
            st.success("✔️ הרכב שלך לא מופיע במאגר הריקולים שלא טופלו.")
    except:
        st.error("מספר לא תקין.")


# ----------------------------------------------------------
# JOIN: For later graphs
# ----------------------------------------------------------
# Ensure numeric
private["mispar_rechev"] = pd.to_numeric(private["mispar_rechev"], errors="coerce")
unattended["mispar_rechev"] = pd.to_numeric(unattended["mispar_rechev"], errors="coerce")

# Merge by TOZERET_CD (manufacturer) and DEGEM_NM (model)
joined = private.merge(
    recalls,
    left_on=["tozeret_cd", "degem_nm"],
    right_on=["tozar_cd", "degem"],
    how="inner",
    suffixes=("_pr", "_rc")
)


# ----------------------------------------------------------
# SECTIONS (SCROLLABLE, NOT TABS)
# ----------------------------------------------------------
st.write("---")


# ----------------------------------------------------------
# SECTION 1 — Which Recall Affected Most Vehicles?
# ----------------------------------------------------------
st.header("🚗 ריקולים שהשפיעו על מספר הרכבים הגבוה ביותר")

recall_counts = (
    joined.groupby(["recall_id", "sug_takala_rc", "teur_takala_rc"])
    .agg(vehicles_affected=("mispar_rechev_pr", "count"))
    .sort_values("vehicles_affected", ascending=False)
    .reset_index()
)

# Rename for display
recall_counts_display = recall_counts.head(20).copy()
recall_counts_display.columns = ["מזהה ריקול", "סוג תקלה", "תיאור תקלה", "מספר רכבים מושפעים"]

fig1 = px.bar(
    recall_counts_display,
    x="מזהה ריקול",
    y="מספר רכבים מושפעים",
    hover_data=["סוג תקלה", "תיאור תקלה"],
    title="20 הריקולים המובילים לפי מספר רכבים מושפעים"
)
st.plotly_chart(fig1, use_container_width=True)

st.subheader("💬 הערות")
st.text_area("הוסף הערות על ריקולים משפיעים:", key="comments_1", height=100)

st.write("---")


# ----------------------------------------------------------
# SECTION 2 — Recalls Over Time
# ----------------------------------------------------------
st.header("📈 ריקולים לאורך זמן לפי יצרן")

if "shnat_recall" in recalls.columns:
    recalls["shnat_recall"] = pd.to_numeric(recalls["shnat_recall"], errors="coerce")

trend = (
    recalls.groupby(["shnat_recall", "tozar_teur"])
    .size()
    .reset_index(name="count")
)

# Rename for display
trend_display = trend.copy()
trend_display.columns = ["שנת ריקול", "יצרן", "מספר ריקולים"]

fig2 = px.line(
    trend_display,
    x="שנת ריקול",
    y="מספר ריקולים",
    color="יצרן",
    title="מספר ריקולים לפי יצרן לאורך זמן"
)
st.plotly_chart(fig2, use_container_width=True)

st.subheader("💬 הערות")
st.text_area("הוסף הערות על מגמות ריקולים:", key="comments_2", height=100)

st.write("---")


# ----------------------------------------------------------
# SECTION 3 — Importer Performance (Attendance Rates)
# ----------------------------------------------------------
st.header("🏭 ביצועי יבואנים - אחוזי טיפול בריקולים")

total_affected = (
    joined.groupby("recall_id")
    .agg(total=("mispar_rechev_pr", "count"))
)

unattended_count = (
    unattended.groupby("recall_id")
    .size()
    .to_frame("unattended")
)

performance = total_affected.join(unattended_count, how="left").fillna(0)
performance["attendance_rate"] = (
    (1 - performance["unattended"] / performance["total"]) * 100
)

# Join importer
performance = performance.merge(
    recalls[["recall_id", "yevuan_teur"]],
    on="recall_id",
    how="left"
)

perf_by_importer = performance.groupby("yevuan_teur")["attendance_rate"].mean().reset_index()
perf_by_importer.columns = ["יבואן", "אחוז ממוצע של טיפול בריקולים"]

fig3 = px.bar(
    perf_by_importer,
    x="יבואן",
    y="אחוז ממוצע של טיפול בריקולים",
    title="ביצועי יבואנים (אחוז ממוצע של טיפול בריקולים)"
)
st.plotly_chart(fig3, use_container_width=True)

st.subheader("💬 הערות")
st.text_area("הוסף הערות על ביצועי יבואנים:", key="comments_3", height=100)

st.write("---")


# ----------------------------------------------------------
# SECTION 4 — Recall Severity Distribution
# ----------------------------------------------------------
st.header("⚠️ התפלגות סוגי ריקולים (חומרה)")

if "sug_takala" in recalls.columns:
    severity_dist = recalls["sug_takala"].value_counts().reset_index()
    severity_dist.columns = ["סוג תקלה", "מספר ריקולים"]
    
    fig4 = px.bar(
        severity_dist,
        x="סוג תקלה",
        y="מספר ריקולים",
        title="התפלגות סוגי תקלות ריקול"
    )
    st.plotly_chart(fig4, use_container_width=True)
else:
    st.warning("השדה sug_takala לא נמצא בנתוני ה-API.")

st.subheader("💬 הערות")
st.text_area("הוסף הערות על חומרת ריקולים:", key="comments_4", height=100)

st.write("---")
st.caption("מקור נתונים: data.gov.il | זהו פרויקט אישי לתיק עבודות.")