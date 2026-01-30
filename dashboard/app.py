"""
USDA Agricultural Production Dashboard
=======================================

An interactive Dash application for visualizing USDA agricultural production
data (1930-2023) across US states for milk, cheese, yogurt, honey, and coffee.

Features:
---------
- Interactive line chart showing production trends over time
- Bar chart displaying top 10 producing states for selected year
- Filterable data table with CSV export functionality
- Dark/light theme toggle
- Multi-select filters for commodities, states, and year range

Data Requirements:
------------------
Expects a CSV file at '../SQL/USDA_production_2023.csv' with columns:
    - State: US state name (uppercase)
    - Year: Production year (integer)
    - commodity: Product type (Cheese, Coffee, Honey, Milk, Yogurt)
    - total_production: Production value in USD

Usage:
------
    python app.py

The dashboard will be available at http://localhost:1234

Dependencies:
-------------
    - dash, dash-bootstrap-components, dash-ag-grid
    - dash-bootstrap-templates
    - pandas, plotly
"""

from dash import jupyter_dash

jupyter_dash.default_mode = "external"

import pandas as pd
import plotly.express as px
from dash import Dash, html, dcc, callback, Output, Input, State
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_bootstrap_templates import ThemeSwitchAIO, load_figure_template

# Load data (long format: State, Year, commodity, total_production)
DATA_PATH = "../SQL/USDA_production_2023.csv"
df = pd.read_csv(DATA_PATH)

# Get unique values for filters
states = sorted(df["State"].unique())
commodities = sorted(df["commodity"].unique())
min_year = int(df["Year"].min())
max_year = int(df["Year"].max())

# Theme configuration
url_theme1 = dbc.themes.COSMO
url_theme2 = dbc.themes.CYBORG
template_theme1 = "cosmo"
template_theme2 = "cyborg"

# Consistent color map for commodities across all charts
COMMODITY_COLORS = {
    "Cheese": "#636EFA",
    "Coffee": "#EF553B",
    "Honey": "#00CC96",
    "Milk": "#AB63FA",
    "Yogurt": "#FFA15A",
}

# Load figure templates for both themes
load_figure_template([template_theme1, template_theme2])

# Initialize Dash app with both theme stylesheets
app = Dash(__name__, external_stylesheets=[url_theme1, url_theme2])
app.title = "USDA Production Dashboard"

