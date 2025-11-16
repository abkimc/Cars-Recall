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

# Max rows constant
MAX_ROWS = 50000


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
# LOAD DATA
# ----------------------------------------------------------
with st.spinner("מוריד נתונים חיים מ-data.gov.il..."):
    recalls = fetch_full_table(RECALLS_RID, MAX_ROWS)
    private = fetch_full_table(PRIVATE_RID, MAX_ROWS)
    unattended = fetch_full_table(UNATTENDED_RID, MAX_ROWS)

st.success("הנתונים נטענו בהצלחה.")

# ----------------------------------------------------------
# CLEAN COLUMN NAMES (normalize to uppercase to match actual API response)
# ----------------------------------------------------------
recalls.columns = recalls.columns.str.upper()
private.columns = private.columns.str.upper()
unattended.columns = unattended.columns.str.upper()

# Hebrew column mapping for display
HEBREW_COLUMNS = {
    "MISPAR_RECHEV": "מספר רכב",
    "RECALL_ID": "מזהה ריקול",
    "SUG_RECALL": "סוג ריקול",
    "SUG_TAKALA": "סוג תקלה",
    "TEUR_TAKALA": "תיאור תקלה",
    "TAARICH_PTICHA": "תאריך פתיחה",
}


# ----------------------------------------------------------
# PLATE LOOKUP TOOL
# ----------------------------------------------------------
st.subheader("🔍 בדיקת מספר רישוי לריקולים שלא טופלו")

plate_input = st.text_input("הזן מספר רישוי (ספרות בלבד):")

if plate_input:
    try:
        plate_num = int(plate_input.strip())
        match = unattended[unattended["MISPAR_RECHEV"] == plate_num]

        if len(match) > 0:
            st.error("⚠️ לרכב שלך יש ריקול שלא טופל!")

            # Merge with recalls to get SUG_TAKALA and TEUR_TAKALA
            match_with_details = match.merge(
                recalls[["RECALL_ID", "SUG_TAKALA", "TEUR_TAKALA"]],
                on="RECALL_ID",
                how="left"
            )

            # Rename columns to Hebrew for display
            display_cols = ["RECALL_ID", "SUG_RECALL", "SUG_TAKALA", "TEUR_TAKALA", "TAARICH_PTICHA"]
            display_match = match_with_details[display_cols].copy()
            display_match.columns = [HEBREW_COLUMNS.get(col, col) for col in display_match.columns]
            
            # Style the dataframe for RTL
            th_props = [
                ('text-align', 'right'),
                ('direction', 'rtl')
            ]
            
            td_props = [
                ('text-align', 'right'),
                ('direction', 'rtl')
            ]
            
            styles = [
                dict(selector="th", props=th_props),
                dict(selector="td", props=td_props)
            ]
            
            styled_df = display_match.style.set_properties(**{'text-align': 'right', 'direction': 'rtl'}).set_table_styles(styles)
            
            st.table(styled_df)
        else:
            st.success("✔️ הרכב שלך לא מופיע במאגר הריקולים שלא טופלו.")
    except Exception as e:
        st.error("מספר לא תקין.")


# ----------------------------------------------------------
# JOIN: For later graphs
# ----------------------------------------------------------
# Ensure numeric
private["MISPAR_RECHEV"] = pd.to_numeric(private["MISPAR_RECHEV"], errors="coerce")
unattended["MISPAR_RECHEV"] = pd.to_numeric(unattended["MISPAR_RECHEV"], errors="coerce")

# Merge by manufacturer and model
joined = private.merge(
    recalls,
    left_on=["TOZERET_CD", "DEGEM_NM"],
    right_on=["TOZAR_CD", "DEGEM"],
    how="inner",
    suffixes=("_PR", "_RC")
)


# ----------------------------------------------------------
# SECTIONS (SCROLLABLE)
# ----------------------------------------------------------
st.write("---")


# ----------------------------------------------------------
# SECTION 1 — Which Recall Affected Most Vehicles?
# ----------------------------------------------------------
st.header("🚗 ריקולים שהשפיעו על מספר הרכבים הגבוה ביותר")

