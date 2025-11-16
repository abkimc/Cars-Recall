import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlencode
import plotly.express as px

# ----------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------
st.set_page_config(page_title="לוח בקרה - ריקולים לרכבים", layout="wide")

# Add RTL CSS for Hebrew alignment
st.markdown("""
<style>
    .stApp {
        direction: rtl;
    }
    .stTextInput > div > div > input {
        direction: rtl;
        text-align: right;
    }
    .stTextArea textarea {
        direction: rtl;
        text-align: right;
    }
    h1, h2, h3, h4, h5, h6, p, div, span {
        direction: rtl;
        text-align: right;
    }
</style>
""", unsafe_allow_html=True)

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
# CLEAN COLUMN NAMES (normalize to uppercase as in API)
# ----------------------------------------------------------
recalls.columns = recalls.columns.str.upper()
private.columns = private.columns.str.upper()
unattended.columns = unattended.columns.str.upper()

# Debug: Show available columns
st.sidebar.write("עמודות זמינות:")
st.sidebar.write("Recalls:", list(recalls.columns))
st.sidebar.write("Private:", list(private.columns))
st.sidebar.write("Unattended:", list(unattended.columns))

# Hebrew column mapping
HEBREW_COLUMNS = {
    # Unattended table
    "MISPAR_RECHEV": "מספר רכב",
    "RECALL_ID": "מזהה ריקול",
    "SUG_RECALL": "סוג ריקול",
    "SUG_TAKALA": "סוג תקלה",
    "TEUR_TAKALA": "תיאור תקלה",
    "TAARICH_PTICHA": "תאריך פתיחה",
    
    # Recalls table
    "TOZAR_CD": "קוד יצרן",
    "TOZAR_TEUR": "יצרן",
    "DEGEM": "דגם",
    "SHNAT_RECALL": "שנת ריקול",
    "BUILD_BEGIN_A": "תחילת ייצור",
    "BUILD_END_A": "סוף ייצור",
    "OFEN_TIKUN": "אופן תיקון",
    "TKINA_EU": "תקנה EU",
    "YEVUAN_TEUR": "יבואן",
    "TELEPHONE": "טלפון",
    "WEBSITE": "אתר",
    
    # Private vehicles table
    "TOZERET_CD": "קוד יצרן",
    "SUG_DEGEM": "סוג דגם",
    "TOZERET_NM": "יצרן",
    "DEGEM_CD": "קוד דגם",
    "DEGEM_NM": "דגם",
    "RAMAT_GIMUR": "רמת גימור",
    "SHNAT_YITZUR": "שנת ייצור",
    "TZEVA_RECHEV": "צבע רכב",
    "SUG_DELEK_NM": "סוג דלק",
    "KINUY_MISHARI": "כינוי מסחרי"
}


# ----------------------------------------------------------
# PLATE LOOKUP TOOL
# ----------------------------------------------------------
st.subheader("🔍 בדיקת מספר רישוי לריקולים שלא טופלו")

plate_input = st.text_input("הזן מספר רישוי (ספרות בלבד):")

if plate_input:
    try:
        plate_num = int(plate_input.strip())
        
        # Convert MISPAR_RECHEV to numeric if not already
        unattended["MISPAR_RECHEV"] = pd.to_numeric(unattended["MISPAR_RECHEV"], errors="coerce")
        
        match = unattended[unattended["MISPAR_RECHEV"] == plate_num]

        if len(match) > 0:
            st.error("⚠️ לרכב שלך יש ריקול שלא טופל!")

            # Get available columns
            available_cols = list(match.columns)
            st.write(f"עמודות זמינות: {available_cols}")
            
            # Merge with recalls to get SUG_TAKALA and TEUR_TAKALA if they exist
            if "RECALL_ID" in match.columns and "RECALL_ID" in recalls.columns:
                match_with_details = match.merge(
                    recalls[["RECALL_ID", "SUG_TAKALA", "TEUR_TAKALA"]],
                    on="RECALL_ID",
                    how="left"
                )
            else:
                match_with_details = match

            # Show all available data
            st.write("פרטי הריקול:")
            
            # Create display dataframe with Hebrew column names
            display_match = match_with_details.copy()
            display_match.columns = [HEBREW_COLUMNS.get(col, col) for col in display_match.columns]
            
            st.dataframe(display_match)
        else:
            st.success("✔️ הרכב שלך לא מופיע במאגר הריקולים שלא טופלו.")
    except Exception as e:
        st.error(f"שגיאה: {str(e)}")
        st.write(f"ניסית להזין: {plate_input}")


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

