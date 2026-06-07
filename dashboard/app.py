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
    - total_production: Annual production in pounds

Usage:
------
    python app.py

The dashboard will be available at http://localhost:1234

Dependencies: 
-------------
Read the requirements.txt for full list, key packages include:
    - dash, dash-bootstrap-components, dash-ag-grid
    - dash-bootstrap-templates
    - pandas, plotly
"""

from dash import jupyter_dash

jupyter_dash.default_mode = "external"

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from dash import Dash, html, dcc, callback, Output, Input, State
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_bootstrap_templates import ThemeSwitchAIO

# Load data (long format: State, Year, commodity, total_production)
DATA_PATH = "../SQL/USDA_production_2023.csv"
df = pd.read_csv(DATA_PATH)

# Get unique values for filters
states = sorted(df["State"].unique())
commodities = sorted(df["commodity"].unique())
min_year = int(df["Year"].min())
max_year = int(df["Year"].max())

# Theme configuration
url_theme1 = dbc.themes.BOOTSTRAP
url_theme2 = dbc.themes.DARKLY
template_theme1 = "vizro_light"
template_theme2 = "vizro_dark"

# Consistent color map for commodities across all charts
COMMODITY_COLORS = {
    "Cheese": "#5865F2",
    "Coffee": "#C66A1D",
    "Honey": "#D2A106",
    "Milk": "#009E9A",
    "Yogurt": "#D45B8C",
}

COMMODITY_ROW_STYLES = [
    {
        "condition": f"params.data.commodity === '{commodity}'",
        "style": {
            "backgroundColor": f"{color}1A",
            "borderLeft": f"4px solid {color}",
        },
    }
    for commodity, color in COMMODITY_COLORS.items()
]

FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

pio.templates[template_theme1] = go.layout.Template(
    layout=go.Layout(
        font={"family": FONT_FAMILY, "color": "#172033"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=list(COMMODITY_COLORS.values()),
        hoverlabel={
            "bgcolor": "#FFFFFF",
            "bordercolor": "#D8E0EA",
            "font": {"color": "#172033", "family": FONT_FAMILY},
        },
    )
)

pio.templates[template_theme2] = go.layout.Template(
    layout=go.Layout(
        font={"family": FONT_FAMILY, "color": "#E6ECF5"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=list(COMMODITY_COLORS.values()),
        hoverlabel={
            "bgcolor": "#172033",
            "bordercolor": "#334155",
            "font": {"color": "#F8FAFC", "family": FONT_FAMILY},
        },
    )
)


def polish_figure(
    fig,
    dark=False,
    left_margin=44,
    bottom_margin=48,
    x_tick_size=11,
    y_tick_size=11,
):
    """Apply the shared dashboard chart styling."""
    grid_color = "rgba(226, 232, 240, 0.16)" if dark else "rgba(15, 23, 42, 0.08)"
    text_color = "#E6ECF5" if dark else "#172033"
    axis_color = "#CBD5E1" if dark else "#475569"
    fig.update_layout(
        margin={"l": left_margin, "r": 24, "t": 72, "b": bottom_margin},
        font={"family": FONT_FAMILY, "size": 13, "color": text_color},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
            "title": None,
        },
        title={"x": 0.02, "xanchor": "left", "font": {"size": 17, "color": text_color}},
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        color=axis_color,
        automargin=True,
        title_font={"size": 12, "color": axis_color},
        title_standoff=10,
        tickfont={"size": x_tick_size, "color": axis_color},
    )
    fig.update_yaxes(
        tickformat=".2s",
        showgrid=True,
        gridcolor=grid_color,
        zeroline=False,
        color=axis_color,
        automargin=True,
        title_font={"size": 12, "color": axis_color},
        title_standoff=10,
        tickfont={"size": y_tick_size, "color": axis_color},
    )
    return fig

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
                        html.H1("USDA Agricultural Production Dashboard", className="app-title"),
                        html.P(
                            "Explore US agricultural production data from 1930 to 2023. "
                            "Select states, year ranges, and commodities to visualize trends.",
                            className="app-subtitle",
                        ),
                    ],
                    className="app-heading",
                )
            ),
            className="app-header",
        ),
        # Filter Controls
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label("Theme:", className="control-label"),
                        html.Div(
                            ThemeSwitchAIO(
                                aio_id="theme",
                                themes=[url_theme1, url_theme2],
                                switch_props={"className": "theme-toggle-switch"},
                            ),
                            className="theme-switch-shell",
                        ),
                    ],
                    md=1,
                    className="filter-block theme-filter",
                ),
                dbc.Col(
                    [
                        html.Label("Commodities:", className="control-label"),
                        dbc.Checklist(
                            id="commodity-checklist",
                            options=[{"label": c, "value": c} for c in commodities],
                            value=["Yogurt", "Honey"],
                            inline=True,
                            className="commodity-checklist",
                        ),
                    ],
                    md=3,
                    className="filter-block",
                ),
                dbc.Col(
                    [
                        html.Label("Year Range:", className="control-label"),
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
                            className="year-slider",
                        ),
                    ],
                    md=5,
                    className="filter-block",
                ),
                dbc.Col(
                    [
                        html.Label("Select States:", className="control-label"),
                        dcc.Dropdown(
                            id="state-dropdown",
                            options=[{"label": s, "value": s} for s in states],
                            value=["CALIFORNIA", "WISCONSIN", "NEW YORK"],
                            multi=True,
                            placeholder="Select states...",
                            className="state-dropdown",
                        ),
                    ],
                    md=3,
                    className="filter-block filter-block-last",
                ),
            ],
            className="filter-panel mb-4",
        ),
        # Line Chart row
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader(html.H5("USA Production Trends Over Time"), className="viz-card-header"),
                        dbc.CardBody(dcc.Graph(id="line-chart"), className="viz-card-body"),
                    ],
                    className="viz-card",
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
                            dbc.CardHeader(html.H5("Top 10 States (Most Recent Selected Year)"), className="viz-card-header"),
                            dbc.CardBody(dcc.Graph(id="bar-chart"), className="viz-card-body"),
                        ],
                        className="viz-card",
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
                                            className="float-end download-button",
                                        ),
                                    ]
                                ),
                                className="viz-card-header",
                            ),
                            dcc.Download(id="download-csv"),
                            dbc.CardBody(
                                dag.AgGrid(
                                    id="data-table",
                                    className="ag-theme-quartz viz-grid",
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
                                        "styleConditions": COMMODITY_ROW_STYLES
                                    },
                                ),
                                className="viz-card-body",
                            ),
                        ],
                        className="viz-card",
                    ),
                    md=6,
                ),
            ],
            className="mb-4",
        ),
    ],
    id="dashboard-shell",
    className="dashboard-shell theme-light",
    fluid=True,
)


# =============================================================================
# CALLBACKS
# =============================================================================


@callback(
    Output("dashboard-shell", "className"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_dashboard_theme(toggle):
    """Switch the dashboard shell between the light and dark visual themes."""
    return "dashboard-shell theme-light" if toggle else "dashboard-shell theme-dark"


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
            "total_production": f"<b>Production (LB)",
            "commodity": f"<b>Commodity",
        },
        markers=True,
        template=template,
    )
    fig.update_traces(marker=dict(size=7), line=dict(width=2.5))
    fig.update_layout(hovermode="x unified")
    return polish_figure(fig, dark=not toggle)


@callback(
    Output("bar-chart", "figure"),
    Input("year-slider", "value"),
    Input("commodity-checklist", "value"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_bar_chart(year_range, selected_commodities, toggle):
    """
    Update bar chart showing top 10 producing states.

    Displays the top 10 states by total production for the latest available
    data year inside the selected range.

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

    available_years = df[
        (df["Year"] >= year_range[0])
        & (df["Year"] <= year_range[1])
        & (df["commodity"].isin(selected_commodities))
    ]["Year"]
    commodity_label = ", ".join(selected_commodities)

    if available_years.empty:
        fig = go.Figure()
        fig.update_layout(
            title=f"<b>Top 10 States - {commodity_label} Production</b>",
            template=template,
            annotations=[
                {
                    "text": "No production records in the selected year range",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                }
            ],
            xaxis={"visible": False},
            yaxis={"visible": False},
        )
        return polish_figure(fig, dark=not toggle)

    selected_year = int(available_years.max())

    # Aggregate production across selected commodities by state
    filtered_df = df[
        (df["Year"] == selected_year)
        & (df["commodity"].isin(selected_commodities))
    ].groupby(["State", "commodity"])["total_production"].sum().reset_index()

    filtered_df = filtered_df.dropna(subset=["total_production"])
    state_totals = (
        filtered_df.groupby("State", as_index=False)["total_production"]
        .sum()
        .rename(columns={"total_production": "state_total_production"})
    )
    top_states = state_totals.nlargest(10, "state_total_production")["State"].tolist()
    top_10 = filtered_df[filtered_df["State"].isin(top_states)].copy()

    fig = px.bar(
        top_10,
        x="State",
        y="total_production",
        color="commodity",
        color_discrete_map=COMMODITY_COLORS,
        title=f"<b>Top 10 States - {commodity_label} Production ({selected_year})</b>",
        labels={"total_production": "Production (LB)", "State": "State", "commodity": "Commodity"},
        category_orders={"State": top_states},
        template=template,
    )
    fig.update_layout(
        barmode="stack",
        xaxis_tickangle=-45,
    )

    return polish_figure(
        fig,
        dark=not toggle,
        left_margin=58,
        bottom_margin=88,
        x_tick_size=10,
    )


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
    app.run(debug=True, port=1234, use_reloader=False)