if len(joined) > 0:
    recall_counts = (
        joined.groupby("RECALL_ID")
        .agg(
            vehicles_affected=("MISPAR_RECHEV_PR", "count"),
            sug_takala=("SUG_TAKALA_RC", "first"),
            teur_takala=("TEUR_TAKALA_RC", "first")
        )
        .sort_values("vehicles_affected", ascending=False)
        .reset_index()
        .head(20)
    )

    fig1 = px.bar(
        recall_counts,
        x="RECALL_ID",
        y="vehicles_affected",
        hover_data=["sug_takala", "teur_takala"],
        title="20 הריקולים המובילים לפי מספר רכבים מושפעים",
        labels={"vehicles_affected": "מספר רכבים מושפעים", "RECALL_ID": "מזהה ריקול"}
    )
    st.plotly_chart(fig1, use_container_width=True)
else:
    st.warning("אין נתונים זמינים לתצוגה.")

# Developer notes section
with st.expander("📝 הערות ותובנות"):
    st.text_area(
        "הוסף הערות מפתח והסברים על הגרף:",
        value="",
        height=150,
        key="dev_notes_1",
        help="שדה זה מיועד לתיעוד תובנות ומסקנות"
    )

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

    fig2 = px.line(
        trend,
        x="SHNAT_RECALL",
        y="count",
        color="TOZAR_TEUR",
        title="מספר ריקולים לפי יצרן לאורך זמן",
        labels={"SHNAT_RECALL": "שנת ריקול", "count": "מספר ריקולים", "TOZAR_TEUR": "יצרן"}
    )
    st.plotly_chart(fig2, use_container_width=True)

# Developer notes section
with st.expander("📝 הערות ותובנות"):
    st.text_area(
        "הוסף הערות מפתח והסברים על הגרף:",
        value="",
        height=150,
        key="dev_notes_2",
        help="שדה זה מיועד לתיעוד תובנות ומסקנות"
    )

st.write("---")


# ----------------------------------------------------------
# SECTION 3 — Importer Performance (Attendance Rates)
# ----------------------------------------------------------
st.header("🏭 ביצועי יבואנים - אחוזי טיפול בריקולים")

if len(joined) > 0:
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

    perf_by_importer = performance.groupby("YEVUAN_TEUR")["attendance_rate"].mean().reset_index()

    fig3 = px.bar(
        perf_by_importer,
        x="YEVUAN_TEUR",
        y="attendance_rate",
        title="ביצועי יבואנים (אחוז ממוצע של טיפול בריקולים)",
        labels={"YEVUAN_TEUR": "יבואן", "attendance_rate": "אחוז טיפול"}
    )
    st.plotly_chart(fig3, use_container_width=True)

# Developer notes section
with st.expander("📝 הערות ותובנות"):
    st.text_area(
        "הוסף הערות מפתח והסברים על הגרף:",
        value="",
        height=150,
        key="dev_notes_3",
        help="שדה זה מיועד לתיעוד תובנות ומסקנות"
    )

st.write("---")


# ----------------------------------------------------------
# SECTION 4 — Recall Severity Distribution
# ----------------------------------------------------------
st.header("⚠️ התפלגות סוגי ריקולים (חומרה)")

if "SUG_TAKALA" in recalls.columns:
    severity_dist = recalls["SUG_TAKALA"].value_counts().reset_index()
    severity_dist.columns = ["SUG_TAKALA", "count"]
    
    fig4 = px.bar(
        severity_dist,
        x="SUG_TAKALA",
        y="count",
        title="התפלגות סוגי תקלות ריקול",
        labels={"SUG_TAKALA": "סוג תקלה", "count": "מספר ריקולים"}
    )
    st.plotly_chart(fig4, use_container_width=True)
else:
    st.warning("השדה SUG_TAKALA לא נמצא בנתוני ה-API.")

# Developer notes section
with st.expander("📝 הערות ותובנות"):
    st.text_area(
        "הוסף הערות מפתח והסברים על הגרף:",
        value="",
        height=150,
        key="dev_notes_4",
        help="שדה זה מיועד לתיעוד תובנות ומסקנות"
    )

st.write("---")
st.caption("מקור נתונים: data.gov.il | זהו פרויקט אישי לתיק עבודות.")