st.sidebar.write("Joined columns:", list(joined.columns))


# ----------------------------------------------------------
# SECTIONS (SCROLLABLE, NOT TABS)
# ----------------------------------------------------------
st.write("---")


# ----------------------------------------------------------
# SECTION 1 — Which Recall Affected Most Vehicles?
# ----------------------------------------------------------
st.header("🚗 ריקולים שהשפיעו על מספר הרכבים הגבוה ביותר")

# Find the correct MISPAR_RECHEV column name after merge
mispar_col = None
for col in joined.columns:
    if "MISPAR_RECHEV" in col:
        mispar_col = col
        break

# Check which columns exist after merge
if mispar_col and "SUG_TAKALA_RC" in joined.columns and "TEUR_TAKALA_RC" in joined.columns:
    recall_counts = (
        joined.groupby(["RECALL_ID", "SUG_TAKALA_RC", "TEUR_TAKALA_RC"])
        .agg(vehicles_affected=(mispar_col, "count"))
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
elif mispar_col:
    # Fallback: use only RECALL_ID
    recall_counts = (
        joined.groupby("RECALL_ID")
        .agg(vehicles_affected=(mispar_col, "count"))
        .sort_values("vehicles_affected", ascending=False)
        .reset_index()
    )
    
    recall_counts_display = recall_counts.head(20).copy()
    recall_counts_display.columns = ["מזהה ריקול", "מספר רכבים מושפעים"]
    
    fig1 = px.bar(
        recall_counts_display,
        x="מזהה ריקול",
        y="מספר רכבים מושפעים",
        title="20 הריקולים המובילים לפי מספר רכבים מושפעים"
    )
    st.plotly_chart(fig1, use_container_width=True)
else:
    st.error("לא נמצא עמודת MISPAR_RECHEV בנתונים המאוחדים")

st.subheader("💬 הערות")
st.text_area("הוסף הערות על ריקולים משפיעים:", key="comments_1", height=100)

st.write("---")


# ----------------------------------------------------------
# SECTION 2 — Recalls Over Time
# ----------------------------------------------------------
st.header("📈 ריקולים לאורך זמן לפי יצרן")

if "SHNAT_RECALL" in recalls.columns:
    recalls["SHNAT_RECALL"] = pd.to_numeric(recalls["SHNAT_RECALL"], errors="coerce")

trend = (
    recalls.groupby(["SHNAT_RECALL", "TOZAR_TEUR"])
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

if mispar_col:
    total_affected = (
        joined.groupby("RECALL_ID")
        .agg(total=(mispar_col, "count"))
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

    perf_by_importer = performance.groupby("YEVUAN_TEUR")["attendance_rate"].mean().reset_index()
    perf_by_importer.columns = ["יבואן", "אחוז ממוצע של טיפול בריקולים"]

    fig3 = px.bar(
        perf_by_importer,
        x="יבואן",
        y="אחוז ממוצע של טיפול בריקולים",
        title="ביצועי יבואנים (אחוז ממוצע של טיפול בריקולים)"
    )
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.error("לא ניתן לחשב ביצועי יבואנים - חסרה עמודת MISPAR_RECHEV")

st.subheader("💬 הערות")
st.text_area("הוסף הערות על ביצועי יבואנים:", key="comments_3", height=100)

st.write("---")


# ----------------------------------------------------------
# SECTION 4 — Recall Severity Distribution
# ----------------------------------------------------------
st.header("⚠️ התפלגות סוגי ריקולים (חומרה)")

if "SUG_TAKALA" in recalls.columns:
    severity_dist = recalls["SUG_TAKALA"].value_counts().reset_index()
    severity_dist.columns = ["סוג תקלה", "מספר ריקולים"]
    
    fig4 = px.bar(
        severity_dist,
        x="סוג תקלה",
        y="מספר ריקולים",
        title="התפלגות סוגי תקלות ריקול"
    )
    st.plotly_chart(fig4, use_container_width=True)
else:
    st.warning("השדה SUG_TAKALA לא נמצא בנתוני ה-API.")

st.subheader("💬 הערות")
st.text_area("הוסף הערות על חומרת ריקולים:", key="comments_4", height=100)

st.write("---")
st.caption("מקור נתונים: data.gov.il | זהו פרויקט אישי לתיק עבודות.")