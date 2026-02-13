"""
Simulation Visualizer Module
==============================
Generates interactive Folium HTML maps showing the simulation state.

Renders:
  - Transmission lines color-coded by voltage (live) or gray (dead)
  - Sensors as large colored circles: green (live) / red (dead)
  - Faulted line highlighted in red dashes
  - Power source marker
  - Full legend with stats

Works with the lightweight GridNetwork from grid_builder.py.
"""

import os
import folium
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────
# VOLTAGE → COLOR MAPPING
# ─────────────────────────────────────────────
VOLTAGE_COLORS = {
    765: {"color": "#FF0040", "label": "765 kV", "width": 4},
    800: {"color": "#FF0040", "label": "800 kV", "width": 4},
    500: {"color": "#FF6600", "label": "500 kV", "width": 3.5},
    400: {"color": "#FF8C00", "label": "400 kV", "width": 3.5},
    220: {"color": "#FFD700", "label": "220 kV", "width": 3},
    132: {"color": "#00BFFF", "label": "132 kV", "width": 2.5},
    100: {"color": "#00CED1", "label": "100 kV", "width": 2.3},
    66:  {"color": "#00E676", "label": "66 kV", "width": 2},
    33:  {"color": "#AB47BC", "label": "33 kV", "width": 1.8},
    22:  {"color": "#90CAF9", "label": "22 kV", "width": 1.5},
    11:  {"color": "#64B5F6", "label": "11 kV", "width": 1.5},
}

DEAD_COLOR = "#424242"
FAULT_COLOR = "#FF0000"
SENSOR_LIVE = "#00E676"
SENSOR_DEAD = "#FF1744"
SOURCE_COLOR = "#E040FB"


def _get_voltage_style(kv: float) -> dict:
    """Return color/width for a voltage level."""
    kv_int = int(round(kv))
    if kv_int in VOLTAGE_COLORS:
        return VOLTAGE_COLORS[kv_int]
    for threshold in sorted(VOLTAGE_COLORS.keys(), reverse=True):
        if kv_int >= threshold:
            return VOLTAGE_COLORS[threshold]
    return {"color": "#64B5F6", "label": f"{kv_int} kV", "width": 1.5}


def _get_map_center(grid) -> Tuple[float, float]:
    """Get center lat/lon from bus geos."""
    lats, lons = [], []
    for bus_id, geo in grid.bus_geo.items():
        lons.append(geo[0])
        lats.append(geo[1])
    if lats:
        return sum(lats) / len(lats), sum(lons) / len(lons)
    return 28.6, 77.2


