import streamlit as st
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import plotly.express as px
import plotly.graph_objects as go

PAGE_TITLE = "GLedger - Carbon Accountability"
PAGE_ICON = "🌱"
LAYOUT = "wide"

REFRESH_INTERVAL = 5

PLANT_COLORS = {
    "Plant_A": "#2E86AB",
    "Plant_B": "#A23B72",
    "Plant_C": "#F18F01",
    "Plant_D": "#C73E1D",
}

class DashboardData:
    """Manages data for the dashboard"""
    
    def __init__(self, max_points: int = 100):
        self.max_points = max_points
        self.data: List[Dict] = []
        self.violations: List[Dict] = []
        self.alerts: List[Dict] = []
    
    def add_reading(self, reading: Dict):
        """Add a new reading"""
        self.data.append(reading)
        
        # Keep only recent data
        if len(self.data) > self.max_points:
            self.data = self.data[-self.max_points:]
    
    def add_violation(self, violation: Dict):
        """Add a violation"""
        self.violations.append(violation)
        
        # Keep only recent violations
        if len(self.violations) > 50:
            self.violations = self.violations[-50:]
    
    def get_dataframe(self) -> pd.DataFrame:
        """Get data as DataFrame"""
        if not self.data:
            return pd.DataFrame()
        return pd.DataFrame(self.data)
    
    def get_current_values(self) -> Dict[str, Any]:
        """Get current values for each plant"""
        df = self.get_dataframe()
        if df.empty:
            return {}
        
        current = {}
        for plant in df["plant_id"].unique():
            plant_data = df[df["plant_id"] == plant].tail(10)
            if not plant_data.empty:
                current[plant] = {
                    "carbon_kg": plant_data["carbon_kg"].sum(),
                    "energy_kwh": plant_data["energy_kwh"].sum(),
                    "fuel_liters": plant_data["fuel_liters"].sum(),
                    "production_units": plant_data["production_units"].sum(),
                    "efficiency": (
                        plant_data["carbon_kg"].sum() / plant_data["production_units"].sum()
                        if plant_data["production_units"].sum() > 0
                        else 0
                    ),
                    "timestamp": plant_data["timestamp"].max()
                }
        
        return current
    
    def get_summary(self) -> Dict[str, Any]:
        """Get overall summary"""
        df = self.get_dataframe()
        if df.empty:
            return {
                "total_carbon": 0,
                "total_production": 0,
                "avg_efficiency": 0,
                "plant_count": 0,
                "violation_count": 0
            }
        
        return {
            "total_carbon": df["carbon_kg"].sum(),
            "total_production": df["production_units"].sum(),
            "avg_efficiency": (
                df["carbon_kg"].sum() / df["production_units"].sum()
                if df["production_units"].sum() > 0
                else 0
            ),
            "plant_count": df["plant_id"].nunique(),
            "violation_count": len(self.violations),
            "last_update": df["timestamp"].max() if "timestamp" in df.columns else None
        }


# Initialize data store
data_store = DashboardData()

def init_page():
    """Initialize the Streamlit page"""
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout=LAYOUT
    )
    
   
    st.markdown("""
    <style>
    .main {
        background-color: #0e1117
    }
    .stMetric {
        background-color: #262730;
        padding: 10px;
        border-radius: 5px;
    }
    .violation-alert {
        background-color: #ff4b4b;
        color: white;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .success-alert {
        background-color: #4caf50;
        color: white;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    </style>
    """, unsafe_allow_html=True)


def sidebar():
    """Create sidebar controls"""
    st.sidebar.title("🌱 GLedger")
    st.sidebar.markdown("---")
    
    # Refresh control
    auto_refresh = st.sidebar.checkbox("Auto-refresh", value=True)
    refresh_rate = st.sidebar.slider("Refresh rate (seconds)", 1, 30, REFRESH_INTERVAL)

    all_plants = ["Plant_A", "Plant_B", "Plant_C", "Plant_D"]
    selected_plants = st.sidebar.multiselect(
        "Select Plants",
        all_plants,
        default=all_plants
    )

    time_range = st.sidebar.select_slider(
        "Time Range",
        options=["Last 5 min", "Last 15 min", "Last 30 min", "Last hour", "All time"],
        value="Last 15 min"
    )
    

    theme = st.sidebar.radio("Theme", ["Dark", "Light"])
    
    return {
        "auto_refresh": auto_refresh,
        "refresh_rate": refresh_rate,
        "selected_plants": selected_plants,
        "time_range": time_range,
        "theme": theme
    }


