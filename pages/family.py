# ------------------ Family / Section Realtime ------------------
# Tab 1: Leaderboard   Tab 2: Time‑series curves
# ---------------------------------------------------------------
import streamlit as st
import pandas as pd
import json
from db_handler import DatabaseManager
import streamlit.components.v1 as components

try:
    from streamlit_extras.st_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

st.set_page_config(page_title="Family / Section Realtime", page_icon="🗃️")
st.title("🗃️ Realtime Family / Section / Dept / Class Visuals")

REFRESH  = st.sidebar.slider("Realtime refresh (s)", 2, 30, 5)
NUM_SALE = st.sidebar.slider("Analyse last # sales", 5, 200, 50)
TOP_N    = st.sidebar.slider("Leaderboard: top N groups", 5, 30, 10)

GROUP_COLS = [
    ("familycat",     "Family"),
    ("sectioncat",    "Section"),
    ("departmentcat", "Department"),
    ("classcat",      "Class"),
]

tab_lb, tab_ts = st.tabs(["Realtime Leaderboard", "Realtime Time‑series"])
db = DatabaseManager()

# ------------- shared helper (cached) -------------
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
        f"SELECT saleid,itemid,quantity,totalprice "
        f"FROM salesitems WHERE saleid IN ({placeholders})",
        saleids,
    )
    if salesitems.empty:
        return sales, salesitems, pd.DataFrame()

    itemids = tuple(int(x) for x in salesitems.itemid.unique())
    item_place = ",".join(["%s"] * len(itemids))
    items = db.fetch_data(
        f"""SELECT itemid,familycat,sectioncat,
                   departmentcat,classcat
              FROM item WHERE itemid IN ({item_place})""",
        itemids,
    )
    return sales, salesitems, items

# ────────────────── Leaderboard tab ──────────────────
with tab_lb:
    sel_col, sel_label = st.selectbox(
        "Leaderboard category:", GROUP_COLS, format_func=lambda x: x[1]
    )
    if st_autorefresh:
        st_autorefresh(interval=REFRESH * 1000, key="lb_refresh")

    sales, salesitems, items = fetch_blocks(NUM_SALE)
    if sales.empty or salesitems.empty or items.empty:
        st.info("No recent sales data.")
    else:
        df = (salesitems.merge(items, on="itemid", how="left")
                        .merge(sales[["saleid","saletime"]], on="saleid", how="left"))
        df[sel_col] = df[sel_col].fillna("Unknown").replace("", "Unknown")

        top_groups = (df.groupby(sel_col)["totalprice"].sum()
                        .sort_values(ascending=False).head(TOP_N).reset_index())

        rt_json = json.dumps([{"group": str(r[sel_col]),
                               "total_sales": float(r.totalprice)}
                               for _, r in top_groups.iterrows()])

        d3_rt = f"""
<script src="https://d3js.org/d3.v7.min.js"></script>
<div id="rt_chart"></div>
<script>
const data={rt_json};
const width=850,height=420,margin={{top:40,right:40,bottom:60,left:120}};
const y=d3.scaleBand().domain(data.map(d=>d.group))
    .rangeRound([margin.top,height-margin.bottom]).padding(0.12);
const x=d3.scaleLinear()
    .domain([0,d3.max(data,d=>d.total_sales)*1.05]).nice()
    .range([margin.left,width-margin.right]);
const color=d3.scaleOrdinal(d3.schemeSet2);
const svg=d3.select("#rt_chart").append("svg")
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
    .attr("x",d=>x(d.total_sales)+8)
    .attr("y",d=>y(d.group)+y.bandwidth()/2+3)
    .text(d=>d3.format(",.0f")(d.total_sales))
    .attr("fill","#1e293b").attr("font-size","1.1rem");
</script>
"""
        st.write(f"### Top {TOP_N} {sel_label}s — last {NUM_SALE} sales")
        components.html(d3_rt, height=450)

# ────────────────── Time‑series tab ──────────────────
with tab_ts:
    ts_col, ts_label = st.selectbox(
        "Time‑series category:", GROUP_COLS,
        format_func=lambda x: x[1], key="ts_sel"
    )
    if st_autorefresh:
        st_autorefresh(interval=REFRESH * 1000, key="ts_refresh")

    sales, salesitems, items = fetch_blocks(NUM_SALE)
    if sales.empty or salesitems.empty or items.empty:
        st.info("No recent sales data.")
    else:
        df = (salesitems.merge(items,on="itemid",how="left")
                        .merge(sales[["saleid","saletime"]],on="saleid",how="left"))
        df[ts_col] = df[ts_col].fillna("Unknown").replace("", "Unknown")
        df["saletime"] = pd.to_datetime(df["saletime"])
        df["t_min"]    = df["saletime"].dt.floor("T")

        ts_agg = (df.groupby([ts_col,"t_min"])["totalprice"]
                    .sum().reset_index())

        ts_data = [{"group": str(r[ts_col]),
                    "date":  r["t_min"].strftime("%Y-%m-%dT%H:%M:%S"),
                    "value": float(r["totalprice"])}
                   for _, r in ts_agg.iterrows()]
        ts_json = json.dumps(ts_data)

        d3_ts = f"""
<script src="https://d3js.org/d3.v7.min.js"></script>
<div id="ts_chart"></div>
<script>
const data={ts_json};
data.forEach(d=>d.date=new Date(d.date));
const dataByCat=Array.from(d3.group(data,d=>d.group),
                           ([key,values])=>({{key:key,values:values}}));

const width=900,height=500,margin={{top:40,right:40,bottom:40,left:80}};
const x=d3.scaleUtc(d3.extent(data,d=>d.date),
                    [margin.left,width-margin.right]);
const y=d3.scaleLinear([0,d3.max(data,d=>d.value)*1.1],
                       [height-margin.bottom,margin.top]);
const color=d3.scaleOrdinal(d3.schemeTableau10);
const line=d3.line().x(d=>x(d.date)).y(d=>y(d.value));

const svg=d3.select("#ts_chart").append("svg")
    .attr("width",width).attr("height",height)
    .attr("viewBox",[0,0,width,height])
    .attr("style","max-width:100%;height:auto;background:#fff;border-radius:14px;");

// axes
svg.append("g")
    .attr("transform",`translate(0,${{height-margin.bottom}})`)
    .call(d3.axisBottom(x).ticks(width/80).tickSizeOuter(0));

svg.append("g")
    .attr("transform",`translate(${{margin.left}},0)`)
    .call(d3.axisLeft(y).ticks(height/50))
    .call(g=>g.select(".domain").remove())
    .call(g=>g.selectAll(".tick line").clone()
        .attr("x2",width-margin.left-margin.right)
        .attr("stroke-opacity",0.1))
    .call(g=>g.append("text")
        .attr("x",-margin.left+5).attr("y",10)
        .attr("fill","currentColor")
        .attr("text-anchor","start").text("Sales"));

// lines + labels
const g=svg.append("g").attr("fill","none").attr("stroke-width",2);

dataByCat.forEach((series,i)=>{{
    g.append("path").datum(series.values)
      .attr("d",line).attr("stroke",color(i));
    const last=series.values.at(-1);
    if(last){{
        g.append("text").text(series.key).attr("font-size","0.9rem")
          .attr("x",x(last.date)+5).attr("y",y(last.value))
          .attr("dy","0.32em").attr("fill",color(i))
          .attr("paint-order","stroke")
          .attr("stroke","#fff").attr("stroke-width",4);
    }}
}});
</script>
"""
        st.write(f"### Realtime time‑series ({ts_label}s) — last {NUM_SALE} sales")
        components.html(d3_ts, height=540)