def render_simulation_map(
    grid,
    energized_status: Dict[int, int],
    sensors: List[int] = None,
    sensor_readings: Dict[int, int] = None,
    blocks: List[List[int]] = None,
    fault_info: dict = None,
    faulty_block_idx: int = -1,
    step_name: str = "simulation",
    output_dir: str = ".",
    title: str = "Grid Simulation"
) -> str:
    """
    Render the current simulation state as an interactive Folium map.
    
    Returns:
        Path to the generated HTML file
    """
    center_lat, center_lon = _get_map_center(grid)
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles=None,
        prefer_canvas=True,
    )
    
    # Tile layers
    folium.TileLayer("cartodbdark_matter", name="🌑 Dark", control=True).add_to(m)
    folium.TileLayer("cartodbpositron", name="☀️ Light", control=True).add_to(m)
    
    # ── 1. PLOT LINES ──
    fg_live = folium.FeatureGroup(name="⚡ Energized Lines", show=True)
    fg_dead = folium.FeatureGroup(name="💀 De-energized Lines", show=True)
    fg_fault = folium.FeatureGroup(name="💥 Faulted Line", show=True)
    
    fault_line_idx = fault_info.get('line_idx', -1) if fault_info else -1
    
    for line in grid.line_list:
        fb = line['from_bus']
        tb = line['to_bus']
        
        if fb not in grid.bus_geo or tb not in grid.bus_geo:
            continue
        
        geo_fb = grid.bus_geo[fb]
        geo_tb = grid.bus_geo[tb]
        coords = [[geo_fb[1], geo_fb[0]], [geo_tb[1], geo_tb[0]]]
        
        kv = line['voltage_kv']
        style = _get_voltage_style(kv)
        
        if line['idx'] == fault_line_idx:
            folium.PolyLine(
                locations=coords,
                color=FAULT_COLOR,
                weight=6,
                opacity=1.0,
                dash_array="10 5",
                tooltip=f"💥 FAULT — {line['name']} ({kv} kV)",
            ).add_to(fg_fault)
            continue
        
        fb_live = energized_status.get(fb, 0) == 1
        tb_live = energized_status.get(tb, 0) == 1
        is_live = fb_live and tb_live and line['in_service']
        
        if is_live:
            folium.PolyLine(
                locations=coords,
                color=style["color"],
                weight=style["width"],
                opacity=0.85,
                tooltip=f"{style['label']} | {line['name']}",
            ).add_to(fg_live)
        else:
            folium.PolyLine(
                locations=coords,
                color=DEAD_COLOR,
                weight=1.5,
                opacity=0.4,
                tooltip=f"DEAD — {line['name']}",
            ).add_to(fg_dead)
    
    fg_live.add_to(m)
    fg_dead.add_to(m)
    fg_fault.add_to(m)
    
    # ── 2. PLOT SENSORS ──
    if sensors:
        fg_sensors = folium.FeatureGroup(name=f"📡 Sensors ({len(sensors)})", show=True)
        
        for i, sensor_bus in enumerate(sensors):
            if sensor_bus not in grid.bus_geo:
                continue
            geo = grid.bus_geo[sensor_bus]
            
            is_live = True
            if sensor_readings:
                is_live = sensor_readings.get(sensor_bus, 1) == 1
            
            color = SENSOR_LIVE if is_live else SENSOR_DEAD
            status_text = "🟢 LIVE" if is_live else "🔴 DEAD"
            
            block_info = ""
            if blocks and i < len(blocks):
                block_info = f"<br>Block {i+1}: {len(blocks[i])} buses"
            
            if faulty_block_idx == i:
                color = "#FF6D00"
                status_text += " ⚠️ FAULT BLOCK"
            
            folium.CircleMarker(
                location=[geo[1], geo[0]],
                radius=10,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                weight=2,
                tooltip=(f"<b>Sensor {i+1}</b><br>"
                        f"Bus: {sensor_bus}<br>"
                        f"Status: {status_text}{block_info}"),
            ).add_to(fg_sensors)
        
        fg_sensors.add_to(m)
    
    # ── 3. PLOT SOURCE ──
    if grid.ext_grid_bus >= 0 and grid.ext_grid_bus in grid.bus_geo:
        fg_source = folium.FeatureGroup(name="🔌 Power Source", show=True)
        geo = grid.bus_geo[grid.ext_grid_bus]
        folium.CircleMarker(
            location=[geo[1], geo[0]],
            radius=14,
            color=SOURCE_COLOR,
            fill=True,
            fill_color=SOURCE_COLOR,
            fill_opacity=0.9,
            weight=3,
            tooltip=f"<b>⚡ POWER SOURCE</b><br>Bus: {grid.ext_grid_bus}",
        ).add_to(fg_source)
        fg_source.add_to(m)
    
    # ── 4. LEGEND ──
    legend = _build_legend(energized_status, sensors, sensor_readings,
                           fault_info, faulty_block_idx)
    m.get_root().html.add_child(folium.Element(legend))
    
    # ── 5. TITLE ──
    title_html = f"""
    <div style="
        position: fixed; top: 12px; left: 50%; transform: translateX(-50%);
        z-index: 9999; background: rgba(20,20,30,0.92); color: #fff;
        padding: 10px 28px; border-radius: 30px;
        font-family: 'Segoe UI', sans-serif; font-size: 15px; font-weight: 600;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4); backdrop-filter: blur(10px);
    ">⚡ {title}</div>
    """
    m.get_root().html.add_child(folium.Element(title_html))
    
    folium.LayerControl(collapsed=False).add_to(m)
    
    # ── Save ──
    filepath = os.path.join(output_dir, f"{step_name}.html")
    m.save(filepath)
    file_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"📄 Saved: {os.path.basename(filepath)} ({file_mb:.1f} MB)")
    
    return filepath


