import streamlit as st
import pandas as pd
import json
from db_handler import DatabaseManager
import streamlit.components.v1 as components

try:
    from streamlit_extras.st_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

st.set_page_config(page_title="Family/Section Sales Visualization", page_icon="🗃️")
st.title("🗃️ Family/Section/Department/Class Visualization")

REFRESH = st.sidebar.slider("Realtime tab: refresh interval (seconds)", 2, 30, 5)
NUM_SALES = st.sidebar.slider("Realtime tab: # recent sales", 5, 100, 30)
TOP_N = st.sidebar.slider("Realtime tab: show top N", 5, 30, 10)

GROUP_COLS = [
    ("familycat", "Family"),
    ("sectioncat", "Section"),
    ("departmentcat", "Department"),
    ("classcat", "Class")
]

tab1, tab2 = st.tabs(["Catalog Structure", "Realtime Sales by Category"])

db = DatabaseManager()

@st.cache_data(ttl=600)
def get_items_summary():
    items = db.fetch_data(
        "SELECT familycat, sectioncat, departmentcat, classcat FROM item"
    )
    return items

with tab1:
    st.subheader("Catalog Distribution in Item Table")
    items = get_items_summary()
    for col, label in GROUP_COLS:
        st.markdown(f"#### {label}s")
        count_df = items[col].fillna("Unknown").replace("", "Unknown").value_counts().reset_index()
        count_df.columns = [label, "Count"]
        count_df = count_df.sort_values("Count", ascending=False)
        # D3 horizontal bar chart for each group
        chart_data = [
            {"group": str(row[label]), "count": int(row["Count"])}
            for _, row in count_df.iterrows()
        ][:30]
        chart_json = json.dumps(chart_data)
        # Calculate chart height based on number of groups
        chart_height = max(100 + len(chart_data) * 18, 180)
        d3_code = f"""
        <script src="https://d3js.org/d3.v7.min.js"></script>
        <div id="bar_{col}"></div>
        <script>
        const data = {chart_json};
        const width = 650;
        const height = {chart_height};
        const margin = {{top: 40, right: 20, bottom: 30, left: 120}};

        const svg = d3.select("#bar_{col}")
          .append("svg")
          .attr("width", width)
          .attr("height", height)
          .attr("viewBox", [0, 0, width, height])
          .attr("style", "max-width: 100%; height: auto; background: #f8fafc; border-radius: 12px;");

        const y = d3.scaleBand()
            .domain(data.map(d => d.group))
            .rangeRound([margin.top, height - margin.bottom])
            .padding(0.14);

        const x = d3.scaleLinear()
            .domain([0, d3.max(data, d => d.count) * 1.05]).nice()
            .range([margin.left, width - margin.right]);

        const color = d3.scaleOrdinal(d3.schemeSet2);

        svg.append("g")
            .attr("fill", d => color(d.group))
          .selectAll("rect")
          .data(data)
          .join("rect")
            .attr("x", x(0))
            .attr("y", d => y(d.group))
            .attr("width", d => x(d.count) - x(0))
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
            .attr("x", d => x(d.count) + 8)
            .attr("y", d => y(d.group) + y.bandwidth()/2 + 3)
            .text(d => d3.format(",")(d.count))
            .attr("fill", "#1e293b")
            .attr("font-size", "1.05rem");
        </script>
        """
        components.html(d3_code, height=chart_height + 30)

with tab2:
    GROUP_KEY, GROUP_LABEL = st.selectbox(
        "Group sales by:",
        GROUP_COLS,
        index=0,
        format_func=lambda x: x[1]
    )

    if st_autorefresh:
        st_autorefresh(interval=REFRESH * 1000, key="family_refresh")

    @st.cache_data(ttl=2)
    def get_sales_and_items(num_sales):
        sales = db.fetch_data(
            f"SELECT saleid, saletime FROM sales ORDER BY saleid DESC LIMIT {num_sales}"
        )
        if sales.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        saleids = sales['saleid'].tolist()
        if not saleids:
            return sales, pd.DataFrame(), pd.DataFrame()
        placeholders = ','.join(['%s'] * len(saleids))
        salesitems = db.fetch_data(
            f"SELECT salesitemid, saleid, itemid, quantity, totalprice FROM salesitems WHERE saleid IN ({placeholders})",
            tuple(saleids)
        )
        if salesitems.empty:
            return sales, salesitems, pd.DataFrame()
        itemids = salesitems['itemid'].unique().tolist()
        if not itemids:
            return sales, salesitems, pd.DataFrame()
        placeholders = ','.join(['%s'] * len(itemids))
        items = db.fetch_data(
            f"SELECT itemid, itemnameenglish, familycat, sectioncat, departmentcat, classcat FROM item WHERE itemid IN ({placeholders})",
            tuple(itemids)
        )
        return sales, salesitems, items

    sales, salesitems, items = get_sales_and_items(NUM_SALES)
    if sales.empty or salesitems.empty or items.empty:
        st.info("No recent sales data found for the selected period.")
        st.stop()

    merged = salesitems.merge(items, on="itemid", how="left")
    merged = merged.merge(sales[["saleid", "saletime"]], on="saleid", how="left")
    merged['saletime'] = pd.to_datetime(merged['saletime'])
    merged[GROUP_KEY] = merged[GROUP_KEY].fillna("Unknown").replace("", "Unknown")

    group_summary = (
        merged
        .groupby(GROUP_KEY, dropna=False)
        .agg(
            total_sales=('totalprice', 'sum'),
            num_transactions=('salesitemid', 'count'),
            num_items=('quantity', 'sum')
        )
        .sort_values("total_sales", ascending=False)
        .reset_index()
    )

    top_groups = group_summary.head(TOP_N)

    if top_groups.empty:
        st.info(f"No sales found for top {TOP_N} {GROUP_LABEL.lower()}s.")
    else:
        chart_data = [
            {
                "group": str(row[GROUP_KEY]) if pd.notna(row[GROUP_KEY]) else "Unknown",
                "total_sales": float(row['total_sales'])
            }
            for _, row in top_groups.iterrows()
        ]
        chart_json = json.dumps(chart_data)
        d3_code = f"""
        <script src="https://d3js.org/d3.v7.min.js"></script>
        <div id="bar_realtime"></div>
        <script>
        const data = {chart_json};
        const width = 850;
        const height = 420;
        const margin = {{top: 40, right: 40, bottom: 60, left: 120}};

        const svg = d3.select("#bar_realtime")
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