# Layout
app.layout = dbc.Container(
    [
        # Header
        dbc.Row(
            dbc.Col(
                html.Div(
                    [
                        html.H1("USDA Agricultural Production Dashboard"),
                        html.P(
                            "Explore US agricultural production data from 1930 to 2023. "
                            "Select states, year ranges, and commodities to visualize trends."
                        ),
                    ],
                    className="text-center my-4",
                )
            )
        ),
        # Filter Controls
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label("Theme:", className="fw-bold"),
                        ThemeSwitchAIO(aio_id="theme", themes=[url_theme1, url_theme2]),
                    ],
                    md=1,
                    style={"borderRight": "1px solid #dee2e6", "paddingRight": "15px"},
                ),
                dbc.Col(
                    [
                        html.Label("Commodities:", className="fw-bold"),
                        dbc.Checklist(
                            id="commodity-checklist",
                            options=[{"label": c, "value": c} for c in commodities],
                            value=["Yogurt", "Honey"],
                            inline=True,
                        ),
                    ],
                    md=3,
                    style={"borderRight": "1px solid #dee2e6", "paddingRight": "15px"},
                ),
                dbc.Col(
                    [
                        html.Label("Year Range:", className="fw-bold"),
                        dcc.RangeSlider(
                            id="year-slider",
                            min=min_year,
                            max=max_year,
                            value=[2000, max_year],
                            marks={
                                y: str(y)
                                for y in range(min_year, max_year + 1, 10)
                            },
                            step=1,
                            tooltip={"placement": "bottom", "always_visible": True},
                        ),
                    ],
                    md=5,
                    style={"borderRight": "1px solid #dee2e6", "paddingRight": "15px"},
                ),
                dbc.Col(
                    [
                        html.Label("Select States:", className="fw-bold"),
                        dcc.Dropdown(
                            id="state-dropdown",
                            options=[{"label": s, "value": s} for s in states],
                            value=["CALIFORNIA", "WISCONSIN", "NEW YORK"],
                            multi=True,
                            placeholder="Select states...",
                        ),
                    ],
                    md=3,
                ),
            ],
            className="mb-4 p-3 bg-light rounded",
        ),
        # Line Chart
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(html.H5("USA Production Trends Over Time")),
                        dbc.CardBody(dcc.Graph(id="line-chart")),
                    ]
                ),
                width=12,
            ),
            className="mb-4",
        ),
        # Bar Chart and Data Table Row
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H5("Top 10 States (Most Recent Selected Year)")),
                            dbc.CardBody(dcc.Graph(id="bar-chart")),
                        ]
                    ),
                    md=6,
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(
                                html.Div(
                                    [
                                        html.H5("Filtered Data From Selected States", className="d-inline"),
                                        dbc.Button(
                                            "Download CSV",
                                            id="download-btn",
                                            color="primary",
                                            size="sm",
                                            className="float-end",
                                        ),
                                    ]
                                )
                            ),
                            dcc.Download(id="download-csv"),
                            dbc.CardBody(
                                dag.AgGrid(
                                    id="data-table",
                                    className="ag-theme-balham",
                                    columnDefs=[
                                        {"field": "State", "sortable": True, "filter": True},
                                        {"field": "Year", "sortable": True, "filter": True},
                                        {"field": "commodity", "sortable": True, "filter": True},
                                        {
                                            "field": "total_production",
                                            "sortable": True,
                                            "filter": True,
                                            "valueFormatter": {
                                                "function": "d3.format(',.0f')(params.value)"
                                            },
                                        },
                                    ],
                                    defaultColDef={"resizable": True},
                                    style={"height": "400px"},
                                    dashGridOptions={
                                        "pagination": True,
                                        "paginationPageSize": 10,
                                    },
                                    getRowStyle={
                                        "styleConditions": [
                                            {"condition": "params.data.commodity === 'Cheese'", "style": {"backgroundColor": "#636EFA", "color": "white"}},
                                            {"condition": "params.data.commodity === 'Coffee'", "style": {"backgroundColor": "#EF553B", "color": "white"}},
                                            {"condition": "params.data.commodity === 'Honey'", "style": {"backgroundColor": "#00CC96", "color": "white"}},
                                            {"condition": "params.data.commodity === 'Milk'", "style": {"backgroundColor": "#AB63FA", "color": "white"}},
                                            {"condition": "params.data.commodity === 'Yogurt'", "style": {"backgroundColor": "#FFA15A", "color": "white"}},
                                        ]
                                    },
                                )
                            ),
                        ]
                    ),
                    md=6,
                ),
            ],
            className="mb-4",
        ),
    ],
    fluid=True,
)


# =============================================================================
# CALLBACKS
# =============================================================================


