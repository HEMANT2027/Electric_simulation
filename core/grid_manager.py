import pandapower as pp
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import networkx as nx
import math
import re

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
