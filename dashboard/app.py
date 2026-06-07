"""
USDA Agricultural Production Dashboard
======================================

An interactive Dash application for exploring USDA commodity production,
forward forecasts, and model validation results.

Features:
---------
- Overview tab with business KPI cards and production trends
- State Trends tab for selected-state production patterns
- Forecasts tab backed by latest per-state/commodity forecasts
- Model Validation tab for actual vs predicted performance review
- Filterable data table with CSV export
- Dark/light theme toggle

Data Requirements:
------------------
Expects a CSV file at 'SQL/USDA_production_2023.csv' with columns:
    - State: US state name
    - Year: Production year
    - commodity: Product type
    - total_production: Production value in LB

Usage:
------
    python app.py

The dashboard will be available at http://localhost:1234
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

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_PATH = PROJECT_ROOT / "SQL/USDA_production_2023.csv"
PREDICTIONS_PATH = PROJECT_ROOT / "models/test_predictions.csv"
FORECASTS_PATH = PROJECT_ROOT / "models/latest_forecasts.csv"

df = pd.read_csv(DATA_PATH)
df["Year"] = df["Year"].astype(int)
df["total_production"] = pd.to_numeric(df["total_production"], errors="coerce")

predictions_df = pd.DataFrame()
if PREDICTIONS_PATH.exists():
    predictions_df = pd.read_csv(PREDICTIONS_PATH)
    predictions_df["abs_error"] = (
        predictions_df["prediction"] - predictions_df["target_next_year_production"]
    ).abs()
    for col in ["pi_80_lower", "pi_95_lower"]:
        if col in predictions_df:
            predictions_df[col] = predictions_df[col].clip(lower=0)

forecasts_df = pd.DataFrame()
if FORECASTS_PATH.exists():
    forecasts_df = pd.read_csv(FORECASTS_PATH)
    for col in ["pi_80_lower", "pi_95_lower"]:
        if col in forecasts_df:
            forecasts_df[col] = forecasts_df[col].clip(lower=0)

states = sorted(df["State"].dropna().unique())
commodities = sorted(df["commodity"].dropna().unique())
min_year = int(df["Year"].min())
max_year = int(df["Year"].max())

MODEL_LABELS = {
    "baseline_previous_year": "Persistence Baseline",
    "baseline_rolling_3_year": "Rolling 3-Year Baseline",
    "random_forest": "Random Forest",
    "xgboost": "XGBoost",
}

_prediction_models = set(predictions_df["model"].unique()) if not predictions_df.empty else set()
_forecast_models = set(forecasts_df["model"].unique()) if not forecasts_df.empty else set()
available_models = [
    model for model in MODEL_LABELS if model in (_prediction_models | _forecast_models)
]
default_model = (
    "random_forest"
    if "random_forest" in available_models
    else (available_models[0] if available_models else None)
)

# ---------------------------------------------------------------------------
# Theme configuration
# ---------------------------------------------------------------------------

url_theme1 = dbc.themes.COSMO
url_theme2 = dbc.themes.CYBORG
template_theme1 = "cosmo"
template_theme2 = "cyborg"

COMMODITY_COLORS = {
    "Cheese": "#2563EB",
    "Coffee": "#92400E",
    "Honey": "#D97706",
    "Milk": "#0F766E",
    "Yogurt": "#7C3AED",
}

COMMODITY_ROW_STYLES = [
    {
        "condition": f"params.data.commodity === '{commodity}'",
        "style": {"borderLeft": f"4px solid {color}"},
    }
    for commodity, color in COMMODITY_COLORS.items()
]

load_figure_template([template_theme1, template_theme2])

app = Dash(__name__, external_stylesheets=[url_theme1, url_theme2])
app.title = "USDA Commodity Production"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_STATES = ["CALIFORNIA", "WISCONSIN", "NEW YORK"]
DEFAULT_COMMODITIES = ["Yogurt", "Honey"]


def _model_options() -> list[dict]:
    return [{"label": MODEL_LABELS.get(model, model), "value": model} for model in available_models]


def _compact_number(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    value = float(value)
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if abs_value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs_value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def _format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value:+.1f}%"


def _theme_values(toggle: bool) -> dict:
    if toggle:
        return {
            "template": template_theme1,
            "text": "#172033",
            "muted": "#64748B",
            "grid": "#D8E0EA",
            "surface": "rgba(255,255,255,0)",
            "hover_bg": "#FFFFFF",
            "hover_border": "#C4D2DF",
            "hover_text": "#172033",
        }
    return {
        "template": template_theme2,
        "text": "#F8FAFC",
        "muted": "#B6C2D1",
        "grid": "#334155",
        "surface": "rgba(255,255,255,0)",
        "hover_bg": "#1D2A40",
        "hover_border": "#475569",
        "hover_text": "#F8FAFC",
    }


def _polish_figure(fig: go.Figure, toggle: bool, height: int | None = None) -> go.Figure:
    theme = _theme_values(toggle)
    fig.update_layout(
        template=theme["template"],
        paper_bgcolor=theme["surface"],
        plot_bgcolor=theme["surface"],
        font={"family": "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", "color": theme["text"]},
        margin={"l": 34, "r": 18, "t": 18, "b": 42},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.03,
            "xanchor": "right",
            "x": 1,
            "font": {"size": 12},
        },
        hovermode="x unified",
        hoverlabel={
            "bgcolor": theme["hover_bg"],
            "bordercolor": theme["hover_border"],
            "font": {
                "family": "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif",
                "color": theme["hover_text"],
                "size": 12,
            },
            "namelength": -1,
        },
    )
    if height:
        fig.update_layout(height=height)
    fig.update_xaxes(
        showgrid=True,
        gridcolor=theme["grid"],
        zeroline=False,
        automargin=True,
        title_font={"size": 12},
        tickfont={"size": 11, "color": theme["muted"]},
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=theme["grid"],
        zeroline=False,
        automargin=True,
        title_font={"size": 12},
        tickfont={"size": 11, "color": theme["muted"]},
        tickformat=".2s",
    )
    return fig


def _empty_figure(message: str, toggle: bool) -> go.Figure:
    theme = _theme_values(toggle)
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 14, "color": theme["muted"]},
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _polish_figure(fig, toggle, height=320)


def _kpi_card(label: str, value_id: str, meta_id: str, accent: str) -> dbc.Col:
    return dbc.Col(
        html.Div(
            [
                html.Div(label, className="kpi-label"),
                html.Div("-", id=value_id, className="kpi-value"),
                html.Div("-", id=meta_id, className="kpi-meta"),
            ],
            className=f"kpi-card accent-{accent}",
        ),
        md=6,
        xl=3,
    )


def _viz_card(title: str, body, subtitle: str | None = None, action=None, class_name: str = "") -> dbc.Card:
    header_children = [
        html.Div(
            [
                html.H3(title, className="viz-card-title"),
                html.Div(subtitle, className="viz-card-subtitle") if subtitle else None,
            ],
            className="viz-card-heading",
        )
    ]
    if action is not None:
        header_children.append(action)

    return dbc.Card(
        [
            dbc.CardHeader(
                html.Div(header_children, className="viz-card-header-row"),
                className="viz-card-header",
            ),
            dbc.CardBody(body, className="viz-card-body"),
        ],
        className=f"viz-card {class_name}".strip(),
    )


def _graph(graph_id: str, height: int = 360) -> dcc.Graph:
    return dcc.Graph(id=graph_id, config={"displayModeBar": False}, style={"height": f"{height}px"})


def _filter_raw(
    year_range: list[int] | None,
    selected_commodities: list[str] | None,
    selected_states: list[str] | None = None,
) -> pd.DataFrame:
    commodities_sel = selected_commodities or DEFAULT_COMMODITIES
    filtered = df[df["commodity"].isin(commodities_sel)].copy()
    if year_range:
        filtered = filtered[(filtered["Year"] >= year_range[0]) & (filtered["Year"] <= year_range[1])]
    if selected_states:
        filtered = filtered[filtered["State"].isin(selected_states)]
    return filtered.dropna(subset=["total_production"])


def _filter_predictions(model: str | None, commodities_sel: list[str] | None, states_sel: list[str] | None) -> pd.DataFrame:
    if predictions_df.empty or not model:
        return pd.DataFrame()
    filtered = predictions_df[predictions_df["model"] == model].copy()
    if commodities_sel:
        filtered = filtered[filtered["commodity"].isin(commodities_sel)]
    if states_sel:
        filtered = filtered[filtered["State"].isin(states_sel)]
    return filtered


def _filter_forecasts(model: str | None, commodities_sel: list[str] | None, states_sel: list[str] | None) -> pd.DataFrame:
    if forecasts_df.empty or not model:
        return pd.DataFrame()
    filtered = forecasts_df[forecasts_df["model"] == model].copy()
    if commodities_sel:
        filtered = filtered[filtered["commodity"].isin(commodities_sel)]
    if states_sel:
        filtered = filtered[filtered["State"].isin(states_sel)]
    return filtered


def _apply_table_filters(
    selected_states: list[str] | None,
    year_range: list[int],
    selected_commodities: list[str] | None,
) -> pd.DataFrame:
    states_sel = selected_states or DEFAULT_STATES
    filtered = _filter_raw(year_range, selected_commodities, states_sel)
    return filtered.sort_values(["State", "Year", "commodity"], ascending=[True, False, True])


def _metric_values(filtered: pd.DataFrame) -> tuple[float, float, float, float]:
    y_true = filtered["target_next_year_production"].to_numpy(dtype=float)
    y_pred = filtered["prediction"].to_numpy(dtype=float)
    errors = y_pred - y_true
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors**2)))
    nonzero = y_true != 0
    mape = float(np.mean(np.abs(errors[nonzero] / y_true[nonzero])) * 100) if nonzero.any() else float("nan")
    ss_res = float(np.sum(errors**2))
    ss_tot = float(np.sum((y_true - np.mean(y_true)) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot != 0 else float("nan")
    return mae, rmse, mape, r2


production_table_columns = [
    {"field": "State", "sortable": True, "filter": True},
    {"field": "Year", "sortable": True, "filter": True},
    {"field": "commodity", "headerName": "Commodity", "sortable": True, "filter": True},
    {
        "field": "total_production",
        "headerName": "Production (LB)",
        "sortable": True,
        "filter": True,
        "valueFormatter": {"function": "d3.format(',.0f')(params.value)"},
    },
]

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

app.layout = html.Div(
    id="dashboard-shell",
    className="dashboard-shell theme-light",
    children=[
        dbc.Container(
            [
                html.Header(
                    [
                        html.Div(
                            [
                                html.Div("USDA", className="brand-chip"),
                                html.H1("USDA Commodity Production", className="app-title"),
                                html.P(
                                    "Production intelligence, forward forecasts, and model validation for agricultural commodities.",
                                    className="app-subtitle",
                                ),
                            ],
                            className="app-heading",
                        ),
                        html.Div(
                            [
                                html.Div("1930-" + str(max_year), className="header-stat"),
                                html.Div("LB units", className="header-stat"),
                            ],
                            className="header-meta",
                        ),
                    ],
                    className="app-header",
                ),
                html.Div(
                    [
                        html.Aside(
                            [
                                html.Div(
                                    [
                                        html.Span("Filters", className="filter-title"),
                                        html.Span("Global", className="filter-badge"),
                                    ],
                                    className="filter-title-row",
                                ),
                                html.Div(
                                    [
                                        html.Label("Theme", className="control-label"),
                                        html.Div(
                                            ThemeSwitchAIO(aio_id="theme", themes=[url_theme1, url_theme2]),
                                            className="theme-switch-shell",
                                        ),
                                    ],
                                    className="filter-section",
                                ),
                                html.Div(
                                    [
                                        html.Label("Commodity", className="control-label"),
                                        dbc.Checklist(
                                            id="commodity-checklist",
                                            options=[{"label": c, "value": c} for c in commodities],
                                            value=DEFAULT_COMMODITIES,
                                            inline=False,
                                            className="commodity-checklist",
                                        ),
                                    ],
                                    className="filter-section",
                                ),
                                html.Div(
                                    [
                                        html.Label("Year Range", className="control-label"),
                                        dcc.RangeSlider(
                                            id="year-slider",
                                            min=min_year,
                                            max=max_year,
                                            value=[2000, max_year],
                                            marks={y: str(y) for y in range(min_year, max_year + 1, 20)},
                                            step=1,
                                            tooltip={"placement": "bottom", "always_visible": False},
                                            className="year-slider",
                                        ),
                                    ],
                                    className="filter-section",
                                ),
                                html.Div(
                                    [
                                        html.Label("State", className="control-label"),
                                        dcc.Dropdown(
                                            id="state-dropdown",
                                            options=[{"label": s.title(), "value": s} for s in states],
                                            value=DEFAULT_STATES,
                                            multi=True,
                                            placeholder="Select states",
                                            className="viz-dropdown",
                                        ),
                                    ],
                                    className="filter-section",
                                ),
                                html.Div(
                                    [
                                        html.Label("Model", className="control-label"),
                                        dcc.Dropdown(
                                            id="model-selector",
                                            options=_model_options(),
                                            value=default_model,
                                            clearable=False,
                                            disabled=not bool(available_models),
                                            className="viz-dropdown",
                                        ),
                                    ],
                                    className="filter-section",
                                ),
                                html.Div(
                                    [
                                        html.Label("Interval", className="control-label"),
                                        dcc.RadioItems(
                                            id="interval-selector",
                                            options=[
                                                {"label": "80%", "value": "80"},
                                                {"label": "95%", "value": "95"},
                                            ],
                                            value="80",
                                            inline=True,
                                            className="interval-radio",
                                        ),
                                    ],
                                    className="filter-section filter-section-last",
                                ),
                            ],
                            className="filter-rail",
                        ),
                        html.Main(
                            dbc.Tabs(
                                id="dashboard-tabs",
                                active_tab="overview-tab",
                                className="dashboard-tabs",
                                children=[
                                    dbc.Tab(
                                        label="Overview",
                                        tab_id="overview-tab",
                                        tabClassName="dashboard-tab",
                                        activeTabClassName="dashboard-tab-active",
                                        children=[
                                            html.Div(
                                                [
                                                    dbc.Row(
                                                        [
                                                            _kpi_card("Total Production", "overview-total", "overview-total-meta", "teal"),
                                                            _kpi_card("YoY Change", "overview-yoy", "overview-yoy-meta", "amber"),
                                                            _kpi_card("Top State", "overview-top-state", "overview-top-state-meta", "blue"),
                                                            _kpi_card("Forecast MAPE", "overview-accuracy", "overview-accuracy-meta", "violet"),
                                                        ],
                                                        className="g-3 mb-3",
                                                    ),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                _viz_card(
                                                                    "Production Trend",
                                                                    _graph("line-chart", 420),
                                                                    "Annual production by selected commodities",
                                                                ),
                                                                lg=8,
                                                            ),
                                                            dbc.Col(
                                                                _viz_card(
                                                                    "Top Producing States",
                                                                    _graph("bar-chart", 420),
                                                                    "Most recent selected year",
                                                                ),
                                                                lg=4,
                                                            ),
                                                        ],
                                                        className="g-3 mb-3",
                                                    ),
                                                    _viz_card(
                                                        "Filtered Production Records",
                                                        [
                                                            dcc.Download(id="download-csv"),
                                                            dag.AgGrid(
                                                                id="data-table",
                                                                className="ag-theme-quartz viz-grid",
                                                                columnDefs=production_table_columns,
                                                                defaultColDef={"resizable": True},
                                                                style={"height": "360px"},
                                                                dashGridOptions={"pagination": True, "paginationPageSize": 10},
                                                                getRowStyle={"styleConditions": COMMODITY_ROW_STYLES},
                                                            ),
                                                        ],
                                                        action=dbc.Button(
                                                            "Download CSV",
                                                            id="download-btn",
                                                            color="primary",
                                                            size="sm",
                                                            className="download-button",
                                                        ),
                                                    ),
                                                ],
                                                className="tab-panel",
                                            )
                                        ],
                                    ),
                                    dbc.Tab(
                                        label="State Trends",
                                        tab_id="state-trends-tab",
                                        tabClassName="dashboard-tab",
                                        activeTabClassName="dashboard-tab-active",
                                        children=[
                                            html.Div(
                                                [
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                _viz_card(
                                                                    "Selected State Trends",
                                                                    _graph("state-trend-chart", 430),
                                                                    "Annual production by selected states",
                                                                ),
                                                                lg=7,
                                                            ),
                                                            dbc.Col(
                                                                _viz_card(
                                                                    "Commodity Mix",
                                                                    _graph("state-mix-chart", 430),
                                                                    "Selected states in the latest year",
                                                                ),
                                                                lg=5,
                                                            ),
                                                        ],
                                                        className="g-3",
                                                    )
                                                ],
                                                className="tab-panel",
                                            )
                                        ],
                                    ),
                                    dbc.Tab(
                                        label="Forecasts",
                                        tab_id="forecasts-tab",
                                        tabClassName="dashboard-tab",
                                        activeTabClassName="dashboard-tab-active",
                                        children=[
                                            html.Div(
                                                [
                                                    dbc.Row(
                                                        [
                                                            _kpi_card("Forecast Production", "forecast-total", "forecast-total-meta", "teal"),
                                                            _kpi_card("Latest Actual", "forecast-latest", "forecast-latest-meta", "blue"),
                                                            _kpi_card("Forecast Change", "forecast-change", "forecast-change-meta", "amber"),
                                                            _kpi_card("Interval Width", "forecast-interval-width", "forecast-interval-width-meta", "violet"),
                                                        ],
                                                        className="g-3 mb-3",
                                                    ),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                _viz_card(
                                                                    "Forecast Explorer",
                                                                    _graph("forecast-chart", 430),
                                                                    "Historical actuals with forward forecast interval",
                                                                ),
                                                                lg=8,
                                                            ),
                                                            dbc.Col(
                                                                _viz_card(
                                                                    "Forecast Growth Ranking",
                                                                    _graph("forecast-ranking-chart", 430),
                                                                    "Top states by forecast production",
                                                                ),
                                                                lg=4,
                                                            ),
                                                        ],
                                                        className="g-3 mb-3",
                                                    ),
                                                    _viz_card(
                                                        "Latest Direct Forecasts",
                                                        dag.AgGrid(
                                                            id="latest-forecasts-table",
                                                            className="ag-theme-quartz viz-grid",
                                                            columnDefs=[
                                                                {"field": "State", "sortable": True, "filter": True},
                                                                {"field": "commodity", "headerName": "Commodity", "sortable": True, "filter": True},
                                                                {"field": "latest_observed_year", "headerName": "Latest Year", "sortable": True},
                                                                {"field": "forecast_year", "headerName": "Forecast Year", "sortable": True},
                                                                {
                                                                    "field": "latest_observed_production",
                                                                    "headerName": "Latest Actual",
                                                                    "sortable": True,
                                                                    "valueFormatter": {"function": "d3.format(',.0f')(params.value)"},
                                                                },
                                                                {
                                                                    "field": "forecast_production",
                                                                    "headerName": "Forecast",
                                                                    "sortable": True,
                                                                    "valueFormatter": {"function": "d3.format(',.0f')(params.value)"},
                                                                },
                                                                {
                                                                    "field": "forecast_change_pct",
                                                                    "headerName": "Change %",
                                                                    "sortable": True,
                                                                    "valueFormatter": {"function": "d3.format('+.1f')(params.value) + '%'"},
                                                                },
                                                                {
                                                                    "field": "interval_width",
                                                                    "headerName": "Interval Width",
                                                                    "sortable": True,
                                                                    "valueFormatter": {"function": "d3.format(',.0f')(params.value)"},
                                                                },
                                                            ],
                                                            defaultColDef={"resizable": True},
                                                            style={"height": "360px"},
                                                            dashGridOptions={"pagination": True, "paginationPageSize": 10},
                                                            getRowStyle={"styleConditions": COMMODITY_ROW_STYLES},
                                                        ),
                                                    ),
                                                ],
                                                className="tab-panel",
                                            )
                                        ],
                                    ),
                                    dbc.Tab(
                                        label="Model Validation",
                                        tab_id="validation-tab",
                                        tabClassName="dashboard-tab",
                                        activeTabClassName="dashboard-tab-active",
                                        children=[
                                            html.Div(
                                                [
                                                    dbc.Row(
                                                        [
                                                            _kpi_card("MAE", "metric-mae", "metric-mae-meta", "teal"),
                                                            _kpi_card("RMSE", "metric-rmse", "metric-rmse-meta", "blue"),
                                                            _kpi_card("MAPE", "metric-mape", "metric-mape-meta", "amber"),
                                                            _kpi_card("R2", "metric-r2", "metric-r2-meta", "violet"),
                                                        ],
                                                        className="g-3 mb-3",
                                                    ),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                _viz_card(
                                                                    "Actual vs Predicted",
                                                                    _graph("actual-pred-scatter", 400),
                                                                    "Backtest observations",
                                                                ),
                                                                lg=6,
                                                            ),
                                                            dbc.Col(
                                                                _viz_card(
                                                                    "Residuals Over Time",
                                                                    _graph("residual-chart", 400),
                                                                    "Actual minus predicted by target year",
                                                                ),
                                                                lg=6,
                                                            ),
                                                        ],
                                                        className="g-3 mb-3",
                                                    ),
                                                    dbc.Row(
                                                        [
                                                            dbc.Col(
                                                                _viz_card(
                                                                    "Actual vs Predicted Production",
                                                                    _graph("actual-vs-pred-chart", 410),
                                                                    "Test-period production totals",
                                                                ),
                                                                lg=7,
                                                            ),
                                                            dbc.Col(
                                                                _viz_card(
                                                                    "Largest Forecast Misses",
                                                                    dag.AgGrid(
                                                                        id="misses-table",
                                                                        className="ag-theme-quartz viz-grid",
                                                                        columnDefs=[
                                                                            {"field": "State", "sortable": True, "filter": True},
                                                                            {"field": "commodity", "headerName": "Commodity", "sortable": True, "filter": True},
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
                                                                        style={"height": "410px"},
                                                                        dashGridOptions={"pagination": True, "paginationPageSize": 10},
                                                                        getRowStyle={"styleConditions": COMMODITY_ROW_STYLES},
                                                                    ),
                                                                ),
                                                                lg=5,
                                                            ),
                                                        ],
                                                        className="g-3",
                                                    ),
                                                ],
                                                className="tab-panel",
                                            )
                                        ],
                                    ),
                                ],
                            ),
                            className="dashboard-main",
                        ),
                    ],
                    className="dashboard-grid",
                ),
            ],
            fluid=True,
            className="dashboard-container",
        )
    ],
)


# ===========================================================================
# CALLBACKS - Theme
# ===========================================================================


@callback(
    Output("dashboard-shell", "className"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_shell_theme(toggle):
    theme_class = "theme-light" if toggle else "theme-dark"
    return f"dashboard-shell {theme_class}"


# ===========================================================================
# CALLBACKS - Overview and production views
# ===========================================================================


@callback(
    Output("overview-total", "children"),
    Output("overview-total-meta", "children"),
    Output("overview-yoy", "children"),
    Output("overview-yoy-meta", "children"),
    Output("overview-top-state", "children"),
    Output("overview-top-state-meta", "children"),
    Output("overview-accuracy", "children"),
    Output("overview-accuracy-meta", "children"),
    Input("year-slider", "value"),
    Input("commodity-checklist", "value"),
    Input("model-selector", "value"),
)
def update_overview_metrics(year_range, selected_commodities, selected_model):
    filtered = _filter_raw(year_range, selected_commodities)
    if filtered.empty:
        return "-", "No production rows", "-", "No comparison year", "-", "No ranked state", "-", "No validation rows"

    total = filtered["total_production"].sum()
    latest_year = int(filtered["Year"].max())
    latest = filtered[filtered["Year"] == latest_year]
    prior = filtered[filtered["Year"] == latest_year - 1]
    current_total = latest["total_production"].sum()
    prior_total = prior["total_production"].sum()
    yoy = ((current_total - prior_total) / prior_total * 100) if prior_total else np.nan

    top_state_series = latest.groupby("State")["total_production"].sum().sort_values(ascending=False)
    top_state = top_state_series.index[0].title() if not top_state_series.empty else "-"
    top_state_value = top_state_series.iloc[0] if not top_state_series.empty else np.nan

    prediction_rows = _filter_predictions(selected_model, selected_commodities, None)
    if prediction_rows.empty:
        accuracy = "-"
        accuracy_meta = "No validation rows"
    else:
        _, _, mape, _ = _metric_values(prediction_rows)
        accuracy = f"{mape:.1f}%" if not pd.isna(mape) else "-"
        accuracy_meta = MODEL_LABELS.get(selected_model, selected_model or "Model")

    return (
        _compact_number(total),
        f"{year_range[0]}-{year_range[1]} selected years",
        _format_pct(yoy),
        f"{latest_year} vs {latest_year - 1}",
        top_state,
        f"{_compact_number(top_state_value)} LB in {latest_year}",
        accuracy,
        accuracy_meta,
    )


@callback(
    Output("line-chart", "figure"),
    Input("year-slider", "value"),
    Input("commodity-checklist", "value"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_line_chart(year_range, selected_commodities, toggle):
    filtered = (
        _filter_raw(year_range, selected_commodities)
        .groupby(["commodity", "Year"], as_index=False)["total_production"]
        .sum()
    )
    if filtered.empty:
        return _empty_figure("No production rows for the selected filters", toggle)

    fig = px.line(
        filtered,
        x="Year",
        y="total_production",
        color="commodity",
        color_discrete_map=COMMODITY_COLORS,
        labels={"Year": "Year", "total_production": "Production (LB)", "commodity": "Commodity"},
        markers=True,
    )
    fig.update_traces(marker={"size": 6}, line={"width": 2.5})
    return _polish_figure(fig, toggle, height=400)


@callback(
    Output("bar-chart", "figure"),
    Input("year-slider", "value"),
    Input("commodity-checklist", "value"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_bar_chart(year_range, selected_commodities, toggle):
    commodities_sel = selected_commodities or DEFAULT_COMMODITIES
    available = df[df["commodity"].isin(commodities_sel)]
    if available.empty:
        return _empty_figure("No production rows for the selected commodities", toggle)

    selected_year = min(int(year_range[1]), int(available["Year"].max()))
    filtered = (
        available[available["Year"] == selected_year]
        .groupby(["State", "commodity"], as_index=False)["total_production"]
        .sum()
        .dropna(subset=["total_production"])
    )
    if filtered.empty:
        return _empty_figure(f"No production rows in {selected_year}", toggle)

    top_states = filtered.groupby("State")["total_production"].sum().nlargest(10).index
    top_10 = filtered[filtered["State"].isin(top_states)].copy()
    state_order = (
        top_10.groupby("State")["total_production"]
        .sum()
        .sort_values(ascending=True)
        .index.tolist()
    )

    fig = px.bar(
        top_10,
        x="total_production",
        y="State",
        color="commodity",
        color_discrete_map=COMMODITY_COLORS,
        orientation="h",
        labels={"total_production": "Production (LB)", "State": "State", "commodity": "Commodity"},
    )
    fig.update_layout(barmode="stack", yaxis={"categoryorder": "array", "categoryarray": state_order})
    return _polish_figure(fig, toggle, height=400)


@callback(
    Output("state-trend-chart", "figure"),
    Output("state-mix-chart", "figure"),
    Input("state-dropdown", "value"),
    Input("year-slider", "value"),
    Input("commodity-checklist", "value"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_state_trends(selected_states, year_range, selected_commodities, toggle):
    states_sel = selected_states or DEFAULT_STATES
    filtered = _filter_raw(year_range, selected_commodities, states_sel)
    if filtered.empty:
        empty = _empty_figure("No production rows for selected states", toggle)
        return empty, empty

    trend = (
        filtered.groupby(["State", "commodity", "Year"], as_index=False)["total_production"]
        .sum()
        .sort_values("Year")
    )
    trend["State"] = trend["State"].str.title()
    fig_trend = px.line(
        trend,
        x="Year",
        y="total_production",
        color="State",
        line_dash="commodity",
        labels={"Year": "Year", "total_production": "Production (LB)", "State": "State", "commodity": "Commodity"},
        markers=True,
    )
    fig_trend.update_traces(marker={"size": 5}, line={"width": 2.2})

    latest_year = int(filtered["Year"].max())
    mix = (
        filtered[filtered["Year"] == latest_year]
        .groupby(["State", "commodity"], as_index=False)["total_production"]
        .sum()
    )
    mix["State"] = mix["State"].str.title()
    order = mix.groupby("State")["total_production"].sum().sort_values(ascending=True).index.tolist()
    fig_mix = px.bar(
        mix,
        x="total_production",
        y="State",
        color="commodity",
        color_discrete_map=COMMODITY_COLORS,
        orientation="h",
        labels={"total_production": "Production (LB)", "State": "State", "commodity": "Commodity"},
    )
    fig_mix.update_layout(barmode="stack", yaxis={"categoryorder": "array", "categoryarray": order})

    return _polish_figure(fig_trend, toggle, height=405), _polish_figure(fig_mix, toggle, height=405)


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
# CALLBACKS - Forecasts
# ===========================================================================


@callback(
    Output("forecast-chart", "figure"),
    Output("forecast-ranking-chart", "figure"),
    Output("forecast-total", "children"),
    Output("forecast-total-meta", "children"),
    Output("forecast-latest", "children"),
    Output("forecast-latest-meta", "children"),
    Output("forecast-change", "children"),
    Output("forecast-change-meta", "children"),
    Output("forecast-interval-width", "children"),
    Output("forecast-interval-width-meta", "children"),
    Output("latest-forecasts-table", "rowData"),
    Input("model-selector", "value"),
    Input("commodity-checklist", "value"),
    Input("state-dropdown", "value"),
    Input("year-slider", "value"),
    Input("interval-selector", "value"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_forecasts(selected_model, selected_commodities, selected_states, year_range, interval, toggle):
    lower_col = f"pi_{interval}_lower"
    upper_col = f"pi_{interval}_upper"
    empty_chart = _empty_figure("No forward forecasts for the selected filters", toggle)
    empty_return = (
        empty_chart,
        empty_chart,
        "-",
        "No forecast rows",
        "-",
        "No latest actual",
        "-",
        "No comparison",
        "-",
        f"{interval}% interval",
        [],
    )

    filtered = _filter_forecasts(selected_model, selected_commodities, selected_states)
    if filtered.empty or lower_col not in filtered or upper_col not in filtered:
        return empty_return

    filtered = filtered.copy()
    filtered["interval_width"] = filtered[upper_col] - filtered[lower_col]
    filtered["forecast_change_pct"] = np.where(
        filtered["latest_observed_production"] != 0,
        (filtered["forecast_production"] - filtered["latest_observed_production"])
        / filtered["latest_observed_production"]
        * 100,
        np.nan,
    )

    hist = _filter_raw(year_range, selected_commodities, selected_states)
    hist_agg = hist.groupby("Year", as_index=False)["total_production"].sum().sort_values("Year")

    forecast_agg = (
        filtered.groupby("forecast_year", as_index=False)
        .agg(
            forecast_production=("forecast_production", "sum"),
            lower=(lower_col, "sum"),
            upper=(upper_col, "sum"),
            latest_actual=("latest_observed_production", "sum"),
        )
        .sort_values("forecast_year")
    )

    fig_forecast = go.Figure()
    if not hist_agg.empty:
        fig_forecast.add_trace(
            go.Scatter(
                x=hist_agg["Year"],
                y=hist_agg["total_production"],
                mode="lines+markers",
                name="Actual",
                line={"color": "#0F766E", "width": 2.6},
                marker={"size": 5},
            )
        )
        last_actual_year = int(hist_agg["Year"].max())
        last_actual_value = float(hist_agg.loc[hist_agg["Year"] == last_actual_year, "total_production"].sum())
        band_x = [last_actual_year] + forecast_agg["forecast_year"].tolist()
        band_upper = [last_actual_value] + forecast_agg["upper"].tolist()
        band_lower = [last_actual_value] + forecast_agg["lower"].tolist()
        forecast_x = [last_actual_year] + forecast_agg["forecast_year"].tolist()
        forecast_y = [last_actual_value] + forecast_agg["forecast_production"].tolist()
    else:
        band_x = forecast_agg["forecast_year"].tolist()
        band_upper = forecast_agg["upper"].tolist()
        band_lower = forecast_agg["lower"].tolist()
        forecast_x = forecast_agg["forecast_year"].tolist()
        forecast_y = forecast_agg["forecast_production"].tolist()

    fig_forecast.add_trace(
        go.Scatter(
            x=band_x,
            y=band_upper,
            mode="lines",
            line={"width": 0},
            showlegend=False,
            hoverinfo="skip",
        )
    )
    fig_forecast.add_trace(
        go.Scatter(
            x=band_x,
            y=band_lower,
            mode="lines",
            fill="tonexty",
            fillcolor="rgba(15, 118, 110, 0.16)",
            line={"width": 0},
            name=f"{interval}% interval",
            hoverinfo="skip",
        )
    )
    fig_forecast.add_trace(
        go.Scatter(
            x=forecast_x,
            y=forecast_y,
            mode="lines+markers",
            name="Forecast",
            line={"color": "#D97706", "width": 2.8, "dash": "dash"},
            marker={"size": 8},
        )
    )
    fig_forecast.update_layout(xaxis_title="Year", yaxis_title="Production (LB)")
    fig_forecast = _polish_figure(fig_forecast, toggle, height=405)

    ranking = (
        filtered.groupby("State", as_index=False)
        .agg(
            forecast_production=("forecast_production", "sum"),
            latest_observed_production=("latest_observed_production", "sum"),
        )
        .assign(
            forecast_change_pct=lambda d: np.where(
                d["latest_observed_production"] != 0,
                (d["forecast_production"] - d["latest_observed_production"])
                / d["latest_observed_production"]
                * 100,
                np.nan,
            )
        )
        .sort_values("forecast_production", ascending=False)
        .head(10)
    )
    ranking["State"] = ranking["State"].str.title()
    order = ranking.sort_values("forecast_production", ascending=True)["State"].tolist()
    fig_ranking = px.bar(
        ranking,
        x="forecast_production",
        y="State",
        color="forecast_change_pct",
        orientation="h",
        color_continuous_scale=["#D97706", "#E2E8F0", "#0F766E"],
        labels={"forecast_production": "Forecast (LB)", "State": "State", "forecast_change_pct": "Change %"},
    )
    fig_ranking.update_layout(yaxis={"categoryorder": "array", "categoryarray": order}, coloraxis_colorbar={"title": "Change %"})
    fig_ranking = _polish_figure(fig_ranking, toggle, height=405)

    forecast_total = filtered["forecast_production"].sum()
    latest_total = filtered["latest_observed_production"].sum()
    forecast_change = ((forecast_total - latest_total) / latest_total * 100) if latest_total else np.nan
    interval_width = filtered["interval_width"].sum()
    forecast_years = sorted(filtered["forecast_year"].unique().tolist())
    latest_years = sorted(filtered["latest_observed_year"].unique().tolist())

    table_rows = (
        filtered[
            [
                "State",
                "commodity",
                "latest_observed_year",
                "forecast_year",
                "latest_observed_production",
                "forecast_production",
                "forecast_change_pct",
                "interval_width",
            ]
        ]
        .sort_values("forecast_production", ascending=False)
        .round({"latest_observed_production": 0, "forecast_production": 0, "forecast_change_pct": 1, "interval_width": 0})
        .to_dict("records")
    )

    return (
        fig_forecast,
        fig_ranking,
        _compact_number(forecast_total),
        f"{MODEL_LABELS.get(selected_model, selected_model)} forecast year {min(forecast_years)}-{max(forecast_years)}",
        _compact_number(latest_total),
        f"Latest observed year {min(latest_years)}-{max(latest_years)}",
        _format_pct(forecast_change),
        "Forecast vs latest actual",
        _compact_number(interval_width),
        f"Total {interval}% interval spread",
        table_rows,
    )


# ===========================================================================
# CALLBACKS - Model Validation
# ===========================================================================


@callback(
    Output("actual-vs-pred-chart", "figure"),
    Output("actual-pred-scatter", "figure"),
    Output("residual-chart", "figure"),
    Output("metric-mae", "children"),
    Output("metric-mae-meta", "children"),
    Output("metric-rmse", "children"),
    Output("metric-rmse-meta", "children"),
    Output("metric-mape", "children"),
    Output("metric-mape-meta", "children"),
    Output("metric-r2", "children"),
    Output("metric-r2-meta", "children"),
    Output("misses-table", "rowData"),
    Input("model-selector", "value"),
    Input("commodity-checklist", "value"),
    Input("state-dropdown", "value"),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
)
def update_model_validation(selected_model, selected_commodities, selected_states, toggle):
    empty = _empty_figure("No model predictions available", toggle)
    no_data = (empty, empty, empty, "-", "No rows", "-", "No rows", "-", "No rows", "-", "No rows", [])

    filtered = _filter_predictions(selected_model, selected_commodities, selected_states)
    if filtered.empty:
        return no_data

    agg = (
        filtered.groupby(["commodity", "target_year"], as_index=False)
        .agg(actual=("target_next_year_production", "sum"), predicted=("prediction", "sum"))
        .sort_values("target_year")
    )
    long = pd.melt(
        agg,
        id_vars=["commodity", "target_year"],
        value_vars=["actual", "predicted"],
        var_name="series",
        value_name="production",
    )
    long["series"] = long["series"].str.title()

    fig_line = px.line(
        long,
        x="target_year",
        y="production",
        color="commodity",
        line_dash="series",
        color_discrete_map=COMMODITY_COLORS,
        labels={"target_year": "Forecast Year", "production": "Production (LB)", "commodity": "Commodity", "series": "Series"},
        markers=True,
    )
    fig_line.update_traces(marker={"size": 6}, line={"width": 2.4})
    fig_line = _polish_figure(fig_line, toggle, height=390)

    scatter = filtered.copy()
    scatter["State"] = scatter["State"].str.title()
    fig_scatter = px.scatter(
        scatter,
        x="target_next_year_production",
        y="prediction",
        color="commodity",
        color_discrete_map=COMMODITY_COLORS,
        hover_data=["State", "target_year"],
        labels={
            "target_next_year_production": "Actual (LB)",
            "prediction": "Predicted (LB)",
            "commodity": "Commodity",
        },
    )
    max_axis = float(max(scatter["target_next_year_production"].max(), scatter["prediction"].max()))
    fig_scatter.add_trace(
        go.Scatter(
            x=[0, max_axis],
            y=[0, max_axis],
            mode="lines",
            name="Perfect fit",
            line={"color": "#94A3B8", "dash": "dot"},
        )
    )
    fig_scatter.update_traces(marker={"size": 8, "opacity": 0.78}, selector={"mode": "markers"})
    fig_scatter = _polish_figure(fig_scatter, toggle, height=380)

    residuals = filtered.copy()
    residuals["residual"] = residuals["target_next_year_production"] - residuals["prediction"]
    residuals = (
        residuals.groupby(["target_year", "commodity"], as_index=False)["residual"]
        .sum()
        .sort_values("target_year")
    )
    fig_residual = px.bar(
        residuals,
        x="target_year",
        y="residual",
        color="commodity",
        color_discrete_map=COMMODITY_COLORS,
        barmode="group",
        labels={"target_year": "Forecast Year", "residual": "Actual - Predicted (LB)", "commodity": "Commodity"},
    )
    fig_residual.add_hline(y=0, line_dash="dot", line_color="#94A3B8")
    fig_residual = _polish_figure(fig_residual, toggle, height=380)

    mae, rmse, mape, r2 = _metric_values(filtered)
    row_count = f"{len(filtered):,} validation rows"
    model_label = MODEL_LABELS.get(selected_model, selected_model or "Model")

    misses = (
        filtered[["State", "commodity", "target_year", "target_next_year_production", "prediction", "abs_error"]]
        .sort_values("abs_error", ascending=False)
        .head(20)
        .round(0)
        .to_dict("records")
    )

    return (
        fig_line,
        fig_scatter,
        fig_residual,
        _compact_number(mae),
        row_count,
        _compact_number(rmse),
        model_label,
        f"{mape:.1f}%" if not pd.isna(mape) else "-",
        "Lower is better",
        f"{r2:.3f}" if not pd.isna(r2) else "-",
        "Closer to 1 is better",
        misses,
    )


if __name__ == "__main__":
    app.run(debug=True, port=1234)
