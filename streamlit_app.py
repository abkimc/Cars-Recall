import streamlit as st
import pandas as pd
import requests
from urllib.parse import urlencode
import plotly.express as px
import plotly.graph_objects as go

# ----------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------
st.set_page_config(page_title="לוח בקרה - ריקולים לרכבים", layout="wide")

# RTL CSS for Hebrew
st.markdown("""
<style>
    .main > div {
        direction: rtl;
    }
    h1, h2, h3, p, label {
        text-align: right;
        direction: rtl;
    }
    .stTextInput > label {
        text-align: right;
        direction: rtl;
    }
    .stTextInput input {
        text-align: right;
        direction: rtl;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------------
# HEADER - Portfolio Style
# ----------------------------------------------------------
st.title("📊 לוח בקרה מתקדם - ריקולים לרכבים בישראל")

st.markdown("""
### אודות הפרויקט
לוח בקרה זה מציג ניתוח מעמיק של נתוני ריקולים לרכבים בישראל, תוך שימוש בנתונים פתוחים של הממשלה.

**מטרת הדשבורד:**
- זיהוי מהיר של רכבים עם ריקולים שלא טופלו
- ניתוח מגמות ריקולים לאורך זמן
- הערכת ביצועי יבואנים בטיפול בריקולים
- זיהוי דגמים בעייתיים והתפלגות חומרת תקלות

**מקור הנתונים:** data.gov.il - פורטל הנתונים הפתוחים של ממשלת ישראל

---
*פרויקט אישי לתיק עבודות בתחום ניתוח נתונים ומדעי הנתונים*
""")

# ----------------------------------------------------------
# CONSTANTS
# ----------------------------------------------------------
RECALLS_RID = "2c33523f-87aa-44ec-a736-edbb0a82975e"
PRIVATE_RID = "053cea08-09bc-40ec-8f7a-156f0677aff3"
UNATTENDED_RID = "36bf1404-0be4-49d2-82dc-2f1ead4a8b93"

API_BASE = "https://data.gov.il/api/3/action/datastore_search"
MAX_ROWS = 50000

# ----------------------------------------------------------
# API FETCHER
# ----------------------------------------------------------
@st.cache_data(show_spinner=True)
def fetch_full_table(resource_id, max_rows=50000):
    all_records = []
    limit = 5000
    offset = 0

    while True:
        params = {"resource_id": resource_id, "limit": limit, "offset": offset}
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

    return pd.DataFrame(all_records)

# ----------------------------------------------------------
# LOAD DATA
# ----------------------------------------------------------
with st.spinner("🔄 טוען נתונים מ-API..."):
    recalls = fetch_full_table(RECALLS_RID, MAX_ROWS)
    private = fetch_full_table(PRIVATE_RID, MAX_ROWS)
    unattended = fetch_full_table(UNATTENDED_RID, MAX_ROWS)

st.success("✅ הנתונים נטענו בהצלחה")

# Normalize columns
recalls.columns = recalls.columns.str.upper()
private.columns = private.columns.str.upper()
unattended.columns = unattended.columns.str.upper()

# ----------------------------------------------------------
# INTERACTIVE PLATE LOOKUP
# ----------------------------------------------------------
st.markdown("---")
st.header("🔍 בדיקת מספר רישוי")
st.write("הזן את מספר הרישוי שלך כדי לבדוק אם יש ריקולים לא מטופלים")

plate_input = st.text_input("מספר רישוי (ספרות בלבד):", placeholder="לדוגמה: 12345678")

if plate_input:
    try:
        plate_num = int(plate_input.strip().replace("-", "").replace(" ", ""))
        match = unattended[unattended["MISPAR_RECHEV"] == plate_num]

        if len(match) > 0:
            st.error("⚠️ לרכב שלך יש ריקול שלא טופל!")
            
            # Get recall details
            recall_ids = match["RECALL_ID"].unique()
            recall_details = recalls[recalls["RECALL_ID"].isin(recall_ids)][
                ["RECALL_ID", "SUG_TAKALA", "TEUR_TAKALA", "TOZAR_TEUR", "DEGEM"]
            ]
            
            st.write("**פרטי הריקולים:**")
            
            # Display with Hebrew column names
            display_df = recall_details.copy()
            display_df.columns = ["מזהה ריקול", "סוג תקלה", "תיאור תקלה", "יצרן", "דגם"]
            
            st.dataframe(display_df, use_container_width=True)
            st.warning("⚠️ מומלץ לפנות ליבואן בהקדם לטיפול בריקול")
        else:
            st.success("✔️ הרכב שלך לא מופיע במאגר הריקולים שלא טופלו")
    except:
        st.error("❌ מספר לא תקין. אנא הזן ספרות בלבד")

st.markdown("---")

# ----------------------------------------------------------
# DATA PREPARATION FOR GRAPHS
# ----------------------------------------------------------

# Convert to numeric
private["MISPAR_RECHEV"] = pd.to_numeric(private["MISPAR_RECHEV"], errors="coerce")
private["SHNAT_YITZUR"] = pd.to_numeric(private["SHNAT_YITZUR"], errors="coerce")
recalls["SHNAT_RECALL"] = pd.to_numeric(recalls["SHNAT_RECALL"], errors="coerce")
recalls["BUILD_BEGIN_A"] = pd.to_numeric(recalls["BUILD_BEGIN_A"], errors="coerce")
recalls["BUILD_END_A"] = pd.to_numeric(recalls["BUILD_END_A"], errors="coerce")

# Join recalls with private vehicles
# Using TOZAR_CD = tozeret_cd, DEGEM = degem_nm, and year range
joined = private.merge(
    recalls,
    left_on=["TOZERET_CD", "DEGEM_NM"],
    right_on=["TOZAR_CD", "DEGEM"],
    how="inner",
    suffixes=("_PRIV", "_REC")
)

# Filter by year range
joined = joined[
    (joined["SHNAT_YITZUR"] >= joined["BUILD_BEGIN_A"]) &
    (joined["SHNAT_YITZUR"] <= joined["BUILD_END_A"])
]

# ----------------------------------------------------------
# GRAPH 1 - Which Recall Affected Most Vehicles
# ----------------------------------------------------------
st.header("📊 גרף 1: ריקולים שהשפיעו על מספר הרכבים הגבוה ביותר")

if len(joined) > 0:
    recall_impact = (
        joined.groupby(["RECALL_ID", "SUG_TAKALA", "TEUR_TAKALA", "TOZAR_TEUR"])
        .agg(vehicles_affected=("MISPAR_RECHEV_PRIV", "count"))
        .reset_index()
        .sort_values("vehicles_affected", ascending=False)
        .head(20)
    )
    
    fig1 = px.bar(
        recall_impact,
        x="RECALL_ID",
        y="vehicles_affected",
        color="vehicles_affected",
        hover_data=["SUG_TAKALA", "TEUR_TAKALA", "TOZAR_TEUR"],
        title="20 הריקולים עם מספר הרכבים המושפעים הגבוה ביותר",
        labels={"vehicles_affected": "מספר רכבים מושפעים", "RECALL_ID": "מזהה ריקול"},
        color_continuous_scale="Reds"
    )
    fig1.update_layout(height=500, showlegend=False)
    st.plotly_chart(fig1, use_container_width=True)
    
    st.info(f"📈 **תובנה עיקרית:** הריקול המשפיע ביותר מכסה {recall_impact.iloc[0]['vehicles_affected']:,} רכבים")
else:
    st.warning("אין נתונים זמינים לגרף זה")

with st.expander("📝 הערות מפתח"):
    st.text_area("הוסף הערות:", key="notes1", height=100)

st.markdown("---")

# ----------------------------------------------------------
# GRAPH 2 - Recalls Over Time by Manufacturer
# ----------------------------------------------------------
st.header("📈 גרף 2: מגמות ריקולים לאורך זמן לפי יצרן")

recalls_clean = recalls[recalls["SHNAT_RECALL"].notna()].copy()
trend = (
    recalls_clean.groupby(["SHNAT_RECALL", "TOZAR_TEUR"])
    .size()
    .reset_index(name="count")
)

# Top 10 manufacturers by total recalls
top_manufacturers = (
    trend.groupby("TOZAR_TEUR")["count"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .index
)

trend_filtered = trend[trend["TOZAR_TEUR"].isin(top_manufacturers)]

fig2 = px.line(
    trend_filtered,
    x="SHNAT_RECALL",
    y="count",
    color="TOZAR_TEUR",
    title="מגמות ריקולים: 10 היצרנים המובילים",
    labels={"SHNAT_RECALL": "שנה", "count": "מספר ריקולים", "TOZAR_TEUR": "יצרן"},
    markers=True
)
fig2.update_layout(height=500, legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02))
st.plotly_chart(fig2, use_container_width=True)

st.info(f"📊 **תובנה עיקרית:** סך הכל {len(recalls_clean)} ריקולים נרשמו במערכת")

with st.expander("📝 הערות מפתח"):
    st.text_area("הוסף הערות:", key="notes2", height=100)

st.markdown("---")

# ----------------------------------------------------------
# GRAPH 3 - Importer Performance (Attendance Rate)
# ----------------------------------------------------------
st.header("🏭 גרף 3: ביצועי יבואנים - אחוזי טיפול בריקולים")

# Total affected per recall
total_per_recall = (
    joined.groupby("RECALL_ID")
    .agg(total=("MISPAR_RECHEV_PRIV", "count"))
)

# Unattended per recall
unattended_per_recall = (
    unattended.groupby("RECALL_ID")
    .size()
    .to_frame("unattended")
)

# Calculate attendance rate
performance = total_per_recall.join(unattended_per_recall, how="left").fillna(0)
performance["attendance_rate"] = ((performance["total"] - performance["unattended"]) / performance["total"] * 100)

# Join with importer info
performance = performance.merge(
    recalls[["RECALL_ID", "YEVUAN_TEUR"]].drop_duplicates(),
    on="RECALL_ID",
    how="left"
)

# Average by importer
importer_perf = (
    performance.groupby("YEVUAN_TEUR")
    .agg(
        avg_attendance=("attendance_rate", "mean"),
        total_recalls=("RECALL_ID", "count")
    )
    .reset_index()
    .sort_values("avg_attendance", ascending=False)
    .head(15)
)

fig3 = px.bar(
    importer_perf,
    x="YEVUAN_TEUR",
    y="avg_attendance",
    color="avg_attendance",
    title="ביצועי יבואנים: אחוז ממוצע של טיפול בריקולים (15 המובילים)",
    labels={"YEVUAN_TEUR": "יבואן", "avg_attendance": "אחוז טיפול ממוצע"},
    color_continuous_scale="Greens",
    hover_data=["total_recalls"]
)
fig3.update_layout(height=500, xaxis_tickangle=-45)
st.plotly_chart(fig3, use_container_width=True)

st.info(f"🎯 **תובנה עיקרית:** אחוז הטיפול הממוצע בכל היבואנים: {performance['attendance_rate'].mean():.1f}%")

with st.expander("📝 הערות מפתח"):
    st.text_area("הוסף הערות:", key="notes3", height=100)

st.markdown("---")

# ----------------------------------------------------------
# GRAPH 4 - Recall Severity Distribution
# ----------------------------------------------------------
st.header("⚠️ גרף 4: התפלגות חומרת הריקולים")

severity_dist = recalls["SUG_TAKALA"].value_counts().reset_index()
severity_dist.columns = ["SUG_TAKALA", "count"]

fig4 = px.pie(
    severity_dist.head(10),
    values="count",
    names="SUG_TAKALA",
    title="התפלגות סוגי תקלות (10 הנפוצות ביותר)",
    hole=0.3
)
fig4.update_traces(textposition='inside', textinfo='percent+label')
fig4.update_layout(height=500)
st.plotly_chart(fig4, use_container_width=True)

st.info(f"⚠️ **תובנה עיקרית:** סוג התקלה הנפוץ ביותר: {severity_dist.iloc[0]['SUG_TAKALA']} ({severity_dist.iloc[0]['count']} מקרים)")

with st.expander("📝 הערות מפתח"):
    st.text_area("הוסף הערות:", key="notes4", height=100)

st.markdown("---")

# ----------------------------------------------------------
# GRAPH 5 - BONUS: Model Analysis
# ----------------------------------------------------------
st.header("🚙 גרף 5: דגמי רכב עם מספר הריקולים הגבוה ביותר")

model_recalls = (
    recalls.groupby(["DEGEM", "TOZAR_TEUR"])
    .size()
    .reset_index(name="recall_count")
    .sort_values("recall_count", ascending=False)
    .head(20)
)

model_recalls["model_full"] = model_recalls["TOZAR_TEUR"] + " - " + model_recalls["DEGEM"]

fig5 = px.bar(
    model_recalls,
    y="model_full",
    x="recall_count",
    orientation="h",
    title="20 הדגמים עם מספר הריקולים הגבוה ביותר",
    labels={"model_full": "יצרן ודגם", "recall_count": "מספר ריקולים"},
    color="recall_count",
    color_continuous_scale="Oranges"
)
fig5.update_layout(height=600, showlegend=False)
st.plotly_chart(fig5, use_container_width=True)

st.info(f"🔧 **תובנה עיקרית:** הדגם עם מספר הריקולים הגבוה ביותר: {model_recalls.iloc[0]['model_full']} ({model_recalls.iloc[0]['recall_count']} ריקולים)")

with st.expander("📝 הערות מפתח"):
    st.text_area("הוסף הערות:", key="notes5", height=100)

st.markdown("---")
st.caption("📊 מקור נתונים: data.gov.il | פרויקט אישי - ניתוח נתונים ומדעי הנתונים | 2024")