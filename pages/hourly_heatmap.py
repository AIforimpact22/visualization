import streamlit as st
import pandas as pd
import numpy as np
from db_handler import DatabaseManager
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(page_title="Sales Calendar Heatmap", page_icon="📆")
st.title("📆 Sales Calendar Heatmap (Year/Month/Hour)")

NUM_DAYS = st.sidebar.slider("Days to show", 7, 90, 30)
db = DatabaseManager()

@st.cache_data(ttl=60)
def fetch_sales_days(num_days):
    sales = db.fetch_data(
        "SELECT saleid, saletime, totalamount FROM sales WHERE saletime >= NOW() - INTERVAL '%s days' ORDER BY saletime ASC",
        (num_days,)
    )
    return sales

sales = fetch_sales_days(NUM_DAYS)
if sales.empty:
    st.info("No sales found.")
    st.stop()

sales["saletime"] = pd.to_datetime(sales["saletime"])
sales["Day"] = sales["saletime"].dt.date
sales["Month"] = sales["saletime"].dt.strftime("%b")
sales["Hour"] = sales["saletime"].dt.hour

all_days = pd.date_range(sales["saletime"].min().date(), sales["saletime"].max().date(), freq="D")
all_hours = np.arange(24)
grid = pd.MultiIndex.from_product([all_days, all_hours], names=["Day", "Hour"])
sales_pivot = (
    sales.groupby(["Day", "Hour"])["totalamount"].sum()
    .reindex(grid, fill_value=0)
    .unstack()
)
sales_pivot = sales_pivot.astype(float).fillna(0.0)
sales_pivot.index = [f"{d.strftime('%b')}-{d.day:02d}" for d in sales_pivot.index]

# Bigger/clearer bar height: min 0.5 inch per day, up to 1 inch per row
per_day_height = 0.65  # try 0.65-1 for chunkier rows
fig_height = max(12, per_day_height * len(sales_pivot))
fig, ax = plt.subplots(figsize=(4, fig_height))

sns.heatmap(
    sales_pivot,
    ax=ax,
    cmap="RdBu_r",
    linewidths=0.3,
    linecolor="#ddd",
    cbar_kws={"label": "Total Sales"},
    xticklabels=[f"{h}:00" for h in sales_pivot.columns],
    yticklabels=sales_pivot.index if len(sales_pivot) < 60 else 10
)
plt.xlabel("Hour of Day")
plt.ylabel("Date (Month-Day)")
plt.title(f"Sales by Day and Hour (last {NUM_DAYS} days)")
plt.tight_layout()

st.pyplot(fig)
st.caption(
    f"Each cell shows the total sales for that day and hour. Blue = low, Red = high. "
    f"(Row height automatically adjusts for the number of days.)"
)

with st.expander("Show sales data as table"):
    st.dataframe(sales_pivot)
