import streamlit as st
import pandas as pd
from db_handler import DatabaseManager
import plotly.express as px

st.set_page_config(page_title="Hourly Sales Heatmap", page_icon="🕒")
st.title("🕒 Hourly Sales Heatmap")

REFRESH  = st.sidebar.slider("Refresh interval (seconds)", 2, 30, 10)
NUM_SALE = st.sidebar.slider("Analyze last # sales", 20, 500, 100)

try:
    from streamlit_extras.st_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

if st_autorefresh:
    st_autorefresh(interval=REFRESH * 1000, key="hm_refresh")

db = DatabaseManager()

@st.cache_data(ttl=2)
def fetch_sales(num_sales):
    sales = db.fetch_data(
        "SELECT saleid, saletime, totalamount FROM sales ORDER BY saleid DESC LIMIT %s",
        (num_sales,)
    )
    return sales

sales = fetch_sales(NUM_SALE)
if sales.empty:
    st.info("No sales found.")
    st.stop()

# Parse time and add weekday/hour columns
sales["saletime"] = pd.to_datetime(sales["saletime"])
sales["Hour"] = sales["saletime"].dt.hour
sales["Weekday"] = sales["saletime"].dt.dayofweek  # Monday=0, Sunday=6

# For user-friendly display:
WEEKDAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
sales["WeekdayName"] = sales["Weekday"].map(lambda i: WEEKDAY_NAMES[i])

# Pivot table: rows=WeekdayName, cols=Hour, values=sum(totalamount)
heatmap_df = sales.pivot_table(
    index="WeekdayName",
    columns="Hour",
    values="totalamount",
    aggfunc="sum",
    fill_value=0
).reindex(WEEKDAY_NAMES)

# Plotly heatmap
fig = px.imshow(
    heatmap_df,
    labels=dict(x="Hour of Day", y="Day of Week", color="Total Sales"),
    x=heatmap_df.columns,
    y=heatmap_df.index,
    aspect="auto",
    color_continuous_scale="YlGnBu",
)

fig.update_layout(
    title=f"Hourly Sales Heatmap (last {NUM_SALE} sales)",
    height=450,
    margin=dict(l=50, r=20, t=70, b=40),
)
fig.update_xaxes(type='category')
fig.update_yaxes(type='category')

st.plotly_chart(fig, use_container_width=True)

st.caption("Each cell shows the **total sales amount** for that day/hour block (last N sales).")
