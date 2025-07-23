import streamlit as st
import pandas as pd
import time
import json
from db_handler import DatabaseManager
import streamlit.components.v1 as components

try:
    from streamlit_extras.st_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

st.set_page_config(page_title="Family/Section Sales Visualization", page_icon="🗃️")
st.title("🗃️ Family/Section/Department/Class Sales Visualization")

REFRESH = st.sidebar.slider("Refresh interval (seconds)", 2, 30, 5)
NUM_SALES = st.sidebar.slider("Number of Recent Sales to Analyze", 5, 100, 30)
TOP_N = st.sidebar.slider("Show Top N Groups", 5, 30, 10)

GROUP_COLS = [
    ("familycat", "Family"),
    ("sectioncat", "Section"),
    ("departmentcat", "Department"),
    ("classcat", "Class")
]

GROUP_KEY, GROUP_LABEL = st.sidebar.selectbox(
    "Group sales by:",
    GROUP_COLS,
    format_func=lambda x: x[1]
)

if st_autorefresh:
    st_autorefresh(interval=REFRESH * 1000, key="family_refresh")

db = DatabaseManager()

@st.cache_data(ttl=2)
def get_sales_and_items(num_sales):
    # 1. Get recent sales (saleid, saletime)
    sales = db.fetch_data(
        f"SELECT saleid, saletime FROM sales ORDER BY saleid DESC LIMIT {num_sales}"
    )
    if sales.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    # 2. Get salesitems for those saleids
    saleids = tuple(sales['saleid'].tolist())
    if len(saleids) == 1:
        saleids_query = f"= {saleids[0]}"
    else:
        saleids_query = f"IN {saleids}"
    salesitems = db.fetch_data(
        f"SELECT salesitemid, saleid, itemid, quantity, totalprice FROM salesitems WHERE saleid {saleids_query}"
    )
    # 3. Get items (for all itemids in those sales)
    itemids = tuple(salesitems['itemid'].unique().tolist()) if not salesitems.empty else ()
    if itemids:
        if len(itemids) == 1:
            itemids_query = f"= {itemids[0]}"
        else:
            itemids_query = f"IN {itemids}"
        items = db.fetch_data(
            f"SELECT itemid, itemnameenglish, familycat, sectioncat, departmentcat, classcat FROM item WHERE itemid {itemids_query}"
        )
    else:
        items = pd.DataFrame()
    return sales, salesitems, items

sales, salesitems, items = get_sales_and_items(NUM_SALES)
if sales.empty or salesitems.empty or items.empty:
    st.info("No recent sales data found.")
    st.stop()

# Merge: salesitems + items (+ sales for time, if needed)
merged = salesitems.merge(items, on="itemid", how="left")
merged = merged.merge(sales[["saleid", "saletime"]], on="saleid", how="left")
merged['saletime'] = pd.to_datetime(merged['saletime'])

# Group and aggregate
group_summary = (
    merged
    .groupby(GROUP_KEY)
    .agg(
        total_sales=('totalprice', 'sum'),
        num_transactions=('salesitemid', 'count'),
        num_items=('quantity', 'sum')
    )
    .sort_values("total_sales", ascending=False)
    .reset_index()
)

top_groups = group_summary.head(TOP_N)

# D3 Bar Chart of total_sales by group
chart_data = [
    {
        "group": str(row[GROUP_KEY]) if pd.notna(row[GROUP_KEY]) else "Unknown",
        "total_sales": float(row['total_sales'])
    }
    for _, row in top_groups.iterrows()
]
chart_json = json.dumps(chart_data)

d3_code = """
<script src="https://d3js.org/d3.v7.min.js"></script>
<div id="bar_chart"></div>
<script>
const data = """ + chart_json + """;

const width = 850;
const height = 420;
const margin = {top: 40, right: 40, bottom: 60, left: 120};

const svg = d3.select("#bar_chart")
  .append("svg")
  .attr("width", width)
  .attr("height", height)
  .attr("viewBox", [0, 0, width, height])
  .attr("style", "max-width: 100%; height: auto; background: #fff; border-radius: 14px;");

const y = d3.scaleBand()
    .domain(data.map(d => d.group))
    .rangeRound([margin.top, height - margin.bottom])
    .padding(0.12);

const x = d3.scaleLinear()
    .domain([0, d3.max(data, d => d.total_sales) * 1.05]).nice()
    .range([margin.left, width - margin.right]);

const color = d3.scaleOrdinal(d3.schemeSet2);

svg.append("g")
    .attr("fill", d => color(d.group))
  .selectAll("rect")
  .data(data)
  .join("rect")
    .attr("x", x(0))
    .attr("y", d => y(d.group))
    .attr("width", d => x(d.total_sales) - x(0))
    .attr("height", y.bandwidth())
    .attr("rx", 7)
    .attr("fill", (d, i) => color(i));

svg.append("g")
    .attr("transform", `translate(0,${margin.top})`)
    .call(d3.axisTop(x).ticks(width/120, "s"))
    .call(g => g.select(".domain").remove());

svg.append("g")
    .attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y).tickSize(0))
    .call(g => g.select(".domain").remove());

svg.selectAll("text.value")
  .data(data)
  .join("text")
    .attr("class", "value")
    .attr("x", d => x(d.total_sales) + 8)
    .attr("y", d => y(d.group) + y.bandwidth()/2 + 3)
    .text(d => d3.format(",.0f")(d.total_sales))
    .attr("fill", "#1e293b")
    .attr("font-size", "1.1rem");
</script>
"""

st.write(f"### Top {TOP_N} {GROUP_LABEL}s by Sales (Realtime)")
components.html(d3_code, height=450)

# Optionally: cards per group (uncomment to enable)
# cols = st.columns(3)
# for i, row in top_groups.iterrows():
#     with cols[i % 3]:
#         st.markdown(f"""
# <div style="background:linear-gradient(90deg,#e0e7ff 0%,#f1f5f9 100%);border-radius:12px;padding:18px 20px;margin-bottom:16px;">
#   <h4 style="margin:0 0 8px 0;color:#0f172a;font-weight:800;font-size:1.1rem;">{row[GROUP_KEY]}</h4>
#   <div style="font-size:1.2rem;color:#1e40af;font-weight:700;">{row['total_sales']:,.2f}</div>
#   <div style="color:#4b5563;">Total Sales</div>
#   <div style="margin-top:10px;">
#     <span style="color:#10b981;font-weight:500;">{row['num_items']}</span> items<br/>
#     <span style="color:#6366f1;">{row['num_transactions']}</span> transactions
#   </div>
# </div>
# """, unsafe_allow_html=True)
