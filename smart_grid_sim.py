import requests
import pandapower as pp
import pandapower.plotting as pp_plot
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import networkx as nx
import json
import os
import math
import re

# Default Bounding Box (New Delhi, wider area)
# south, west, north, east
DEFAULT_BBOX = (28.5000, 77.1000, 28.7000, 77.3000)

def fetch_osm_data(bbox=DEFAULT_BBOX):
    """
    Fetches power infrastructure data from OSM Overpass API.
    Returns the JSON response.
    """
    overpass_url = "http://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json];
    (
      node["power"="pole"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
      node["power"="tower"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
      way["power"="line"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
      node["power"="substation"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});
    );
    out body;
    >;
    out skel qt;
    """
    try:
        print("Fetching data from OSM Overpass API...")
        response = requests.get(overpass_url, params={'data': overpass_query}, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('elements'):
            print("Warning: No elements found in the specified bounding box.")
            return None
            
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from OSM: {e}")
        print("Please consider downloading the data manually from https://overpass-turbo.eu/")
        print("Export as JSON and load it locally if needed.")
        return None

def process_osm_data(data):
    """
    Process OSM data into lists of poles and lines.
    """
    if not data:
        return [], []
        
    nodes = {}
    poles = []
    lines = [] # These will be list of node IDs
    
    for element in data['elements']:
        if element['type'] == 'node':
            nodes[element['id']] = {
                'lat': element['lat'],
                'lon': element['lon'],
                'tags': element.get('tags', {})
            }
            if element.get('tags', {}).get('power') in ['pole', 'tower']:
                poles.append(element['id'])
        elif element['type'] == 'way':
             if element.get('tags', {}).get('power') == 'line':
                # Capture voltage if available
                voltage = element.get('tags', {}).get('voltage', '11000') # Default to 11kV
                lines.append({
                    'nodes': element['nodes'],
                    'voltage': voltage
                })
                
    return nodes, poles, lines


def build_network(nodes, poles, lines):
    """
    Convert OSM nodes/lines into a Pandapower network.
    """
    net = pp.create_empty_network()
    
    # Map OSM Node ID -> Pandapower Bus ID
    osm_to_bus = {}
    
    # create buses for poles
    relevant_nodes = set(poles)
    for line_data in lines:
        relevant_nodes.update(line_data['nodes'])
        
    for node_id in relevant_nodes:
        if node_id not in nodes:
            continue
            
        node_info = nodes[node_id]
        # Create bus
        bus_id = pp.create_bus(net, vn_kv=11.0, name=f"OSM_{node_id}", 
                               geo=(node_info['lon'], node_info['lat']))
        osm_to_bus[node_id] = bus_id

    # Create lines
    lines_created = 0
    for line_data in lines:
        line_nodes = line_data['nodes']
        voltage_str = line_data['voltage']
        
        # Simple voltage parsing
        try:
             import re
             v_val = float(re.findall(r"[-+]?\d*\.\d+|\d+", str(voltage_str))[0])
             if v_val > 500:
                 v_val = v_val / 1000.0
             if v_val == 0: v_val = 11.0
        except:
            v_val = 11.0

        for i in range(len(line_nodes) - 1):
            u, v = line_nodes[i], line_nodes[i+1]
            if u in osm_to_bus and v in osm_to_bus:
                pp.create_line(net, osm_to_bus[u], osm_to_bus[v], length_km=0.1, 
                               std_type="NA2XS2Y 1x240 RM/25 12/20 kV", 
                               name=f"Line_{u}_{v}_{v_val}kV")
                lines_created += 1
                
    if len(net.bus) == 0:
        print("No buses created. Check data.")
        return net

    # Find Connected Components and keep the largest one
    mg = pp.topology.create_nxgraph(net)
    if not nx.is_connected(mg):
        print("Network is not fully connected. Keeping the largest connected component...")
        largest_cc = max(nx.connected_components(mg), key=len)
        
        buses_to_drop = set(net.bus.index) - largest_cc
        net.bus.drop(buses_to_drop, inplace=True)
        
        lines_to_keep = []
        for idx, row in net.line.iterrows():
            if row.from_bus in largest_cc and row.to_bus in largest_cc:
                lines_to_keep.append(idx)
        
        net.line = net.line.loc[lines_to_keep]
        
    print(f"Network built: {len(net.bus)} buses, {len(net.line)} lines.")
    
    # Add External Grid (Source)
    if len(net.bus) > 0:
        ext_grid_bus = net.bus.index[0]
        pp.create_ext_grid(net, bus=ext_grid_bus, vm_pu=1.02, name="Substation_Feed")
        print(f"External Grid attached at Bus {ext_grid_bus}")
        
    return net

def sort_buses_linearly(net):
    """
    Sorts buses based on topological distance from the external grid (substation).
    """
    if len(net.ext_grid) == 0:
        return []
        
    start_bus = net.ext_grid.bus.iloc[0]
    
    g = pp.topology.create_nxgraph(net)
    
    try:
        ordering = list(nx.dfs_preorder_nodes(g, source=start_bus))
        
        if len(ordering) > 100:
            print(f"Limiting demo to first 100 poles out of {len(ordering)}.")
            ordering = ordering[:100]
            
        return ordering
    except Exception as e:
        print(f"Error sorting buses: {e}")
        return list(net.bus.index)

def simulate_fault(net):
    """
    Runs power flow, selects a random line to disconnect (fault).
    """
    try:
        pp.runpp(net)
        print("Initial Power Flow successful.")
    except pp.LoadflowNotConverged:
        print("Initial Power Flow failed to converge!")
        return None
        
    if len(net.line) == 0:
        return None

    fault_line_idx = np.random.choice(net.line.index)
    net.line.at[fault_line_idx, 'in_service'] = False
    
    try:
        pp.runpp(net)
    except:
        pass
        
    return fault_line_idx

def get_energized_status(net):
    """
    Returns a dictionary {bus_id: status (1/0)}
    Logic: simple connectivity check from Ext Grid. 
    """
    g = pp.topology.create_nxgraph(net, respect_switches=True)
    
    if len(net.ext_grid) == 0:
        return {b: 0 for b in net.bus.index}
        
    start_bus = net.ext_grid.bus.iloc[0]
    
    try:
        reachable = set(nx.descendants(g, start_bus)) | {start_bus}
    except:
        reachable = set()
    
    status = {}
    for bus in net.bus.index:
        status[bus] = 1 if bus in reachable else 0
        
    return status

def apply_sensor_strategy(net, sorted_buses):
    """
    Implements Square-Root n Sensor Placement.
    """
    n = len(sorted_buses)
    if n == 0:
        return [], [], None
        
    k = math.ceil(math.sqrt(n))
    print(f"Total poles: {n}, Block size k: {k}")
    
    blocks = []
    current_block = []
    
    for i, bus in enumerate(sorted_buses):
        current_block.append(bus)
        if len(current_block) == k:
            blocks.append(current_block)
            current_block = []
    if current_block:
        blocks.append(current_block)
        
    sensors = []
    for blk in blocks:
        sensors.append(blk[-1])
        
    real_status = get_energized_status(net)
    sensor_readings = [real_status.get(s, 0) for s in sensors]
    
    faulty_block_idx = -1
    for i, reading in enumerate(sensor_readings):
        if reading == 0:
            faulty_block_idx = i
            break
            
    print(f"Sensor Readings: {sensor_readings}")
    print(f"Identified Faulty Block Index: {faulty_block_idx}")
    
    return sensors, blocks, faulty_block_idx

def get_voltage_color(voltage_kv):
    if voltage_kv < 11: return 'cyan'
    if voltage_kv == 11: return 'blue'
    if voltage_kv == 33: return 'orange'
    if voltage_kv > 33: return 'purple'
    return 'gray'

def visualize_grid(net, sensors, blocks, faulty_block_idx, output_file="grid_monitoring_demo.html"):
    """
    Generates an interactive Plotly map with Flow Control Buttons.
    """
    print("Generating interactive visualization with flow control...")
    
    fault_energized_status = get_energized_status(net)
    
    def get_gmaps_url(lat, lon):
        return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"

    data = []
    
    # 1. POLES
    bus_x = net.bus.geo.apply(lambda x: x[0]).tolist()
    bus_y = net.bus.geo.apply(lambda x: x[1]).tolist()
    bus_urls = [get_gmaps_url(y, x) for x, y in zip(bus_x, bus_y)]
    bus_names = net.bus.index.astype(str).tolist()
    
    trace_poles_off = go.Scattermapbox(
        lon=bus_x, lat=bus_y, mode='markers',
        marker=dict(size=6, color='gray', opacity=0.5),
        name='Poles (OFF)', text=bus_names, customdata=bus_urls, visible=True
    )
    
    trace_poles_on = go.Scattermapbox(
        lon=bus_x, lat=bus_y, mode='markers',
        marker=dict(size=6, color='black', opacity=0.8),
        name='Poles (ON)', text=bus_names, customdata=bus_urls, visible=False
    )
    
    # 2. LINES
    lines_x_off = []
    lines_y_off = []
    lines_x_on_by_volt = {} 
    
    lines_x_fault_energized = {}
    lines_x_fault_deenergized = []
    lines_y_fault_energized = {}
    lines_y_fault_deenergized = []
    
    for idx, row in net.line.iterrows():
        try:
            fb = net.bus.loc[row.from_bus]
            tb = net.bus.loc[row.to_bus]
            
            import re
            try:
                v_val = float(re.findall(r"_([\d.]+)kV", row['name'])[0])
            except:
                v_val = 11.0
            
            xs = [fb.geo[0], tb.geo[0], None]
            ys = [fb.geo[1], tb.geo[1], None]
            
            lines_x_off.extend(xs)
            lines_y_off.extend(ys)
            
            if v_val not in lines_x_on_by_volt:
                lines_x_on_by_volt[v_val] = ([], [])
            lines_x_on_by_volt[v_val][0].extend(xs)
            lines_x_on_by_volt[v_val][1].extend(ys)
            
            is_energized = (fault_energized_status.get(row.from_bus, 0) == 1 and 
                            fault_energized_status.get(row.to_bus, 0) == 1)
            
            if is_energized:
                if v_val not in lines_x_fault_energized:
                    lines_x_fault_energized[v_val] = ([], [])
                lines_x_fault_energized[v_val][0].extend(xs)
                lines_x_fault_energized[v_val][1].extend(ys)
            else:
                lines_x_fault_deenergized.extend(xs)
                lines_y_fault_deenergized.extend(ys)
        except:
            pass

    trace_lines_off = go.Scattermapbox(
        lon=lines_x_off, lat=lines_y_off, mode='lines',
        line=dict(width=2, color='lightgray'),
        name='Lines (OFF)', hoverinfo='none', visible=True
    )
    
    traces_lines_on = []
    for volt, (lx, ly) in lines_x_on_by_volt.items():
        color = get_voltage_color(volt)
        t = go.Scattermapbox(
            lon=lx, lat=ly, mode='lines',
            line=dict(width=2, color=color),
            name=f'{volt}kV Lines', visible=False
        )
        traces_lines_on.append(t)
        
    traces_lines_fault_on = []
    for volt, (lx, ly) in lines_x_fault_energized.items():
        color = get_voltage_color(volt)
        t = go.Scattermapbox(
            lon=lx, lat=ly, mode='lines',
            line=dict(width=2, color=color),
            name=f'{volt}kV Lines (Live)', visible=False
        )
        traces_lines_fault_on.append(t)
        
    trace_lines_fault_off = go.Scattermapbox(
        lon=lines_x_fault_deenergized, lat=lines_y_fault_deenergized,
        mode='lines',
        line=dict(width=2, color='gray'),
        name='Lines (De-energized)', visible=False
    )
    
    # 3. SENSORS
    sensor_x = [net.bus.loc[s, 'geo'][0] for s in sensors if s in net.bus.index]
    sensor_y = [net.bus.loc[s, 'geo'][1] for s in sensors if s in net.bus.index]
    
    trace_sensors_on = go.Scattermapbox(
        lon=sensor_x, lat=sensor_y, mode='markers',
        marker=dict(size=12, color='blue', symbol='circle'),
        name='Sensors (Active)', visible=False
    )
    
    s_x_f = []
    s_y_f = []
    s_c_f = []
    s_t_f = []
    
    real_status = get_energized_status(net)
    
    for s in sensors:
        if s in net.bus.index:
            reading = real_status.get(s, 0)
            geo = net.bus.loc[s, 'geo']
            s_x_f.append(geo[0])
            s_y_f.append(geo[1])
            col = 'blue' if reading == 1 else 'gray'
            s_c_f.append(col)
            s_t_f.append(f"Sensor: {'LIVE' if reading else 'DEAD'}")
            
    trace_sensors_fault = go.Scattermapbox(
        lon=s_x_f, lat=s_y_f, mode='markers',
        marker=dict(size=12, color=s_c_f, symbol='circle'),
        name='Sensors (Reporting)', text=s_t_f, visible=False
    )
    
    # 4. FAULTY BLOCK
    trace_fault_block = go.Scattermapbox(lon=[], lat=[]) 
    if faulty_block_idx is not None and 0 <= faulty_block_idx < len(blocks):
        faulty_block_buses = blocks[faulty_block_idx]
        fb_x = [net.bus.loc[b, 'geo'][0] for b in faulty_block_buses if b in net.bus.index]
        fb_y = [net.bus.loc[b, 'geo'][1] for b in faulty_block_buses if b in net.bus.index]
        
        trace_fault_block = go.Scattermapbox(
            lon=fb_x, lat=fb_y, mode='markers',
            marker=dict(size=14, color='red', opacity=0.9),
            name='Faulty Block Detected',
            text=[f"Faulty Block {faulty_block_idx}"] * len(fb_x),
            visible=False
        )
        
    # ASSEMBLE
    data.append(trace_lines_off)  # 0
    data.append(trace_poles_off)  # 1
    
    offset_on = len(data)
    data.extend(traces_lines_on) 
    data.append(trace_poles_on)
    data.append(trace_sensors_on)
    count_on = len(traces_lines_on) + 2
    
    offset_fault = len(data)
    data.extend(traces_lines_fault_on)
    data.append(trace_lines_fault_off)
    trace_poles_fault = go.Scattermapbox(
         lon=bus_x, lat=bus_y, mode='markers', marker=dict(size=6, color='black'), 
         name='Poles', visible=False, customdata=bus_urls
    )
    data.append(trace_poles_fault)
    data.append(trace_sensors_fault)
    data.append(trace_fault_block)
    
    total_traces = len(data)
    
    vis_off = [False] * total_traces
    vis_off[0] = True 
    vis_off[1] = True 
    
    vis_on = [False] * total_traces
    for i in range(offset_on, offset_on + count_on):
        vis_on[i] = True
        
    vis_fault = [False] * total_traces
    for i in range(offset_fault, total_traces):
        vis_fault[i] = True
        
    updatemenus = [
        dict(
            type="buttons",
            direction="left",
            buttons=[
                dict(label="System Off", method="update", args=[{"visible": vis_off}, {"title": "System Status: OFF"}]),
                dict(label="Energize Grid", method="update", args=[{"visible": vis_on}, {"title": "System Status: NORMAL FLOW"}]),
                dict(label="Simulate Fault", method="update", args=[{"visible": vis_fault}, {"title": "System Status: FAULT DETECTED"}])
            ],
            pad={"r": 10, "t": 10},
            showactive=True, x=0.05, xanchor="left", y=1.1, yanchor="top"
        ),
    ]

    center_lat = sum(bus_y) / len(bus_y) if bus_y else DEFAULT_BBOX[0]
    center_lon = sum(bus_x) / len(bus_x) if bus_x else DEFAULT_BBOX[1]

    layout = go.Layout(
        title='System Status: OFF',
        mapbox_style="carto-positron",
        mapbox=dict(center=dict(lat=center_lat, lon=center_lon), zoom=15),
        updatemenus=updatemenus,
        margin=dict(l=0, r=0, t=80, b=0),
        legend=dict(x=0, y=1, bgcolor='rgba(255,255,255,0.7)')
    )
    
    fig = go.Figure(data=data, layout=layout)
    fig.write_html(output_file)
    
    js_code = """
    <script>
    document.addEventListener("DOMContentLoaded", function(){
        var plotElement = document.getElementsByClassName('plotly-graph-div')[0];
        plotElement.on('plotly_click', function(data){
            if(data.points.length > 0){
                var url = data.points[0].customdata;
                if(url && url.startsWith('http')){
                    window.open(url, '_blank');
                }
            }
        });
    });
    </script>
    """
    with open(output_file, "a") as f:
        f.write(js_code)
        
    print(f"Visualization saved to {output_file} with Google Maps integration.")

def main():
    print("=== Smart Grid Simulator ===")
    osm_data = fetch_osm_data()
    if not osm_data:
        print("Required data not found. Exiting.")
        return

    nodes, poles, lines = process_osm_data(osm_data)
    if not poles:
        print("No poles found in data. Exiting.")
        return
        
    net = build_network(nodes, poles, lines)
    if len(net.bus) == 0:
        return

    sorted_buses = sort_buses_linearly(net)
    print(f"Sorted {len(sorted_buses)} buses for sensor placement.")
    
    fault_idx = simulate_fault(net)
    if fault_idx is not None:
        print(f"Simulated fault on Line Index: {fault_idx}")
    else:
        print("Could not simulate fault/power flow.")
        
    sensors, blocks, faulty_block_idx = apply_sensor_strategy(net, sorted_buses)
    visualize_grid(net, sensors, blocks, faulty_block_idx)

if __name__ == "__main__":
    main()