def _build_legend(energized_status, sensors=None, sensor_readings=None,
                  fault_info=None, faulty_block_idx=-1) -> str:
    """Build an HTML legend panel."""
    live = sum(1 for v in energized_status.values() if v == 1)
    dead = sum(1 for v in energized_status.values() if v == 0)
    total = len(energized_status)
    
    stats = f'<div style="font-size:12px;margin-bottom:6px;">Buses: {live}🟢 {dead}🔴 / {total}</div>'
    
    sensor_stats = ""
    if sensors and sensor_readings:
        s_live = sum(1 for s in sensors if sensor_readings.get(s, 0) == 1)
        s_dead = len(sensors) - s_live
        sensor_stats = f'<div style="font-size:12px;margin-bottom:6px;">Sensors: {s_live}🟢 {s_dead}🔴 / {len(sensors)}</div>'
    
    fault_text = ""
    if fault_info:
        fault_text = f'<div style="font-size:11px;color:#FF1744;font-weight:bold;margin-bottom:4px;">⚠️ Fault L{fault_info.get("line_idx","?")}</div>'
    if faulty_block_idx >= 0:
        fault_text += f'<div style="font-size:11px;color:#FF6D00;margin-bottom:4px;">Block {faulty_block_idx+1} faulty</div>'
    
    v_items = ""
    for kv in sorted(VOLTAGE_COLORS.keys(), reverse=True):
        info = VOLTAGE_COLORS[kv]
        v_items += f'<div style="display:flex;align-items:center;margin:1px 0;"><div style="width:22px;height:3px;background:{info["color"]};margin-right:5px;"></div><span style="font-size:10px;">{info["label"]}</span></div>'
    
    features = f"""
    <hr style="margin:4px 0;border-color:#444;">
    <div style="display:flex;align-items:center;margin:2px 0;"><span style="color:{SENSOR_LIVE};margin-right:5px;">●</span><span style="font-size:10px;">Sensor Live</span></div>
    <div style="display:flex;align-items:center;margin:2px 0;"><span style="color:{SENSOR_DEAD};margin-right:5px;">●</span><span style="font-size:10px;">Sensor Dead</span></div>
    <div style="display:flex;align-items:center;margin:2px 0;"><span style="color:{SOURCE_COLOR};margin-right:5px;">●</span><span style="font-size:10px;">Source</span></div>
    <div style="display:flex;align-items:center;margin:2px 0;"><span style="color:{FAULT_COLOR};margin-right:5px;">━</span><span style="font-size:10px;">Fault</span></div>
    <div style="display:flex;align-items:center;margin:2px 0;"><span style="color:{DEAD_COLOR};margin-right:5px;">─</span><span style="font-size:10px;">Dead</span></div>
    """
    
    return f"""
    <div style="position:fixed;bottom:30px;left:12px;z-index:9999;
        background:rgba(20,20,30,0.92);color:#eee;padding:10px 12px;
        border-radius:10px;box-shadow:0 2px 12px rgba(0,0,0,0.5);
        font-family:'Segoe UI',sans-serif;max-height:80vh;overflow-y:auto;
        backdrop-filter:blur(8px);min-width:150px;">
        <div style="font-weight:bold;font-size:12px;margin-bottom:5px;border-bottom:1px solid #555;padding-bottom:3px;">⚡ Status</div>
        {stats}{sensor_stats}{fault_text}{v_items}{features}
    </div>"""
