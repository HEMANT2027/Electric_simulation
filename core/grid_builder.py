"""
Grid Builder Module (Optimized)
================================
Builds a lightweight graph-based grid from Overpass GeoJSON features.

IMPORTANT OPTIMIZATION: We do NOT use pandapower's per-element create_*()
functions (which are O(n²) due to DataFrame appends). Instead, we build
a NetworkX graph directly and store bus metadata in dicts. This runs in
seconds instead of 13+ minutes.

The resulting GridNetwork object has:
  - G: NetworkX graph with bus IDs as nodes, edges as line segments
  - bus_geo: Dict[bus_id → (lon, lat)]
  - bus_voltage: Dict[bus_id → kV]
  - line_data: Dict[(from_bus, to_bus) → {voltage_kv, name, in_service, length_km}]
  - ext_grid_bus: The bus where the power source is connected
"""

import networkx as nx
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class GridNetwork:
    """Lightweight grid representation (replaces pandapower net)."""
    G: nx.Graph = field(default_factory=nx.Graph)
    bus_geo: Dict[int, Tuple[float, float]] = field(default_factory=dict)     # bus_id -> (lon, lat)
    bus_voltage: Dict[int, float] = field(default_factory=dict)                # bus_id -> kV
    line_data: Dict[Tuple[int, int], dict] = field(default_factory=dict)       # (from, to) -> info
    line_list: list = field(default_factory=list)                               # ordered list of line dicts
    ext_grid_bus: int = -1
    
    @property
    def num_buses(self):
        return self.G.number_of_nodes()
    
    @property
    def num_lines(self):
        return self.G.number_of_edges()
    
    def get_bus_geo(self, bus_id: int) -> Tuple[float, float]:
        """Get (lon, lat) for a bus."""
        return self.bus_geo.get(bus_id, (77.2, 28.6))
    
    def set_line_in_service(self, line_idx: int, in_service: bool):
        """Set a line's in_service status by index."""
        if 0 <= line_idx < len(self.line_list):
            self.line_list[line_idx]['in_service'] = in_service
    
    def get_active_graph(self) -> nx.Graph:
        """Return a graph with only in-service edges."""
        active = nx.Graph()
        active.add_nodes_from(self.G.nodes())
        for line in self.line_list:
            if line['in_service']:
                active.add_edge(line['from_bus'], line['to_bus'])
        return active


def parse_voltage_kv(voltage_str: str) -> float:
    """Parse voltage string (in volts) to kV. Takes max if semicolon-separated."""
    if not voltage_str:
        return 11.0
    try:
        parts = voltage_str.split(";")
        values = [float(p.strip()) for p in parts if p.strip().replace('.', '').isdigit()]
        if not values:
            return 11.0
        max_v = max(values)
        if max_v > 1000:
            return max_v / 1000.0
        return max_v if max_v > 0 else 11.0
    except (ValueError, TypeError):
        return 11.0


