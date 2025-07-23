import streamlit as st
import pandas as pd
from db_handler import DatabaseManager

st.set_page_config(page_title="Sales & Sales Items Browser", page_icon="🧾")
st.title("🧾 Sales & Sales Items Data Browser")

db = DatabaseManager()

# Utility: list all table names in the current DB (for Postgres, not sqlite)
@st.cache_data(ttl=600)
def get_db_tables():
    sql = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """
    df = db.fetch_data(sql)
    return df['table_name'].tolist() if not df.empty else []

tables = get_db_tables()
st.write("**Available tables in the database:**", tables)

def first_existing_table(possibles):
    for name in possibles:
        if name in tables:
            return name
    return None

sales_table = first_existing_table(["sales", "Sales"])
salesitems_table = first_existing_table(["salesitems", "salesitem", "SalesItems", "SalesItem"])

if not sales_table or not salesitems_table:
    st.error(f"Could not find required tables. Found: {tables}")
    st.stop()

# Load tables
@st.cache_data(ttl=300)
def load_table(tablename, ordercol=None):
    q = f"SELECT * FROM {tablename}"
    if ordercol:
        q += f" ORDER BY {ordercol} DESC"
    return db.fetch_data(q)

df_sales = load_table(sales_table, ordercol="saleid")
df_salesitems = load_table(salesitems_table, ordercol="salesitemid")

tab1, tab2 = st.tabs(["Sales", "Sales Items"])

with tab1:
    st.subheader(f"Table: {sales_table}")
    if df_sales.empty:
        st.info("No sales records found.")
    else:
        st.dataframe(df_sales, use_container_width=True)

with tab2:
    st.subheader(f"Table: {salesitems_table}")
    if df_salesitems.empty:
        st.info("No sales items found.")
    else:
        st.dataframe(df_salesitems, use_container_width=True)

# Optional: Drill-down - show salesitems for a selected sale
if not df_sales.empty and not df_salesitems.empty:
    with st.expander("Show sale details (click to expand)", expanded=False):
        saleids = df_sales['saleid'].unique()
        selected = st.selectbox("Select a Sale ID to view items", saleids)
        subitems = df_salesitems[df_salesitems['saleid'] == selected]
        st.write(f"Items in Sale ID {selected}:")
        st.dataframe(subitems, use_container_width=True)
