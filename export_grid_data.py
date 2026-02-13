"""
Export Grid Data to JSON
=========================
Builds the grid using core/ modules and exports a compact JSON file
for the React dashboard. The JSON contains all buses, lines, towers,
poles, substations, and the ext_grid source — everything the client-side
simulation engine needs.

Usage:
    python export_grid_data.py
"""

import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(__file__))

from core.geojson_loader import load_overpass_geojson
from core.grid_builder import build_grid_from_geojson

GEOJSON_FILE = os.path.join(os.path.dirname(__file__), "IndiaTransmission - Copy.geojson")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "dashboard", "public", "grid_data.json")

# ── Delhi NCR bounding box ──
# Covers Delhi, Noida, Gurugram, Faridabad, Ghaziabad and surroundings
BBOX = {
    "min_lon": 76.5,
    "max_lon": 77.8,
    "min_lat": 27.5,
    "max_lat": 29.0,
}


def in_bbox(lon, lat, bbox=BBOX):
    """Check if a point falls within the bounding box."""
    return (bbox["min_lon"] <= lon <= bbox["max_lon"] and
            bbox["min_lat"] <= lat <= bbox["max_lat"])


def main():
    print("⚡ Exporting grid data for React dashboard (Delhi NCR region)...")
    t_start = time.time()

    # Load & classify
    classified = load_overpass_geojson(GEOJSON_FILE)
    
    # Build grid (process all lines so connectivity is correct)
    grid = build_grid_from_geojson(classified, max_lines=50000)
    
    print(f"Full grid: {grid.num_buses} buses, {grid.num_lines} edges")
    
    # ── Filter buses to Delhi NCR bounding box ──
    region_bus_ids = set()
    for bus_id in grid.G.nodes():
        geo = grid.bus_geo.get(bus_id, (0, 0))
        lon, lat = geo[0], geo[1]
        if in_bbox(lon, lat):
            region_bus_ids.add(bus_id)
    
    print(f"Buses in Delhi NCR: {len(region_bus_ids)} / {grid.num_buses}")
    
    # ── Export buses: [id, lon, lat, voltage_kv] ──
    buses = []
    for bus_id in region_bus_ids:
        geo = grid.bus_geo.get(bus_id, (0, 0))
        voltage = grid.bus_voltage.get(bus_id, 11.0)
        buses.append([bus_id, round(geo[0], 5), round(geo[1], 5), voltage])
    
    # ── Export lines: only those connecting two buses within the region ──
    lines = []
    new_idx = 0
    for line in grid.line_list:
        if line['from_bus'] in region_bus_ids and line['to_bus'] in region_bus_ids:
            lines.append([
                new_idx,
                line['from_bus'],
                line['to_bus'],
                line['voltage_kv'],
                line['name']
            ])
            new_idx += 1
    
    # ── Export towers within bbox ──
    towers = []
    for feat in classified.get('towers', []):
        geom = feat.get('geometry', {})
        if geom.get('type') == 'Point':
            coords = geom.get('coordinates', [])
            if len(coords) >= 2 and in_bbox(coords[0], coords[1]):
                towers.append([round(coords[0], 5), round(coords[1], 5)])
    
    # ── Export poles within bbox ──
    poles = []
    for feat in classified.get('poles', []):
        geom = feat.get('geometry', {})
        if geom.get('type') == 'Point':
            coords = geom.get('coordinates', [])
            if len(coords) >= 2 and in_bbox(coords[0], coords[1]):
                poles.append([round(coords[0], 5), round(coords[1], 5)])
    
    # ── Export substations within bbox ──
    substations = []
    for feat in classified.get('substations', []):
        props = feat.get('properties', {})
        geom = feat.get('geometry', {})
        geom_type = geom.get('type', '')
        
        voltage_str = props.get('voltage', '')
        name = props.get('name', props.get('ref', ''))
        
        if geom_type == 'Point':
            coords = geom.get('coordinates', [])
            if len(coords) >= 2 and in_bbox(coords[0], coords[1]):
                substations.append([round(coords[0], 5), round(coords[1], 5), voltage_str, name])
        elif geom_type == 'Polygon':
            ring = geom.get('coordinates', [[]])[0]
            if ring:
                lons = [c[0] for c in ring]
                lats = [c[1] for c in ring]
                cx = sum(lons) / len(lons)
                cy = sum(lats) / len(lats)
                if in_bbox(cx, cy):
                    substations.append([
                        round(cx, 5), round(cy, 5),
                        voltage_str, name
                    ])
    
    # ── Pick a power source bus within the region ──
    ext_grid_bus = grid.ext_grid_bus
    if ext_grid_bus not in region_bus_ids:
        # Fallback: pick a high-voltage bus in the region
        best_bus = None
        best_v = 0
        for bus_id in region_bus_ids:
            v = grid.bus_voltage.get(bus_id, 11.0)
            if v > best_v:
                best_v = v
                best_bus = bus_id
        ext_grid_bus = best_bus if best_bus is not None else (list(region_bus_ids)[0] if region_bus_ids else 0)
        print(f"Power source reassigned to bus {ext_grid_bus} ({best_v} kV) within Delhi NCR")
    
    # ── Build output ──
    data = {
        "buses": buses,
        "lines": lines,
        "towers": towers,
        "poles": poles,
        "substations": substations,
        "ext_grid_bus": ext_grid_bus,
        "stats": {
            "total_buses": len(buses),
            "total_lines": len(lines),
            "total_towers": len(towers),
            "total_poles": len(poles),
            "total_substations": len(substations),
        }
    }
    
    # Ensure output dir exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, separators=(',', ':'))
    
    file_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    
    print(f"\n✅ Exported to {OUTPUT_FILE}")
    print(f"   Region: Delhi NCR ({BBOX})")
    print(f"   Size: {file_mb:.1f} MB")
    print(f"   Buses: {len(buses)}")
    print(f"   Lines: {len(lines)}")
    print(f"   Towers: {len(towers)}")
    print(f"   Poles: {len(poles)}")
    print(f"   Substations: {len(substations)}")
    print(f"   Time: {time.time()-t_start:.1f}s")


if __name__ == "__main__":
    main()
