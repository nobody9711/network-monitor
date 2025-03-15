"""
Network Monitor Dashboard - Web interface for network monitoring and management
"""

import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from flask import Flask
import plotly.graph_objs as go
from datetime import datetime, timedelta
import humanize
import logging

from src.database.influx import InfluxDBStorage
from src.database.mongo import MongoDBStorage
from src.security.analyzer import SecurityAnalyzer
from src.security.alerts import AlertManager

logger = logging.getLogger(__name__)

# Initialize Flask server
server = Flask(__name__)

# Initialize Dash app with Bootstrap theme
app = dash.Dash(
    __name__,
    server=server,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True
)

# Dashboard layout components
def create_header():
    """Create the dashboard header."""
    return dbc.Navbar(
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H3("Network Monitor", className="text-light mb-0"),
                    html.P("Raspberry Pi Network Monitoring Dashboard", className="text-muted mb-0")
                ]),
                dbc.Col([
                    dbc.Button("Refresh", id="refresh-data", color="primary", className="mr-2"),
                    dbc.Button("Settings", id="open-settings", color="secondary")
                ], width="auto", className="d-flex align-items-center")
            ], align="center")
        ], fluid=True),
        dark=True,
        color="dark",
        className="mb-4"
    )

def create_overview_cards():
    """Create overview statistics cards."""
    return dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H5("Active Devices", className="card-title text-primary"),
                html.H3(id="active-devices-count", children="0"),
                html.P(id="active-devices-change", children="0% change", className="text-muted")
            ])
        ]), width=3),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H5("Current Bandwidth", className="card-title text-success"),
                html.H3(id="current-bandwidth", children="0 Mbps"),
                html.P(id="bandwidth-change", children="0% change", className="text-muted")
            ])
        ]), width=3),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H5("DNS Queries", className="card-title text-info"),
                html.H3(id="dns-queries-count", children="0"),
                html.P(id="dns-queries-change", children="0% change", className="text-muted")
            ])
        ]), width=3),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H5("Security Alerts", className="card-title text-warning"),
                html.H3(id="security-alerts-count", children="0"),
                html.P(id="alerts-change", children="0% change", className="text-muted")
            ])
        ]), width=3)
    ], className="mb-4")

def create_bandwidth_graph():
    """Create the bandwidth usage graph."""
    return dbc.Card([
        dbc.CardHeader([
            html.H5("Network Bandwidth", className="mb-0"),
            dbc.ButtonGroup([
                dbc.Button("1H", id="bandwidth-1h", size="sm", color="primary", outline=True),
                dbc.Button("6H", id="bandwidth-6h", size="sm", color="primary", outline=True),
                dbc.Button("24H", id="bandwidth-24h", size="sm", color="primary", outline=True, active=True)
            ], size="sm")
        ], className="d-flex justify-content-between align-items-center"),
        dbc.CardBody([
            dcc.Graph(
                id="bandwidth-graph",
                config={"displayModeBar": False}
            )
        ])
    ], className="mb-4")

def create_device_table():
    """Create the active devices table."""
    return dbc.Card([
        dbc.CardHeader([
            html.H5("Active Devices", className="mb-0"),
            dbc.Input(
                type="text",
                id="device-search",
                placeholder="Search devices...",
                className="w-25"
            )
        ], className="d-flex justify-content-between align-items-center"),
        dbc.CardBody([
            html.Div(id="device-table")
        ])
    ], className="mb-4")

def create_alerts_timeline():
    """Create the security alerts timeline."""
    return dbc.Card([
        dbc.CardHeader([
            html.H5("Security Alerts", className="mb-0"),
            dbc.Select(
                id="alert-severity",
                options=[
                    {"label": "All Severities", "value": "all"},
                    {"label": "High", "value": "high"},
                    {"label": "Medium", "value": "medium"},
                    {"label": "Low", "value": "low"}
                ],
                value="all",
                className="w-25"
            )
        ], className="d-flex justify-content-between align-items-center"),
        dbc.CardBody([
            html.Div(id="alerts-timeline")
        ])
    ])

# Main dashboard layout
app.layout = dbc.Container([
    create_header(),
    create_overview_cards(),
    dbc.Row([
        dbc.Col([
            create_bandwidth_graph()
        ], width=8),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("System Status"),
                dbc.CardBody([
                    html.Div(id="system-status")
                ])
            ])
        ], width=4)
    ], className="mb-4"),
    dbc.Row([
        dbc.Col([
            create_device_table()
        ], width=8),
        dbc.Col([
            create_alerts_timeline()
        ], width=4)
    ])
], fluid=True)

