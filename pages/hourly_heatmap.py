import streamlit as st
import pandas as pd
from db_handler import DatabaseManager
import plotly.express as px

st.set_page_config(page_title="Sales Calendar Heatmap", page_icon="📆")
st.title("📆 Sales by Day and Hour (Calendar Style)")

REFRESH  = st.sidebar.slider("Refresh interval (seconds)", 2, 30, 10)
NUM_SALE = st.sidebar.slider("Analyze last # sales", 20, 500, 100)

try:
    from streamlit_extras.st_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

if st_autorefresh:
    st_autorefresh(interval=REFRESH * 1000, key="calendar_heat_refresh")

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

sales["saletime"] = pd.to_datetime(sales["saletime"])
sales["Day"] = sales["saletime"].dt.strftime("%Y-%m-%d")
sales["Hour"] = sales["saletime"].dt.hour

pivot = sales.pivot_table(
    index="Day",
    columns="Hour",
    values="totalamount",
    aggfunc="sum",
    fill_value=0
).sort_index()

fig = px.imshow(
    pivot,
    labels=dict(x="Hour of Day", y="Date", color="Total Sales"),
    x=pivot.columns,
    y=pivot.index,
    aspect="auto",
    color_continuous_scale="Viridis",
)

fig.update_layout(
    title=f"Sales Calendar Heatmap (last {NUM_SALE} sales)",
    height=600,
    margin=dict(l=50, r=20, t=70, b=40),
)
fig.update_xaxes(type='category')
fig.update_yaxes(type='category')

st.plotly_chart(fig, use_container_width=True)
st.caption("Each cell shows the total sales for that day/hour (last N sales).")
