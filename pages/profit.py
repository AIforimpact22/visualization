import streamlit as st
import pandas as pd
import json
from db_handler import DatabaseManager
import streamlit.components.v1 as components

try:
    from streamlit_extras.st_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

st.set_page_config(page_title="Category Profit Leaderboard", page_icon="💰")
st.title("💰 Top N Categories by Net Profit")

REFRESH  = st.sidebar.slider("Refresh interval (s)", 2, 30, 5)
NUM_SALE = st.sidebar.slider("Analyse last # sales", 5, 200, 50)
TOP_N    = st.sidebar.slider("Top N groups", 5, 30, 10)

GROUP_COLS = [
    ("familycat",     "Family"),
    ("sectioncat",    "Section"),
    ("departmentcat", "Department"),
    ("classcat",      "Class"),
]

tab1, tab2 = st.tabs(["Net Profit Leaderboard", "Gross Sales Leaderboard"])

db = DatabaseManager()

@st.cache_data(ttl=2)
def fetch_blocks(n_sales: int):
    sales = db.fetch_data(
        "SELECT saleid, saletime FROM sales ORDER BY saleid DESC LIMIT %s",
        (n_sales,),
    )
    if sales.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    saleids = tuple(int(x) for x in sales.saleid.tolist())
    placeholders = ",".join(["%s"] * len(saleids))
    salesitems = db.fetch_data(
        f"SELECT saleid,itemid,quantity,totalprice,unitprice "
        f"FROM salesitems WHERE saleid IN ({placeholders})",
        saleids,
    )
    if salesitems.empty:
        return sales, salesitems, pd.DataFrame(), pd.DataFrame()
    itemids = tuple(int(x) for x in salesitems.itemid.unique())
    item_place = ",".join(["%s"] * len(itemids))
    items = db.fetch_data(
        f"""SELECT itemid,itemnameenglish,familycat,sectioncat,
                   departmentcat,classcat,sellingprice
            FROM item WHERE itemid IN ({item_place})""",
        itemids,
    )
    inventory = db.fetch_data(
        f"""SELECT itemid, cost_per_unit
            FROM inventory
            WHERE itemid IN ({item_place})""",
        itemids,
    )
    return sales, salesitems, items, inventory

with tab1:
    group_col, group_label = st.selectbox(
        "Profit leaderboard category:",
        GROUP_COLS, format_func=lambda x: x[1]
    )
    if st_autorefresh:
        st_autorefresh(interval=REFRESH * 1000, key="profit_leader_refresh")

    sales, salesitems, items, inventory = fetch_blocks(NUM_SALE)
    if sales.empty or salesitems.empty or items.empty or inventory.empty:
        st.info("Not enough sales/inventory data.")
    else:
        # Merge all
        df = (
            salesitems
            .merge(items, on="itemid", how="left")
            .merge(inventory.groupby("itemid")["cost_per_unit"].min().reset_index(), on="itemid", how="left")
            .merge(sales[["saleid","saletime"]], on="saleid", how="left")
        )
        df[group_col] = df[group_col].fillna("Unknown").replace("", "Unknown")
        df["profit"] = (df["unitprice"] - df["cost_per_unit"].fillna(0)) * df["quantity"]

        top_groups = (
            df.groupby(group_col, dropna=False)["profit"]
            .sum()
            .sort_values(ascending=False)
            .head(TOP_N)
            .reset_index()
        )

        profit_json = json.dumps([
            {"group": str(r[group_col]), "net_profit": float(r.profit)}
            for _, r in top_groups.iterrows()
        ])

        d3_profit = f"""
<script src="https://d3js.org/d3.v7.min.js"></script>
<div id="profit_chart"></div>
<script>
const data={profit_json};
const width=850,height=420,margin={{top:40,right:40,bottom:60,left:120}};
const y=d3.scaleBand().domain(data.map(d=>d.group))
    .rangeRound([margin.top,height-margin.bottom]).padding(0.12);
const x=d3.scaleLinear()
    .domain([d3.min(data,d=>d.net_profit),d3.max(data,d=>d.net_profit)*1.05]).nice()
    .range([margin.left,width-margin.right]);
const color=d3.scaleOrdinal(d3.schemeSet2);
const svg=d3.select("#profit_chart").append("svg")
    .attr("width",width).attr("height",height)
    .attr("viewBox",[0,0,width,height])
    .attr("style","max-width:100%;height:auto;background:#fff;border-radius:14px;");
svg.append("g").selectAll("rect").data(data).join("rect")
    .attr("x",d=>x(Math.min(0,d.net_profit)))
    .attr("y",d=>y(d.group))
    .attr("width",d=>Math.abs(x(d.net_profit)-x(0)))
    .attr("height",y.bandwidth()).attr("rx",7)
    .attr("fill",(d,i)=>color(i));
svg.append("g")
    .attr("transform",`translate(0,${{margin.top}})`)
    .call(d3.axisTop(x).ticks(width/120,"s"))
    .call(g=>g.select(".domain").remove());
svg.append("g")
    .attr("transform",`translate(${{margin.left}},0)`)
    .call(d3.axisLeft(y).tickSize(0))
    .call(g=>g.select(".domain").remove());
svg.selectAll("text.val").data(data).join("text")
    .attr("x",d=>x(d.net_profit)+(d.net_profit<0?-45:10))
    .attr("y",d=>y(d.group)+y.bandwidth()/2+3)
    .text(d=>d3.format(",.0f")(d.net_profit))
    .attr("fill","#1e293b").attr("font-size","1.1rem");
</script>
"""
        st.write(f"### Top {TOP_N} {group_label}s by **Net Profit** — last {NUM_SALE} sales")
        components.html(d3_profit, height=450)