# Callback functions
@app.callback(
    [
        Output("active-devices-count", "children"),
        Output("current-bandwidth", "children"),
        Output("dns-queries-count", "children"),
        Output("security-alerts-count", "children")
    ],
    Input("refresh-data", "n_clicks"),
    prevent_initial_call=False
)
def update_overview_stats(n_clicks):
    """Update the overview statistics cards."""
    try:
        # Get active devices count
        active_devices = len(mongo_db.get_active_devices(hours=1))
        
        # Get current bandwidth
        bandwidth_data = influx_db.get_current_bandwidth()
        current_bandwidth = f"{bandwidth_data.get('total_mbps', 0):.1f} Mbps"
        
        # Get DNS queries
        pihole_stats = influx_db.get_pihole_summary()
        dns_queries = pihole_stats.get("dns_queries_today", 0)
        
        # Get security alerts count
        alerts = alert_manager.get_recent_alerts(hours=24)
        alert_count = len(alerts)
        
        return active_devices, current_bandwidth, dns_queries, alert_count
    except Exception as e:
        logger.error(f"Error updating overview stats: {e}")
        return "Error", "Error", "Error", "Error"

@app.callback(
    Output("bandwidth-graph", "figure"),
    [
        Input("bandwidth-1h", "n_clicks"),
        Input("bandwidth-6h", "n_clicks"),
        Input("bandwidth-24h", "n_clicks")
    ],
    prevent_initial_call=False
)
def update_bandwidth_graph(*args):
    """Update the bandwidth usage graph."""
    ctx = dash.callback_context
    if not ctx.triggered:
        timeframe = 24  # Default to 24 hours
    else:
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        timeframe = int(button_id.split("-")[1][:-1])  # Extract hours from button ID
    
    try:
        # Get bandwidth data from InfluxDB
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=timeframe)
        bandwidth_data = influx_db.get_bandwidth_metrics(
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat()
        )
        
        # Prepare data for plotting
        timestamps = []
        download = []
        upload = []
        
        for point in bandwidth_data:
            timestamps.append(point["timestamp"])
            download.append(point.get("download_mbps", 0))
            upload.append(point.get("upload_mbps", 0))
        
        # Create the figure
        figure = {
            "data": [
                go.Scatter(
                    x=timestamps,
                    y=download,
                    name="Download",
                    line={"color": "#2ecc71"}
                ),
                go.Scatter(
                    x=timestamps,
                    y=upload,
                    name="Upload",
                    line={"color": "#e74c3c"}
                )
            ],
            "layout": go.Layout(
                margin={"l": 40, "r": 20, "t": 20, "b": 30},
                showlegend=True,
                legend={"orientation": "h"},
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis={
                    "showgrid": False,
                    "zeroline": False
                },
                yaxis={
                    "showgrid": True,
                    "gridcolor": "rgba(255,255,255,0.1)",
                    "zeroline": False,
                    "title": "Mbps"
                }
            )
        }
        
        return figure
    except Exception as e:
        logger.error(f"Error updating bandwidth graph: {e}")
        return {}

@app.callback(
    Output("device-table", "children"),
    [Input("device-search", "value")],
    prevent_initial_call=False
)
def update_device_table(search_term):
    """Update the active devices table."""
    try:
        # Get active devices
        devices = mongo_db.get_active_devices(hours=1)
        
        # Filter devices if search term is provided
        if search_term:
            search_term = search_term.lower()
            devices = [
                d for d in devices
                if search_term in d.get("hostname", "").lower() or
                search_term in d.get("ip", "").lower() or
                search_term in d.get("mac", "").lower()
            ]
        
        # Create table
        table = dbc.Table([
            html.Thead([
                html.Tr([
                    html.Th("Hostname"),
                    html.Th("IP Address"),
                    html.Th("MAC Address"),
                    html.Th("Last Seen"),
                    html.Th("Status")
                ])
            ]),
            html.Tbody([
                html.Tr([
                    html.Td(device.get("hostname", "Unknown")),
                    html.Td(device["ip"]),
                    html.Td(device["mac"]),
                    html.Td(humanize.naturaltime(
                        datetime.now() - datetime.fromisoformat(device["last_seen"])
                    )),
                    html.Td(html.Span(
                        "Active",
                        className="badge bg-success" if device.get("active", False) else "badge bg-secondary"
                    ))
                ]) for device in devices
            ])
        ], bordered=True, hover=True, responsive=True, className="mb-0")
        
        return table
    except Exception as e:
        logger.error(f"Error updating device table: {e}")
        return html.Div("Error loading device data", className="text-danger")

