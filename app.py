import streamlit as st
import pandapower as pp
import numpy as np
import networkx as nx
import math
from core.osm_client import fetch_osm_data
from core.data_processor import process_osm_data, process_geojson_data
from core.grid_manager import build_network
from core.power_flow import get_energized_status
from core.visualizer import create_plotly_map
from core.geojson_loader import (
    load_geojson_features, 
    get_available_regions,
    get_region_center,
    GEOJSON_PATH
)
import os

# --- CONFIG ---
st.set_page_config(page_title="Smart Grid Simulator", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        font-weight: bold;
    }
    .stButton>button:hover {
        border-color: #00ADB5;
        color: #00ADB5;
    }
    h1, h2, h3 {
        color: #00ADB5 !important;
    }
    .metric-card {
        background-color: #161B22;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363D;
        text-align: center;
    }
    .data-source-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #00ADB5;
        margin-bottom: 10px;
    }
    .success-banner {
        background: linear-gradient(90deg, #00E676 0%, #00C853 100%);
        color: black;
        padding: 10px 15px;
        border-radius: 8px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# --- MAIN APP LOGIC ---

st.title("⚡ Interactive Smart Grid Simulator")

# Session State Initialization
if 'net' not in st.session_state:
    st.session_state['net'] = None
if 'sensors' not in st.session_state:
    st.session_state['sensors'] = []
if 'energized' not in st.session_state:
    st.session_state['energized'] = False
if 'fault_line' not in st.session_state:
    st.session_state['fault_line'] = None
if 'data_source' not in st.session_state:
    st.session_state['data_source'] = None

# --- SIDEBAR: DATA SOURCE SELECTION ---
st.sidebar.header("1. Data Source")

# Check if GeoJSON file exists
geojson_available = os.path.exists(GEOJSON_PATH)

data_source_tab = st.sidebar.radio(
    "Choose Data Source:",
    ["🇮🇳 India Transmission Grid", "🌐 OSM (Custom Area)"],
    index=0 if geojson_available else 1
)

if data_source_tab == "🇮🇳 India Transmission Grid":
    st.sidebar.markdown("---")
    
    if not geojson_available:
        st.sidebar.error("GeoJSON file not found!")
        st.sidebar.info(f"Expected at: {GEOJSON_PATH}")
    else:
        st.sidebar.success("✅ India Grid Data Available")
        
        # Region selector
        region = st.sidebar.selectbox(
            "Select Region:",
            get_available_regions(),
            index=0
        )
        
        # Data limits
        col1, col2 = st.sidebar.columns(2)
        max_towers = col1.number_input("Max Towers", 100, 50000, 5000, 500)
        max_lines = col2.number_input("Max Lines", 50, 5000, 1000, 100)
        
        if st.sidebar.button("🔌 Load India Grid", type="primary"):
            progress_bar = st.sidebar.progress(0)
            status_text = st.sidebar.empty()
            
            def update_progress(pct, msg):
                progress_bar.progress(pct)
                status_text.text(msg)
            
            with st.spinner("Loading India Transmission Grid..."):
                towers, lines = load_geojson_features(
                    region=region,
                    max_towers=max_towers,
                    max_lines=max_lines,
                    progress_callback=update_progress
                )
                
                if towers or lines:
                    status_text.text("Building network...")
                    nodes, poles, line_data = process_geojson_data(towers, lines)
                    
                    if poles or line_data:
                        net = build_network(nodes, poles, line_data)
                        st.session_state['net'] = net
                        st.session_state['energized'] = False
                        st.session_state['fault_line'] = None
                        st.session_state['sensors'] = []
                        st.session_state['data_source'] = f"India Grid ({region})"
                        
                        progress_bar.progress(100)
                        status_text.text("✅ Grid loaded successfully!")
                        st.success(f"Grid Built! {len(net.bus)} Nodes, {len(net.line)} Lines")
                    else:
                        st.error("No valid data found in the selected region.")
                else:
                    st.error("Failed to load GeoJSON data.")

else:  # OSM Custom Area
    st.sidebar.markdown("---")
    st.sidebar.subheader("OSM Bounding Box")
    
    col1, col2 = st.sidebar.columns(2)
    south = col1.number_input("South", value=28.50, format="%.4f")
    north = col2.number_input("North", value=28.70, format="%.4f")
    west = col1.number_input("West", value=77.10, format="%.4f")
    east = col2.number_input("East", value=77.30, format="%.4f")
    
    if st.sidebar.button("🌐 Fetch OSM Data & Build Grid"):
        with st.spinner("Fetching data from OpenStreetMap..."):
            osm_data = fetch_osm_data(bbox=(south, west, north, east))
            if osm_data:
                nodes, poles, lines = process_osm_data(osm_data)
                if poles:
                    net = build_network(nodes, poles, lines)
                    st.session_state['net'] = net
                    st.session_state['energized'] = False
                    st.session_state['fault_line'] = None
                    st.session_state['sensors'] = []
                    st.session_state['data_source'] = "OSM (Custom Area)"
                    st.success(f"Grid Built! {len(net.bus)} Poles, {len(net.line)} Lines")
                else:
                    st.error("No poles found.")
            else:
                st.error("Failed to fetch data.")

net = st.session_state['net']

if net is not None:
    # Show data source
    if st.session_state['data_source']:
        st.markdown(f"**📊 Data Source:** {st.session_state['data_source']}")
    
    # --- PANEL: SENSORS ---
    st.sidebar.markdown("---")
    st.sidebar.header("2. Sensor Placement")
    
    # Auto Place
    if st.sidebar.button("Auto-Place Sensors (Sqrt N)"):
        try:
            start_bus = net.ext_grid.bus.iloc[0]
            g = pp.topology.create_nxgraph(net)
            ordering = list(nx.dfs_preorder_nodes(g, source=start_bus))
            n = len(ordering)
            k = math.ceil(math.sqrt(n))
            
            new_sensors = []
            for i in range(k-1, n, k):
                new_sensors.append(ordering[i])
            if ordering[-1] not in new_sensors:
                new_sensors.append(ordering[-1])
                
            st.session_state['sensors'] = new_sensors
            st.success(f"Placed {len(new_sensors)} sensors automatically.")
        except Exception as e:
            st.error(f"Auto-placement failed: {e}")

    # Manual Place
    all_buses = list(net.bus.index)
    selected_sensors = st.sidebar.multiselect(
        "Manually Select Sensor Poles:", 
        all_buses, 
        default=st.session_state['sensors']
    )
    st.session_state['sensors'] = selected_sensors

    # --- PANEL: CONTROL ---
    st.sidebar.markdown("---")
    st.sidebar.header("3. Grid Control")
    
    col1, col2 = st.sidebar.columns(2)
    if col1.button("🔌 Energize Grid"):
        st.session_state['energized'] = True
        st.session_state['fault_line'] = None
        
    if col2.button("🚫 Cut Power"):
        st.session_state['energized'] = False
        st.session_state['fault_line'] = None

    # --- PANEL: FAULT ---
    st.sidebar.markdown("---")
    st.sidebar.header("4. Fault Generation")
    
    failed_lines_options = list(net.line.index)
    fault_target = st.sidebar.selectbox("Select Line to Fault:", failed_lines_options)
    
    if st.sidebar.button("💥 Trigger Fault"):
        if st.session_state['energized']:
            st.session_state['fault_line'] = fault_target
        else:
            st.warning("Energize the grid first!")

    # --- MAIN DISPLAY ---
    
    # Calculate Status
    if st.session_state['energized']:
        net.line['in_service'] = True
        
        if st.session_state['fault_line'] is not None:
            net.line.at[st.session_state['fault_line'], 'in_service'] = False
            
        status = get_energized_status(net)
    else:
        status = {b: 0 for b in net.bus.index}

    # Sensor Analysis
    sensors = st.session_state['sensors']
    if sensors and st.session_state['energized']:
        live_sensors = sum(1 for s in sensors if status.get(s,0)==1)
        dead_sensors = len(sensors) - live_sensors
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Nodes", len(net.bus))
        c2.metric("Total Sensors", len(sensors))
        c3.metric("Live Sensors", live_sensors, delta_color="normal")
        c4.metric("Dead Sensors", dead_sensors, delta_color="inverse")
    
    # Render Map
    fig = create_plotly_map(net, status, st.session_state['fault_line'], sensors)
    st.plotly_chart(fig, use_container_width=True)
    
    st.info("💡 Tip: Use the sidebar to control electricity flow and sensors. Choose between India Grid data or OSM custom areas.")

else:
    st.markdown("### 👋 Welcome to the Smart Grid Simulator")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div class="data-source-card">
            <h3>🇮🇳 India Transmission Grid</h3>
            <p>Visualize India's complete high-voltage transmission network with 200,000+ towers and 1,200+ transmission lines.</p>
            <p><strong>Features:</strong></p>
            <ul>
                <li>Regional filtering (North, South, East, West)</li>
                <li>High-voltage transmission lines</li>
                <li>Tower locations across India</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="data-source-card">
            <h3>🌐 OpenStreetMap Data</h3>
            <p>Fetch real-time power infrastructure data from OpenStreetMap for any area worldwide.</p>
            <p><strong>Features:</strong></p>
            <ul>
                <li>Custom bounding box selection</li>
                <li>Live OSM data fetching</li>
                <li>Poles, towers, and lines</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.info("👈 **Get Started:** Select a data source from the sidebar and load the grid!")