def metrics_row(summary: Dict[str, Any]):
    """Display metrics row"""
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "Total Carbon",
            f"{summary.get('total_carbon', 0):,.0f} kg",
            delta=None
        )
    
    with col2:
        st.metric(
            "Total Production",
            f"{summary.get('total_production', 0):,}",
            delta=None
        )
    
    with col3:
        efficiency = summary.get('avg_efficiency', 0)
        delta_color = "normal" if efficiency < 15 else "inverse"
        st.metric(
            "Avg Efficiency",
            f"{efficiency:.1f} kg/unit",
            delta=None,
            delta_color=delta_color
        )
    
    with col4:
        st.metric(
            "Active Plants",
            summary.get('plant_count', 0),
            delta=None
        )
    
    with col5:
        violations = summary.get('violation_count', 0)
        delta_color = "inverse" if violations > 0 else "normal"
        st.metric(
            "Violations",
            violations,
            delta=None,
            delta_color=delta_color
        )


def carbon_chart(df: pd.DataFrame, plants: List[str]):
    """Display carbon emissions chart"""
    st.subheader("📊 Carbon Emissions Over Time")
    
    if df.empty:
        st.info("No data available")
        return
    
    # Filter by selected plants
    df = df[df["plant_id"].isin(plants)] if plants else df
    
    if df.empty:
        st.info("No data for selected plants")
        return
    
    # Create line chart
    fig = px.line(
        df,
        x="timestamp",
        y="carbon_kg",
        color="plant_id",
        color_discrete_map=PLANT_COLORS,
        title="Carbon Emissions (kg CO2)",
        labels={"carbon_kg": "Carbon (kg)", "timestamp": "Time"}
    )
    
    fig.update_layout(
        xaxis_title="Time",
        yaxis_title="Carbon Emissions (kg CO2)",
        legend_title="Plant",
        template="plotly_dark" if True else "plotly_white"
    )
    
    st.plotly_chart(fig, use_container_width=True)


def efficiency_chart(df: pd.DataFrame, plants: List[str]):
    """Display efficiency chart"""
    st.subheader("⚡ Production Efficiency")
    
    if df.empty:
        st.info("No data available")
        return
    
    # Filter by selected plants
    df = df[df["plant_id"].isin(plants)] if plants else df
    
    if df.empty:
        st.info("No data for selected plants")
        return
    
    # Calculate efficiency per reading
    df = df.copy()
    df["efficiency"] = df["carbon_kg"] / df["production_units"]
    
    # Create bar chart
    fig = px.bar(
        df.groupby("plant_id")["efficiency"].mean().reset_index(),
        x="plant_id",
        y="efficiency",
        color="plant_id",
        color_discrete_map=PLANT_COLORS,
        title="Average Efficiency (kg CO2 per production unit)",
        labels={"efficiency": "Efficiency (kg/unit)", "plant_id": "Plant"}
    )
    
    # Add threshold line
    fig.add_hline(y=15, line_dash="dash", line_color="orange", 
                  annotation_text="Warning Threshold")
    fig.add_hline(y=20, line_dash="dash", line_color="red",
                  annotation_text="Critical Threshold")
    
    fig.update_layout(
        yaxis_title="Efficiency (kg CO2/unit)",
        template="plotly_dark"
    )
    
    st.plotly_chart(fig, use_container_width=True)


def plant_comparison(current_values: Dict):
    """Display plant comparison"""
    st.subheader("🏭 Plant Comparison")
    
    if not current_values:
        st.info("No current values available")
        return
    
    # Create comparison data
    comparison_data = []
    for plant, values in current_values.items():
        comparison_data.append({
            "Plant": plant,
            "Carbon (kg)": values["carbon_kg"],
            "Energy (kWh)": values["energy_kwh"],
            "Fuel (L)": values["fuel_liters"],
            "Production": values["production_units"],
            "Efficiency": values["efficiency"]
        })
    
    df = pd.DataFrame(comparison_data)
    
    # Display as table with formatting
    st.dataframe(
        df.style.format({
            "Carbon (kg)": "{:.1f}",
            "Energy (kWh)": "{:.1f}",
            "Fuel (L)": "{:.1f}",
            "Production": "{:.0f}",
            "Efficiency": "{:.2f}"
        }).background_gradient(
            subset=["Efficiency"],
            cmap="RdYlGn_r"  # Red for high (bad), green for low (good)
        ),
        use_container_width=True
    )


def alert_list(violations: List[Dict]):
    """Display alert list"""
    st.subheader("🚨 Recent Alerts")
    
    if not violations:
        st.success("No violations detected!")
        return
    
    # Show last 10 violations
    recent = violations[-10:]
    
    for alert in reversed(recent):
        plant = alert.get("plant_id", "Unknown")
        violation_type = alert.get("violation_type", "Unknown")
        message = alert.get("message", "")
        timestamp = alert.get("timestamp", alert.get("window_end", ""))
        
        st.error(f"**{plant}** - {violation_type}: {message}")
        st.caption(f"Time: {timestamp}")


