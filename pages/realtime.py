import streamlit as st
import pandas as pd
import time
from db_handler import DatabaseManager

st.set_page_config(page_title="Realtime Sales Graph", page_icon="📊")
st.title("📊 Realtime Sales Graph")

REFRESH = st.sidebar.slider("Refresh interval (seconds)", 2, 30, 5)
NUM_SALES = st.sidebar.slider("Number of Recent Sales to Show", 5, 50, 10)

db = DatabaseManager()

@st.cache_data(ttl=2)
def get_recent_sales(n=10):
    return db.fetch_data(
        f"SELECT saleid, datetime, totalamount FROM sales ORDER BY saleid DESC LIMIT {n}"
    )

@st.cache_data(ttl=2)
def get_salesitems_for_sale(saleid):
    return db.fetch_data(
        "SELECT itemid, quantity, price, total FROM salesitems WHERE saleid = %s ORDER BY salesitemid", (saleid,)
    )

placeholder = st.empty()
while True:
    with placeholder.container():
        st.write("Last refreshed at", time.strftime("%H:%M:%S"))

        sales_df = get_recent_sales(NUM_SALES)
        if sales_df.empty:
            st.info("No sales yet.")
            time.sleep(REFRESH)
            continue

        # Sort for better chart axis (oldest to newest)
        sales_df = sales_df.sort_values("saleid")
        sales_df['datetime'] = pd.to_datetime(sales_df['datetime'])

        # Plot sales totals
        st.subheader("Recent Sales (Total Amount)")
        st.bar_chart(
            data=sales_df,
            x="datetime",
            y="totalamount",
            use_container_width=True
        )

        # Select and plot items for a sale
        saleids = sales_df['saleid'].tolist()[::-1]  # show newest first in dropdown
        selected = st.selectbox("Show items for Sale ID:", saleids)
        items_df = get_salesitems_for_sale(selected)
        st.subheader(f"Item Quantities for Sale {selected}")

        if items_df.empty:
            st.info("No items for this sale.")
        else:
            # Group by itemid (sum quantities if necessary)
            chart_df = items_df.groupby("itemid", as_index=False)["quantity"].sum()
            st.bar_chart(
                data=chart_df,
                x="itemid",
                y="quantity",
                use_container_width=True
            )
    time.sleep(REFRESH)
    st.cache_data.clear()
