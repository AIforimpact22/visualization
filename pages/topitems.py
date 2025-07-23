import streamlit as st
import pandas as pd
import json
from db_handler import DatabaseManager
import streamlit.components.v1 as components

try:
    from streamlit_extras.st_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

st.set_page_config(page_title="Top 10 Fastest Moving Items", page_icon="🏆")
st.title("🏆 Top 10 Fastest Moving Items")

REFRESH  = st.sidebar.slider("Refresh interval (seconds)", 2, 30, 5)
NUM_SALE = st.sidebar.slider("Number of Recent Sales", 10, 300, 50, step=10)

if st_autorefresh:
    st_autorefresh(interval=REFRESH * 1000, key="topitems_refresh")

db = DatabaseManager()

@st.cache_data(ttl=2)
def fetch_blocks(n_sales: int):
    sales = db.fetch_data(
        "SELECT saleid, saletime FROM sales ORDER BY saleid DESC LIMIT %s",
        (n_sales,),
    )
    if sales.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    saleids = tuple(int(x) for x in sales.saleid.tolist())
    placeholders = ",".join(["%s"] * len(saleids))
    salesitems = db.fetch_data(
        f"SELECT saleid,itemid,quantity,totalprice FROM salesitems WHERE saleid IN ({placeholders})",
        saleids,
    )
    if salesitems.empty:
        return sales, salesitems, pd.DataFrame()

    itemids = tuple(int(x) for x in salesitems.itemid.unique())
    item_place = ",".join(["%s"] * len(itemids))
    items = db.fetch_data(
        f"SELECT itemid,itemnameenglish FROM item WHERE itemid IN ({item_place})",
        itemids,
    )
    return sales, salesitems, items

sales, salesitems, items = fetch_blocks(NUM_SALE)
if sales.empty or salesitems.empty or items.empty:
    st.info("No sales found.")
    st.stop()

df = (
    salesitems.merge(items, on="itemid", how="left")
)

agg = (
    df.groupby(["itemid", "itemnameenglish"], dropna=False)
      .agg(quantity_sold=('quantity', 'sum'),
           total_revenue=('totalprice', 'sum'),
           avg_price=('totalprice', 'mean'))
      .sort_values("quantity_sold", ascending=False)
      .head(10)
      .reset_index()
)

# ------------- D3 Horizontal Bar Chart -------------
chart_data = [
    {
        "item": row["itemnameenglish"] if pd.notna(row["itemnameenglish"]) else "Unknown",
        "quantity": int(row["quantity_sold"])
    }
    for _, row in agg.iterrows()
]
chart_json = json.dumps(chart_data)
chart_height = max(280, 80 + len(chart_data) * 35)

d3_code = f"""
<script src="https://d3js.org/d3.v7.min.js"></script>
<div id="topitems_chart"></div>
<script>
const data={chart_json};
const width=700,height={chart_height},margin={{top:40,right:20,bottom:30,left:220}};
const y=d3.scaleBand().domain(data.map(d=>d.item))
    .rangeRound([margin.top,height-margin.bottom]).padding(0.16);
const x=d3.scaleLinear()
    .domain([0,d3.max(data,d=>d.quantity)*1.05]).nice()
    .range([margin.left,width-margin.right]);
const color=d3.scaleOrdinal(d3.schemeCategory10);

const svg=d3.select("#topitems_chart").append("svg")
    .attr("width",width).attr("height",height)
    .attr("viewBox",[0,0,width,height])
    .attr("style","max-width:100%;height:auto;background:#f8fafc;border-radius:12px;");

svg.append("g").selectAll("rect").data(data).join("rect")
    .attr("x",x(0)).attr("y",d=>y(d.item))
    .attr("width",d=>x(d.quantity)-x(0)).attr("height",y.bandwidth())
    .attr("rx",8).attr("fill",(d,i)=>color(i));

svg.append("g")
    .attr("transform",`translate(0,${{margin.top}})`)
    .call(d3.axisTop(x).ticks(width/120,"s"))
    .call(g=>g.select(".domain").remove());

svg.append("g")
    .attr("transform",`translate(${{margin.left}},0)`)
    .call(d3.axisLeft(y).tickSize(0))
    .call(g=>g.select(".domain").remove());

svg.selectAll("text.val").data(data).join("text")
    .attr("x",d=>x(d.quantity)+8)
    .attr("y",d=>y(d.item)+y.bandwidth()/2+3)
    .text(d=>d3.format(",")(d.quantity))
    .attr("fill","#0f172a")
    .attr("font-size","1.12rem");
</script>
"""
st.write(f"### Top 10 Items by Quantity Sold (Last {NUM_SALE} Sales)")
components.html(d3_code, height=chart_height + 50)

# ------------- Summary Table -------------
with st.expander("Show details as table"):
    agg_disp = agg.rename(columns={
        "itemnameenglish": "Item Name",
        "quantity_sold": "Quantity Sold",
        "total_revenue": "Total Revenue",
        "avg_price": "Average Sale Price"
    })
    agg_disp["Total Revenue"] = agg_disp["Total Revenue"].map('{:,.2f}'.format)
    agg_disp["Average Sale Price"] = agg_disp["Average Sale Price"].map('{:,.2f}'.format)
    st.dataframe(agg_disp, use_container_width=True)
