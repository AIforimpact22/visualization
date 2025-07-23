import streamlit as st
import pandas as pd
import time
from db_handler import DatabaseManager

st.set_page_config(page_title="Realtime Sales Monitor", page_icon="⏱️")
st.title("⏱️ Realtime Sales Monitor")

REFRESH = st.sidebar.slider("Refresh interval (seconds)", 2, 30, 5)

db = DatabaseManager()

@st.cache_data(ttl=2)
def get_recent_sales(n=10):
    return db.fetch_data(
        f"SELECT * FROM sales ORDER BY saleid DESC LIMIT {n}"
    )

@st.cache_data(ttl=2)
def get_salesitems_for_sale(saleid):
    return db.fetch_data(
        "SELECT * FROM salesitems WHERE saleid = %s ORDER BY salesitemid", (saleid,)
    )

# Realtime loop
placeholder = st.empty()
while True:
    with placeholder.container():
        st.write("Last refreshed at", time.strftime("%H:%M:%S"))
        sales_df = get_recent_sales()
        if sales_df.empty:
            st.info("No sales yet.")
            time.sleep(REFRESH)
            continue
        st.dataframe(sales_df, use_container_width=True)

        saleids = sales_df['saleid'].tolist()
        selected = st.selectbox("Show items for Sale ID:", saleids)
        items_df = get_salesitems_for_sale(selected)
        st.subheader(f"Items for Sale {selected}")
        if items_df.empty:
            st.info("No items for this sale.")
        else:
            st.dataframe(items_df, use_container_width=True)
    time.sleep(REFRESH)
    st.cache_data.clear()  # Force cache refresh