with tab2:
    group_col, group_label = st.selectbox(
        "Gross sales leaderboard category:",
        GROUP_COLS, format_func=lambda x: x[1], key="gross_lb"
    )
    if st_autorefresh:
        st_autorefresh(interval=REFRESH * 1000, key="gross_leader_refresh")

    sales, salesitems, items, inventory = fetch_blocks(NUM_SALE)
    if sales.empty or salesitems.empty or items.empty:
        st.info("Not enough sales data.")
    else:
        df = (
            salesitems
            .merge(items, on="itemid", how="left")
            .merge(sales[["saleid","saletime"]], on="saleid", how="left")
        )
        df[group_col] = df[group_col].fillna("Unknown").replace("", "Unknown")

        top_groups = (
            df.groupby(group_col, dropna=False)["totalprice"]
            .sum()
            .sort_values(ascending=False)
            .head(TOP_N)
            .reset_index()
        )

        rt_json = json.dumps([
            {"group": str(r[group_col]), "total_sales": float(r.totalprice)}
            for _, r in top_groups.iterrows()
        ])

        d3_rt = f"""
<script src="https://d3js.org/d3.v7.min.js"></script>
<div id="gross_chart"></div>
<script>
const data={rt_json};
const width=850,height=420,margin={{top:40,right:40,bottom:60,left:120}};
const y=d3.scaleBand().domain(data.map(d=>d.group))
    .rangeRound([margin.top,height-margin.bottom]).padding(0.12);
const x=d3.scaleLinear()
    .domain([0,d3.max(data,d=>d.total_sales)*1.05]).nice()
    .range([margin.left,width-margin.right]);
const color=d3.scaleOrdinal(d3.schemeSet2);
const svg=d3.select("#gross_chart").append("svg")
    .attr("width",width).attr("height",height)
    .attr("viewBox",[0,0,width,height])
    .attr("style","max-width:100%;height:auto;background:#fff;border-radius:14px;");
svg.append("g").selectAll("rect").data(data).join("rect")
    .attr("x",x(0)).attr("y",d=>y(d.group))
    .attr("width",d=>x(d.total_sales)-x(0))
    .attr("height",y.bandwidth()).attr("rx",7)
    .attr("fill",(d,i)=>color(i));
svg.append("g")
    .attr("transform",`translate(0,${{margin.top}})`)
    .call(d3.axisTop(x).ticks(width/120,"s"))
    .call(g=>g.select(".domain").remove());
svg.append("g")
    .attr("transform",`translate(${{margin.left}},0)`)
    .call(d3.axisLeft(y).tickSize(0))
    .call(g=>g.select(".domain").remove());
svg.selectAll("text.val").data(data).join("text")
    .attr("x",d=>x(d.total_sales)+10)
    .attr("y",d=>y(d.group)+y.bandwidth()/2+3)
    .text(d=>d3.format(",.0f")(d.total_sales))
    .attr("fill","#1e293b").attr("font-size","1.1rem");
</script>
"""
        st.write(f"### Top {TOP_N} {group_label}s by **Gross Sales** — last {NUM_SALE} sales")
        components.html(d3_rt, height=450)