@app.callback(
    Output("alerts-timeline", "children"),
    [Input("alert-severity", "value")],
    prevent_initial_call=False
)
def update_alerts_timeline(severity):
    """Update the security alerts timeline."""
    try:
        # Get recent alerts
        alerts = alert_manager.get_recent_alerts(hours=24)
        
        # Filter by severity if not "all"
        if severity != "all":
            alerts = [a for a in alerts if a["severity"] == severity]
        
        # Create timeline items
        timeline_items = []
        for alert in alerts:
            severity_color = {
                "high": "danger",
                "medium": "warning",
                "low": "info"
            }.get(alert["severity"], "secondary")
            
            timeline_items.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Small(
                            humanize.naturaltime(
                                datetime.now() - datetime.fromisoformat(alert["timestamp"])
                            ),
                            className="text-muted"
                        ),
                        html.Span(
                            alert["severity"].title(),
                            className=f"badge bg-{severity_color} float-end"
                        )
                    ]),
                    html.P(alert["details"]["message"], className="mb-0 mt-1")
                ])
            )
        
        return dbc.ListGroup(timeline_items) if timeline_items else html.P("No alerts found")
    except Exception as e:
        logger.error(f"Error updating alerts timeline: {e}")
        return html.Div("Error loading alerts", className="text-danger")

@app.callback(
    Output("system-status", "children"),
    Input("refresh-data", "n_clicks"),
    prevent_initial_call=False
)
def update_system_status(n_clicks):
    """Update the system status information."""
    try:
        # Get system performance metrics
        performance = influx_db.get_recent_performance(minutes=5)
        
        if not performance or "error" in performance:
            return html.Div("Error loading system status", className="text-danger")
        
        # Create status indicators
        status_items = [
            dbc.Row([
                dbc.Col(html.Strong("CPU Usage:"), width=4),
                dbc.Col([
                    html.Span(f"{performance.get('cpu_percent', 0):.1f}%"),
                    dbc.Progress(
                        value=performance.get('cpu_percent', 0),
                        color="success" if performance.get('cpu_percent', 0) < 80 else "warning",
                        className="mt-1"
                    )
                ], width=8)
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(html.Strong("Memory Usage:"), width=4),
                dbc.Col([
                    html.Span(f"{performance.get('memory_percent', 0):.1f}%"),
                    dbc.Progress(
                        value=performance.get('memory_percent', 0),
                        color="success" if performance.get('memory_percent', 0) < 80 else "warning",
                        className="mt-1"
                    )
                ], width=8)
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(html.Strong("Disk Usage:"), width=4),
                dbc.Col([
                    html.Span(f"{performance.get('disk_percent', 0):.1f}%"),
                    dbc.Progress(
                        value=performance.get('disk_percent', 0),
                        color="success" if performance.get('disk_percent', 0) < 80 else "warning",
                        className="mt-1"
                    )
                ], width=8)
            ], className="mb-3"),
            dbc.Row([
                dbc.Col(html.Strong("Temperature:"), width=4),
                dbc.Col([
                    html.Span(f"{performance.get('temperature', 0):.1f}°C"),
                    dbc.Progress(
                        value=min(100, (performance.get('temperature', 0) / 80) * 100),
                        color="success" if performance.get('temperature', 0) < 60 else "warning",
                        className="mt-1"
                    )
                ], width=8)
            ])
        ]
        
        return html.Div(status_items)
    except Exception as e:
        logger.error(f"Error updating system status: {e}")
        return html.Div("Error loading system status", className="text-danger")

def start_dashboard(mongo_db_instance: MongoDBStorage,
                   influx_db_instance: InfluxDBStorage,
                   alert_manager_instance: AlertManager,
                   host: str = "0.0.0.0",
                   port: int = 8050,
                   debug: bool = False) -> None:
    """
    Start the dashboard web application.
    
    Args:
        mongo_db_instance: MongoDB storage instance
        influx_db_instance: InfluxDB storage instance
        alert_manager_instance: Alert manager instance
        host: Host to run the dashboard on
        port: Port to run the dashboard on
        debug: Whether to run in debug mode
    """
    global mongo_db, influx_db, alert_manager
    mongo_db = mongo_db_instance
    influx_db = influx_db_instance
    alert_manager = alert_manager_instance
    
    logger.info(f"Starting dashboard on {host}:{port}")
    app.run_server(host=host, port=port, debug=debug) 