def build_grid_from_geojson(classified_features: Dict[str, list],
                            max_lines: int = 5000,
                            progress_callback=None) -> GridNetwork:
    """
    Build a GridNetwork from Overpass GeoJSON features.
    
    This is FAST — O(n) instead of pandapower's O(n²).
    
    Args:
        classified_features: Dict from load_overpass_geojson()
        max_lines: Maximum number of transmission lines to process
        progress_callback: Optional callback(pct, msg)
        
    Returns:
        A GridNetwork object.
    """
    grid = GridNetwork()
    
    lines_feats = classified_features.get('lines', [])[:max_lines]
    minor_feats = classified_features.get('minor_lines', [])[:100]
    cable_feats = classified_features.get('cables', [])[:100]
    sub_feats = classified_features.get('substations', [])
    
    all_line_feats = lines_feats + minor_feats + cable_feats
    total_feats = len(all_line_feats)
    
    if progress_callback:
        progress_callback(0, f"Processing {total_feats} line features...")
    
    # ── Step 1: Build nodes and edges from line coordinates ──
    coord_to_bus = {}  # (round_lon, round_lat) -> bus_id
    bus_counter = 0
    line_idx = 0
    
    for feat_i, feat in enumerate(all_line_feats):
        props = feat.get('properties', {})
        geom = feat.get('geometry', {})
        coords = geom.get('coordinates', [])
        voltage_str = props.get('voltage', '')
        voltage_kv = parse_voltage_kv(voltage_str)
        power_type = props.get('power', 'line')
        feat_id = feat.get('id', f'feat_{feat_i}')
        
        if len(coords) < 2:
            continue
        
        # Get or create bus for each coordinate
        line_bus_ids = []
        for coord in coords:
            if len(coord) < 2:
                continue
            lon, lat = coord[0], coord[1]
            key = (round(lon, 4), round(lat, 4))
            
            if key not in coord_to_bus:
                bid = bus_counter
                coord_to_bus[key] = bid
                grid.bus_geo[bid] = (lon, lat)
                grid.bus_voltage[bid] = voltage_kv
                grid.G.add_node(bid)
                bus_counter += 1
            
            line_bus_ids.append(coord_to_bus[key])
        
        # Create edges between consecutive nodes
        for i in range(len(line_bus_ids) - 1):
            fb, tb = line_bus_ids[i], line_bus_ids[i + 1]
            if fb == tb:
                continue
            
            # Haversine distance
            geo_fb = grid.bus_geo[fb]
            geo_tb = grid.bus_geo[tb]
            length_km = _haversine(geo_fb[1], geo_fb[0], geo_tb[1], geo_tb[0])
            if length_km < 0.001:
                length_km = 0.01
            
            line_info = {
                'idx': line_idx,
                'from_bus': fb,
                'to_bus': tb,
                'voltage_kv': voltage_kv,
                'name': f"L_{feat_id}_{i}_{voltage_kv}kV",
                'power_type': power_type,
                'length_km': length_km,
                'in_service': True,
            }
            
            grid.G.add_edge(fb, tb)
            grid.line_data[(fb, tb)] = line_info
            grid.line_list.append(line_info)
            line_idx += 1
        
        if progress_callback and feat_i % 500 == 0:
            pct = int((feat_i / total_feats) * 70)
            progress_callback(pct, f"Processed {feat_i}/{total_feats}...")
    
    print(f"Created {bus_counter} buses and {line_idx} line segments.")
    
    if bus_counter == 0:
        print("ERROR: No buses created!")
        return grid
    
    # ── Step 2: Keep only the largest connected component ──
    if progress_callback:
        progress_callback(75, "Finding largest connected component...")
    
    if not nx.is_connected(grid.G):
        components = list(nx.connected_components(grid.G))
        largest_cc = max(components, key=len)
        
        removed_buses = set(grid.G.nodes()) - largest_cc
        
        # Remove non-largest nodes
        grid.G.remove_nodes_from(removed_buses)
        for bus_id in removed_buses:
            grid.bus_geo.pop(bus_id, None)
            grid.bus_voltage.pop(bus_id, None)
        
        # Filter line_list
        grid.line_list = [l for l in grid.line_list
                          if l['from_bus'] in largest_cc and l['to_bus'] in largest_cc]
        
        # Re-index lines
        for i, line in enumerate(grid.line_list):
            line['idx'] = i
        
        # Filter line_data
        grid.line_data = {k: v for k, v in grid.line_data.items()
                         if k[0] in largest_cc and k[1] in largest_cc}
        
        print(f"Kept largest component: {len(largest_cc)} buses "
              f"(removed {len(removed_buses)}, {len(components)} components)")
    
    # ── Step 3: Attach power source ──
    if progress_callback:
        progress_callback(90, "Attaching power source...")
    
    grid.ext_grid_bus = _find_best_source_bus(grid, sub_feats, coord_to_bus)
    
    if progress_callback:
        progress_callback(100, f"Grid: {grid.num_buses} buses, {grid.num_lines} edges")
    
    print(f"Final grid: {grid.num_buses} buses, {grid.num_lines} edges")
    print(f"Power source at bus {grid.ext_grid_bus}")
    
    return grid


def _find_best_source_bus(grid: GridNetwork, substation_features: list,
                          coord_to_bus: dict) -> int:
    """Find the best bus for the power source — prefers a substation with highest voltage."""
    best_bus = None
    best_voltage = 0
    
    for feat in substation_features:
        props = feat.get('properties', {})
        voltage_str = props.get('voltage', '')
        voltage_kv = parse_voltage_kv(voltage_str)
        
        geom = feat.get('geometry', {})
        geom_type = geom.get('type', '')
        
        if geom_type == 'Polygon':
            ring = geom.get('coordinates', [[]])[0]
            if ring:
                lon, lat = ring[0][0], ring[0][1]
            else:
                continue
        elif geom_type == 'Point':
            coords = geom.get('coordinates', [])
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]
            else:
                continue
        else:
            continue
        
        key = (round(lon, 4), round(lat, 4))
        if key in coord_to_bus:
            bus_id = coord_to_bus[key]
            if bus_id in grid.G.nodes() and voltage_kv > best_voltage:
                best_voltage = voltage_kv
                best_bus = bus_id
    
    if best_bus is not None:
        print(f"Source at substation bus {best_bus} ({best_voltage} kV)")
        return best_bus
    
    # Fallback: first node in the graph
    return list(grid.G.nodes())[0]


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