@callback(
    Output("line-chart", "figure"),
    Input("year-slider", "value"),
    Input("commodity-checklist", "value"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_line_chart(year_range, selected_commodities, toggle):
    """
    Update line chart showing national production trends over time.

    Aggregates production data across all states by commodity and year,
    displaying trends for selected commodities within the specified year range.

    Args:
        year_range: List of [start_year, end_year] from the range slider.
        selected_commodities: List of commodity names to display.
        toggle: Boolean for theme selection (True=light, False=dark).

    Returns:
        plotly.graph_objects.Figure: Line chart with markers showing production trends.
    """
    template = template_theme1 if toggle else template_theme2

    if not selected_commodities:
        selected_commodities = ["Yogurt", "Honey"]

    filtered_df = df[
        (df["Year"] >= year_range[0])
        & (df["Year"] <= year_range[1])
        & (df["commodity"].isin(selected_commodities))
    ].groupby(["commodity", "Year"])["total_production"].sum().reset_index().copy()

    title = f"<b>{', '.join(selected_commodities)} Production by Year"

    fig = px.line(
        filtered_df,
        x="Year",
        y="total_production",
        color="commodity",
        color_discrete_map=COMMODITY_COLORS,
        title=title,
        labels={
            "Year": f"<b>Year",
            "total_production": f"<b>Production (USD)",
            "commodity": f"<b>Commodity",
        },
        markers=True,
        template=template,
    )
    fig.update_traces(marker=dict(size=10))
    fig.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title={'x':0.5}
    )
    return fig


@callback(
    Output("bar-chart", "figure"),
    Input("year-slider", "value"),
    Input("commodity-checklist", "value"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_bar_chart(year_range, selected_commodities, toggle):
    """
    Update bar chart showing top 10 producing states.

    Displays the top 10 states by production value for the most recent year
    in the selected range. If the selected year exceeds available data,
    falls back to the latest year with data.

    Args:
        year_range: List of [start_year, end_year] from the range slider.
        selected_commodities: List of commodity names to include.
        toggle: Boolean for theme selection (True=light, False=dark).

    Returns:
        plotly.graph_objects.Figure: Grouped bar chart of top producing states.
    """
    template = template_theme1 if toggle else template_theme2

    if not selected_commodities:
        selected_commodities = ["Yogurt", "Honey"]

    # Find the latest year with data for selected commodities
    lastyear = int(df[df["commodity"].isin(selected_commodities)]["Year"].max())
    if int(year_range[1]) > lastyear:
        selected_year = lastyear
    else:
        selected_year = year_range[1]

    # Aggregate production across selected commodities by state
    filtered_df = df[
        (df["Year"] == selected_year)
        & (df["commodity"].isin(selected_commodities))
    ].groupby(["State", "commodity"])["total_production"].sum().reset_index()

    filtered_df = filtered_df.dropna(subset=["total_production"])
    top_10 = filtered_df.nlargest(10, "total_production")
    commodity_label = ", ".join(selected_commodities)
    fig = px.bar(
        top_10,
        x="State",
        y="total_production",
        color="commodity",
        color_discrete_map=COMMODITY_COLORS,
        title=f"<b>Top 10 States - {commodity_label} Production ({selected_year})",
        labels={"total_production": f"<b>Production (USD)", "State": f"<b>State", "commodity": f"<b>Commodity"},
        template=template,
    )
    fig.update_layout(
        xaxis_tickangle=-45,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), 
        title={'x':0.5}
    )

    return fig


@callback(
    Output("data-table", "rowData"),
    Input("state-dropdown", "value"),
    Input("year-slider", "value"),
    Input("commodity-checklist", "value"),
)
def update_table(selected_states, year_range, selected_commodities):
    """
    Update the data table with filtered production records.

    Filters the dataset by selected states, year range, and commodities,
    then sorts results by state (ascending), year (descending), and commodity.

    Args:
        selected_states: List of state names to include in the table.
        year_range: List of [start_year, end_year] from the range slider.
        selected_commodities: List of commodity names to include.

    Returns:
        list[dict]: List of row dictionaries for the AG Grid table.
    """
    if not selected_states:
        selected_states = states[:3]

    if not selected_commodities:
        selected_commodities = ["Yogurt", "Honey"]

    filtered_df = df[
        (df["State"].isin(selected_states))
        & (df["Year"] >= year_range[0])
        & (df["Year"] <= year_range[1])
        & (df["commodity"].isin(selected_commodities))
    ].copy()

    filtered_df = filtered_df.dropna(subset=["total_production"])
    filtered_df = filtered_df.sort_values(["State", "Year", "commodity"], ascending=[True, False, True])

    return filtered_df.to_dict("records")


@callback(
    Output("download-csv", "data"),
    Input("download-btn", "n_clicks"),
    State("state-dropdown", "value"),
    State("year-slider", "value"),
    State("commodity-checklist", "value"),
    prevent_initial_call=True,
)
def download_csv(n_clicks, selected_states, year_range, selected_commodities):
    """
    Generate and download filtered data as a CSV file.

    Triggered by the Download CSV button click. Applies the same filters
    as the data table and exports the results to a downloadable CSV file.

    Args:
        n_clicks: Number of times the download button has been clicked.
        selected_states: List of state names from the dropdown (State).
        year_range: List of [start_year, end_year] from the slider (State).
        selected_commodities: List of commodity names from checklist (State).

    Returns:
        dict: Download data object with CSV content, or None if not triggered.
    """
    if not n_clicks:
        return None

    if not selected_states:
        selected_states = states[:3]

    if not selected_commodities:
        selected_commodities = ["Yogurt", "Honey"]

    filtered_df = df[
        (df["State"].isin(selected_states))
        & (df["Year"] >= year_range[0])
        & (df["Year"] <= year_range[1])
        & (df["commodity"].isin(selected_commodities))
    ].copy()

    filtered_df = filtered_df.dropna(subset=["total_production"])
    filtered_df = filtered_df.sort_values(["State", "Year", "commodity"], ascending=[True, False, True])

    return dcc.send_data_frame(filtered_df.to_csv, "usda_production_filtered_data.csv", index=False)


if __name__ == "__main__":
    app.run(debug=True, port=1234)
