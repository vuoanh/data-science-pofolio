# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a data science portfolio project analyzing USDA agricultural production data. The project demonstrates SQL analysis skills using SQLite and Python dashboard development with Plotly Dash.

## Repository Structure

- **SQL/** - SQLite-based analysis of USDA agricultural commodities (milk, cheese, coffee, honey, yogurt)
- **dashboard/** - Jupyter notebook tutorial demonstrating Plotly Dash interactive dashboards

## Working with the SQL Project

### Database

The SQLite database `project-USDA.sqlite` contains production data tables and a state lookup table. Tables use State_ANSI codes that join to `state_lookup` for state names.

### Running Queries

```bash
sqlite3 project-USDA.sqlite < load_and_examine_USDA_data.sql
```

Or interactively:
```bash
sqlite3 project-USDA.sqlite
.read load_and_examine_USDA_data.sql
```

### Data Schema Pattern

Production tables follow this structure:
- Year, Period (e.g., APR), State_ANSI, Value

Note: Some Value fields contain commas in numeric strings that need cleaning with `REPLACE(Value, ',', '')`.

## Working with the Dashboard

The Dash tutorial notebook requires:
- dash
- plotly
- pandas
- dash-ag-grid
- dash-bootstrap-components

Run with Jupyter:
```bash
jupyter notebook dashboard/dash_tutorial.ipynb
```