def leaderboard(current_values: Dict):
    """Display efficiency leaderboard"""
    st.subheader("🏆 Efficiency Leaderboard")
    
    if not current_values:
        st.info("No data available")
        return
    
    # Create leaderboard data
    leaderboard_data = []
    for plant, values in current_values.items():
        efficiency = values["efficiency"]
        
        # Determine rating
        if efficiency < 10:
            rating = "🟢 Excellent"
        elif efficiency < 15:
            rating = "🟡 Good"
        elif efficiency < 20:
            rating = "🟠 Warning"
        else:
            rating = "🔴 Critical"
        
        leaderboard_data.append({
            "Plant": plant,
            "Efficiency (kg/unit)": efficiency,
            "Rating": rating,
            "Status": "✅ Compliant" if efficiency < 15 else "⚠️ Non-compliant"
        })
    
    # Sort by efficiency
    leaderboard_data.sort(key=lambda x: x["Efficiency (kg/unit)"])
    
    # Display
    df = pd.DataFrame(leaderboard_data)
    
    for i, row in df.iterrows():
        col1, col2, col3 = st.columns([1, 2, 2])
        
        with col1:
            if i == 0:
                st.markdown(f"🥇 **{row['Plant']}**")
            elif i == 1:
                st.markdown(f"🥈 **{row['Plant']}**")
            elif i == 2:
                st.markdown(f"🥉 **{row['Plant']}**")
            else:
                st.markdown(f"**{row['Plant']}**")
        
        with col2:
            st.write(f"{row['Efficiency (kg/unit)']:.2f} kg CO2/unit")
        
        with col3:
            st.write(row["Rating"])
        
        st.markdown("---")


def main():
    """Main dashboard function"""
    init_page()
    
    # Get sidebar controls
    controls = sidebar()
    
    # Main title
    st.title(f"{PAGE_ICON} GLedger - Carbon Accountability")
    st.markdown("Real-time carbon compliance monitoring for industrial facilities")
    st.markdown("---")
    
    # Check for demo mode (no live data)
    demo_mode = st.checkbox("Demo Mode (generate sample data)", value=True)
    
    if demo_mode:
        # Generate sample data
        plants = ["Plant_A", "Plant_B", "Plant_C", "Plant_D"]
        
        # Create sample data
        np.random.seed(42)
        sample_data = []
        
        for i in range(50):
            timestamp = datetime.now() - timedelta(minutes=50-i)
            for plant in plants:
                base_carbon = {"Plant_A": 100, "Plant_B": 150, "Plant_C": 80, "Plant_D": 200}[plant]
                carbon = base_carbon * np.random.uniform(0.8, 1.2)
                
                if np.random.random() < 0.05:  # 5% spike
                    carbon *= 2.5
                
                sample_data.append({
                    "plant_id": plant,
                    "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                    "energy_kwh": carbon * 0.82 / 2.31,
                    "fuel_liters": carbon / 2.31,
                    "production_units": int(carbon / 12),
                    "carbon_kg": carbon
                })
        
        # Convert to DataFrame
        df = pd.DataFrame(sample_data)
        
        # Generate sample violations
        violations = []
        for plant in plants[:2]:  # 2 plants with violations
            violations.append({
                "plant_id": plant,
                "violation_type": "THRESHOLD_EXCEEDED",
                "message": f"Emission {np.random.uniform(500, 800):.0f}kg exceeds threshold 500kg",
                "timestamp": datetime.now().isoformat()
            })
        
        current = {}
        for plant in plants:
            plant_df = df[df["plant_id"] == plant]
            current[plant] = {
                "carbon_kg": plant_df["carbon_kg"].sum(),
                "energy_kwh": plant_df["energy_kwh"].sum(),
                "fuel_liters": plant_df["fuel_liters"].sum(),
                "production_units": plant_df["production_units"].sum(),
                "efficiency": plant_df["carbon_kg"].sum() / plant_df["production_units"].sum() if plant_df["production_units"].sum() > 0 else 0,
                "timestamp": plant_df["timestamp"].max()
            }
        
        summary = {
            "total_carbon": df["carbon_kg"].sum(),
            "total_production": df["production_units"].sum(),
            "avg_efficiency": df["carbon_kg"].sum() / df["production_units"].sum() if df["production_units"].sum() > 0 else 0,
            "plant_count": df["plant_id"].nunique(),
            "violation_count": len(violations)
        }
    else:
        # Use real data from data store
        df = data_store.get_dataframe()
        current = data_store.get_current_values()
        violations = data_store.violations
        summary = data_store.get_summary()
    
    # Display metrics
    metrics_row(summary)
    st.markdown("---")
    
    # Display charts
    col1, col2 = st.columns(2)
    
    with col1:
        carbon_chart(df, controls["selected_plants"])
    
    with col2:
        efficiency_chart(df, controls["selected_plants"])
    
    st.markdown("---")
    
    # Display additional info
    col1, col2 = st.columns(2)
    
    with col1:
        plant_comparison(current)
    
    with col2:
        leaderboard(current)
    
    st.markdown("---")
    
    # Display alerts
    alert_list(violations)
    
    # Auto-refresh
    if controls["auto_refresh"]:
        time.sleep(controls["refresh_rate"])
        st.rerun()


if __name__ == "__main__":
    main()
