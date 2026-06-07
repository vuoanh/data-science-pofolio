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
- Model Validation tab: actual vs predicted, metric cards, largest-miss table
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
Read the requirements.txt for full list, key packages include:
    - dash, dash-bootstrap-components, dash-ag-grid
    - dash-bootstrap-templates
    - pandas, plotly
"""

from dash import jupyter_dash

jupyter_dash.default_mode = "external"

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, html, dcc, callback, Output, Input, State
import dash_bootstrap_components as dbc
import dash_ag_grid as dag
from dash_bootstrap_templates import ThemeSwitchAIO, load_figure_template

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

DATA_PATH = "../SQL/USDA_production_2023.csv"
PREDICTIONS_PATH = Path(__file__).parent / "../models/test_predictions.csv"

df = pd.read_csv(DATA_PATH)

predictions_df = pd.DataFrame()
if PREDICTIONS_PATH.exists():
    predictions_df = pd.read_csv(PREDICTIONS_PATH)
    predictions_df["abs_error"] = (
        predictions_df["prediction"] - predictions_df["target_next_year_production"]
    ).abs()

states = sorted(df["State"].unique())
commodities = sorted(df["commodity"].unique())
min_year = int(df["Year"].min())
max_year = int(df["Year"].max())

MODEL_LABELS = {
    "baseline_previous_year": "Persistence Baseline",
    "baseline_rolling_3_year": "Rolling 3-Year Baseline",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
}
available_models = (
    sorted(predictions_df["model"].unique().tolist())
    if not predictions_df.empty
    else []
)

# ---------------------------------------------------------------------------
# Theme configuration
# ---------------------------------------------------------------------------

url_theme1 = dbc.themes.COSMO
url_theme2 = dbc.themes.CYBORG
template_theme1 = "cosmo"
template_theme2 = "cyborg"

COMMODITY_COLORS = {
    "Cheese": "#636EFA",
    "Coffee": "#EF553B",
    "Honey": "#00CC96",
    "Milk": "#AB63FA",
    "Yogurt": "#FFA15A",
}

load_figure_template([template_theme1, template_theme2])

app = Dash(__name__, external_stylesheets=[url_theme1, url_theme2])
app.title = "USDA Production Dashboard"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_STATES = ["CALIFORNIA", "WISCONSIN", "NEW YORK"]
DEFAULT_COMMODITIES = ["Yogurt", "Honey"]


def _metric_card(label: str, card_id: str) -> dbc.Col:
    return dbc.Col(
        dbc.Card(
            dbc.CardBody([
                html.P(label, className="text-muted small mb-1"),
                html.H4("—", id=card_id, className="mb-0"),
            ]),
            className="text-center h-100",
        ),
        md=3,
    )


def _filter_predictions(model: str, commodities_sel: list, states_sel: list) -> pd.DataFrame:
    if predictions_df.empty:
        return pd.DataFrame()
    mask = predictions_df["model"] == model
    if commodities_sel:
        mask &= predictions_df["commodity"].isin(commodities_sel)
    if states_sel:
        mask &= predictions_df["State"].isin(states_sel)
    return predictions_df[mask].copy()


def _apply_table_filters(
    selected_states: list,
    year_range: list,
    selected_commodities: list,
) -> pd.DataFrame:
    states_sel = selected_states or DEFAULT_STATES
    commodities_sel = selected_commodities or DEFAULT_COMMODITIES
    filtered = df[
        df["State"].isin(states_sel)
        & (df["Year"] >= year_range[0])
        & (df["Year"] <= year_range[1])
        & df["commodity"].isin(commodities_sel)
    ].copy()
    filtered = filtered.dropna(subset=["total_production"])
    return filtered.sort_values(["State", "Year", "commodity"], ascending=[True, False, True])


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

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
        # Global filter controls
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
                            marks={y: str(y) for y in range(min_year, max_year + 1, 10)},
                            step=1,
                            tooltip={"placement": "bottom", "always_visible": True},
                        ),
                    ],
                    md=4,
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
                    md=4,
                ),
            ],
            className="mb-4 p-3 bg-light rounded",
        ),
        # Tabs
        dbc.Tabs(
            id="dashboard-tabs",
            active_tab="trends-tab",
            children=[
                # ----------------------------------------------------------
                # Tab 1: Production Trends
                # ----------------------------------------------------------
                dbc.Tab(label="Production Trends", tab_id="trends-tab", children=[
                    dbc.Row(
                        dbc.Col(
                            dbc.Card([
                                dbc.CardHeader(html.H5("USA Production Trends Over Time")),
                                dbc.CardBody(dcc.Graph(id="line-chart")),
                            ]),
                            width=12,
                        ),
                        className="mb-4 mt-3",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Card([
                                    dbc.CardHeader(html.H5("Top 10 States (Most Recent Selected Year)")),
                                    dbc.CardBody(dcc.Graph(id="bar-chart")),
                                ]),
                                md=6,
                            ),
                            dbc.Col(
                                dbc.Card([
                                    dbc.CardHeader(
                                        html.Div([
                                            html.H5("Filtered Data From Selected States", className="d-inline"),
                                            dbc.Button(
                                                "Download CSV",
                                                id="download-btn",
                                                color="primary",
                                                size="sm",
                                                className="float-end",
                                            ),
                                        ])
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
                                ]),
                                md=6,
                            ),
                        ],
                        className="mb-4",
                    ),
                ]),

                # ----------------------------------------------------------
                # Tab 2: Model Validation
                # ----------------------------------------------------------
                dbc.Tab(label="Model Validation", tab_id="validation-tab", children=[
                    # Model selector
                    dbc.Row(
                        dbc.Col(
                            [
                                html.Label("Model:", className="fw-bold"),
                                dcc.Dropdown(
                                    id="model-selector",
                                    options=[
                                        {"label": MODEL_LABELS.get(m, m), "value": m}
                                        for m in available_models
                                    ],
                                    value=(
                                        "random_forest"
                                        if "random_forest" in available_models
                                        else (available_models[0] if available_models else None)
                                    ),
                                    clearable=False,
                                    style={"maxWidth": "320px"},
                                ),
                                html.P(
                                    "Test period: 2019–2023. Commodity and state filters above apply. "
                                    "The chart aggregates across selected states.",
                                    className="text-muted small mt-2 mb-0",
                                ),
                            ],
                            md=6,
                        ),
                        className="mt-3 mb-3",
                    ),
                    # Actual vs Predicted time series
                    dbc.Row(
                        dbc.Col(
                            dbc.Card([
                                dbc.CardHeader(html.H5("Actual vs Predicted Production (Test Period 2019–2023)")),
                                dbc.CardBody(dcc.Graph(id="actual-vs-pred-chart")),
                            ]),
                            width=12,
                        ),
                        className="mb-4",
                    ),
                    # Metric cards
                    dbc.Row(
                        [
                            _metric_card("MAE", "metric-mae"),
                            _metric_card("RMSE", "metric-rmse"),
                            _metric_card("MAPE", "metric-mape"),
                            _metric_card("R²", "metric-r2"),
                        ],
                        className="mb-4",
                    ),
                    # Largest misses table
                    dbc.Row(
                        dbc.Col(
                            dbc.Card([
                                dbc.CardHeader(html.H5("Largest Forecast Misses")),
                                dbc.CardBody(
                                    dag.AgGrid(
                                        id="misses-table",
                                        className="ag-theme-balham",
                                        columnDefs=[
                                            {"field": "State", "sortable": True, "filter": True},
                                            {"field": "commodity", "sortable": True, "filter": True},
                                            {"field": "target_year", "sortable": True, "headerName": "Forecast Year"},
                                            {
                                                "field": "target_next_year_production",
                                                "headerName": "Actual",
                                                "sortable": True,
                                                "valueFormatter": {"function": "d3.format(',.0f')(params.value)"},
                                            },
                                            {
                                                "field": "prediction",
                                                "headerName": "Predicted",
                                                "sortable": True,
                                                "valueFormatter": {"function": "d3.format(',.0f')(params.value)"},
                                            },
                                            {
                                                "field": "abs_error",
                                                "headerName": "Abs Error",
                                                "sortable": True,
                                                "valueFormatter": {"function": "d3.format(',.0f')(params.value)"},
                                            },
                                        ],
                                        defaultColDef={"resizable": True},
                                        style={"height": "380px"},
                                        dashGridOptions={"pagination": True, "paginationPageSize": 10},
                                    )
                                ),
                            ]),
                            width=12,
                        ),
                        className="mb-4",
                    ),
                ]),
            ],
        ),
    ],
    fluid=True,
)


# ===========================================================================
# CALLBACKS — Production Trends tab
# ===========================================================================


@callback(
    Output("line-chart", "figure"),
    Input("year-slider", "value"),
    Input("commodity-checklist", "value"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_line_chart(year_range, selected_commodities, toggle):
    template = template_theme1 if toggle else template_theme2

    if not selected_commodities:
        selected_commodities = DEFAULT_COMMODITIES

    filtered = df[
        (df["Year"] >= year_range[0])
        & (df["Year"] <= year_range[1])
        & (df["commodity"].isin(selected_commodities))
    ].groupby(["commodity", "Year"])["total_production"].sum().reset_index()

    fig = px.line(
        filtered,
        x="Year",
        y="total_production",
        color="commodity",
        color_discrete_map=COMMODITY_COLORS,
        title=f"<b>{', '.join(selected_commodities)} Production by Year",
        labels={
            "Year": "<b>Year",
            "total_production": "<b>Production (USD)",
            "commodity": "<b>Commodity",
        },
        markers=True,
        template=template,
    )
    fig.update_traces(marker=dict(size=10))
    fig.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title={"x": 0.5},
    )
    return fig


@callback(
    Output("bar-chart", "figure"),
    Input("year-slider", "value"),
    Input("commodity-checklist", "value"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_bar_chart(year_range, selected_commodities, toggle):
    template = template_theme1 if toggle else template_theme2

    if not selected_commodities:
        selected_commodities = DEFAULT_COMMODITIES

    lastyear = int(df[df["commodity"].isin(selected_commodities)]["Year"].max())
    selected_year = min(int(year_range[1]), lastyear)

    filtered = df[
        (df["Year"] == selected_year)
        & (df["commodity"].isin(selected_commodities))
    ].groupby(["State", "commodity"])["total_production"].sum().reset_index()
    filtered = filtered.dropna(subset=["total_production"])

    # Rank by total across commodities, then keep top 10 distinct states
    top_states = filtered.groupby("State")["total_production"].sum().nlargest(10).index
    top_10 = filtered[filtered["State"].isin(top_states)]

    fig = px.bar(
        top_10,
        x="State",
        y="total_production",
        color="commodity",
        color_discrete_map=COMMODITY_COLORS,
        title=f"<b>Top 10 States - {', '.join(selected_commodities)} Production ({selected_year})",
        labels={
            "total_production": "<b>Production (USD)",
            "State": "<b>State",
            "commodity": "<b>Commodity",
        },
        template=template,
    )
    fig.update_layout(
        xaxis_tickangle=-45,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title={"x": 0.5},
    )
    return fig


@callback(
    Output("data-table", "rowData"),
    Input("state-dropdown", "value"),
    Input("year-slider", "value"),
    Input("commodity-checklist", "value"),
)
def update_table(selected_states, year_range, selected_commodities):
    return _apply_table_filters(selected_states, year_range, selected_commodities).to_dict("records")


@callback(
    Output("download-csv", "data"),
    Input("download-btn", "n_clicks"),
    State("state-dropdown", "value"),
    State("year-slider", "value"),
    State("commodity-checklist", "value"),
    prevent_initial_call=True,
)
def download_csv(_n_clicks, selected_states, year_range, selected_commodities):
    filtered = _apply_table_filters(selected_states, year_range, selected_commodities)
    return dcc.send_data_frame(filtered.to_csv, "usda_production_filtered_data.csv", index=False)


# ===========================================================================
# CALLBACKS — Model Validation tab
# ===========================================================================


@callback(
    Output("actual-vs-pred-chart", "figure"),
    Output("metric-mae", "children"),
    Output("metric-rmse", "children"),
    Output("metric-mape", "children"),
    Output("metric-r2", "children"),
    Output("misses-table", "rowData"),
    Input("model-selector", "value"),
    Input("commodity-checklist", "value"),
    Input("state-dropdown", "value"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_model_validation(selected_model, selected_commodities, selected_states, toggle):
    template = template_theme1 if toggle else template_theme2
    empty_fig = go.Figure().update_layout(
        template=template,
        title={"text": "No model predictions available", "x": 0.5},
    )
    no_data = (empty_fig, "—", "—", "—", "—", [])

    if predictions_df.empty or not selected_model:
        return no_data

    commodities_sel = selected_commodities or DEFAULT_COMMODITIES
    filtered = _filter_predictions(selected_model, commodities_sel, selected_states)

    if filtered.empty:
        return no_data

    # Actual vs Predicted time series — aggregate national totals per commodity
    agg = (
        filtered.groupby(["commodity", "target_year"])
        .agg(
            actual=("target_next_year_production", "sum"),
            predicted=("prediction", "sum"),
        )
        .reset_index()
    )
    long = pd.melt(
        agg,
        id_vars=["commodity", "target_year"],
        value_vars=["actual", "predicted"],
        var_name="series",
        value_name="production",
    )
    long["series"] = long["series"].str.title()

    fig = px.line(
        long,
        x="target_year",
        y="production",
        color="commodity",
        line_dash="series",
        color_discrete_map=COMMODITY_COLORS,
        title=f"<b>Actual vs Predicted — {MODEL_LABELS.get(selected_model, selected_model)}",
        labels={
            "target_year": "<b>Forecast Year",
            "production": "<b>Production",
            "commodity": "<b>Commodity",
            "series": "<b>Series",
        },
        markers=True,
        template=template,
    )
    fig.update_traces(marker=dict(size=8))
    fig.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        title={"x": 0.5},
    )

    # Metric cards
    y_true = filtered["target_next_year_production"].to_numpy(dtype=float)
    y_pred = filtered["prediction"].to_numpy(dtype=float)
    errors = y_pred - y_true
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    nonzero = y_true != 0
    mape = float(np.mean(np.abs(errors[nonzero] / y_true[nonzero])) * 100) if nonzero.any() else float("nan")
    ss_res = float(np.sum(errors ** 2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot != 0 else float("nan")

    def _fmt(v: float, style: str = "number") -> str:
        if np.isnan(v):
            return "—"
        if style == "pct":
            return f"{v:.1f}%"
        if style == "r2":
            return f"{v:.3f}"
        return f"{v:,.0f}"

    misses = (
        filtered[["State", "commodity", "target_year", "target_next_year_production", "prediction", "abs_error"]]
        .sort_values("abs_error", ascending=False)
        .head(20)
        .round(0)
        .to_dict("records")
    )

    return (fig, _fmt(mae), _fmt(rmse), _fmt(mape, "pct"), _fmt(r2, "r2"), misses)


if __name__ == "__main__":
    app.run(debug=True, port=1234)
