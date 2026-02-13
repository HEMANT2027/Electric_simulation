"""
Transmission Map Visualizer
============================
Reads an Overpass-exported GeoJSON file containing power infrastructure
(lines, cables, substations, towers, poles, transformers) and generates
an interactive HTML map with:
  - Color coding by voltage level
  - Feature grouping with layer toggle controls
  - Legend for all voltage/feature colors
  - Dark satellite-style basemap for contrast

Usage:
    python plot_transmission_map.py
"""

import json
import os
import sys
import time

import folium
from folium.plugins import MarkerCluster

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
GEOJSON_FILE = os.path.join(os.path.dirname(__file__), "export (1).geojson")
OUTPUT_HTML = os.path.join(os.path.dirname(__file__), "transmission_map.html")

# ─────────────────────────────────────────────
# VOLTAGE → COLOR MAPPING
# ─────────────────────────────────────────────
VOLTAGE_COLORS = {
    765: {"color": "#FF0040", "label": "765 kV (UHV)", "width": 4},
    800: {"color": "#FF0040", "label": "800 kV (HVDC)", "width": 4},
    500: {"color": "#FF6600", "label": "500 kV (EHV)", "width": 3.5},
    400: {"color": "#FF8C00", "label": "400 kV (EHV)", "width": 3.5},
    220: {"color": "#FFD700", "label": "220 kV (HV)", "width": 3},
    132: {"color": "#00BFFF", "label": "132 kV (HV)", "width": 2.5},
    100: {"color": "#00CED1", "label": "100 kV", "width": 2.3},
    66:  {"color": "#00E676", "label": "66 kV (MV)", "width": 2},
    33:  {"color": "#AB47BC", "label": "33 kV (MV)", "width": 1.8},
    25:  {"color": "#7E57C2", "label": "25 kV", "width": 1.6},
    22:  {"color": "#90CAF9", "label": "22 kV (LV)", "width": 1.5},
    11:  {"color": "#64B5F6", "label": "11 kV (LV)", "width": 1.5},
    0:   {"color": "#9E9E9E", "label": "Unknown V", "width": 1.2},
}


def parse_voltage_kv(voltage_str: str) -> int:
    """Parse voltage string (in volts, e.g. '400000') into kV integer.
    Handles semicolon-separated multi-voltage strings by taking the highest."""
    if not voltage_str or voltage_str == "unknown":
        return 0
    try:
        parts = voltage_str.split(";")
        max_v = max(int(p.strip()) for p in parts if p.strip().isdigit())
        return max_v // 1000
    except (ValueError, TypeError):
        return 0


def get_voltage_style(voltage_kv: int) -> dict:
    """Return color/width/label for a given kV value."""
    if voltage_kv in VOLTAGE_COLORS:
        return VOLTAGE_COLORS[voltage_kv]
    # Find nearest
    for threshold in sorted(VOLTAGE_COLORS.keys(), reverse=True):
        if voltage_kv >= threshold:
            return VOLTAGE_COLORS[threshold]
    return VOLTAGE_COLORS[0]


def build_legend_html() -> str:
    """Build a custom HTML legend for the map."""
    items = ""
    # Voltage legend
    for kv in sorted(VOLTAGE_COLORS.keys(), reverse=True):
        if kv == 0:
            continue
        info = VOLTAGE_COLORS[kv]
        items += f"""
        <div style="display:flex;align-items:center;margin:2px 0;">
            <div style="width:30px;height:4px;background:{info['color']};margin-right:8px;border-radius:2px;"></div>
            <span style="font-size:11px;">{info['label']}</span>
        </div>"""
    # Unknown
    items += f"""
    <div style="display:flex;align-items:center;margin:2px 0;">
        <div style="width:30px;height:4px;background:#9E9E9E;margin-right:8px;border-radius:2px;"></div>
        <span style="font-size:11px;">Unknown Voltage</span>
    </div>"""
    # Feature legend
    feature_items = [
        ("#E040FB", "━━", "Underground Cable"),
        ("#78909C", "──", "Minor Line"),
        ("#2E7D32", "■", "Substation"),
        ("#455A64", "●", "Tower"),
        ("#8D6E63", "●", "Pole"),
        ("#7B1FA2", "◆", "Transformer"),
    ]
    items += '<hr style="margin:6px 0;border-color:#555;">'
    for color, symbol, label in feature_items:
        items += f"""
        <div style="display:flex;align-items:center;margin:2px 0;">
            <span style="color:{color};font-size:14px;width:30px;text-align:center;margin-right:4px;">{symbol}</span>
            <span style="font-size:11px;">{label}</span>
        </div>"""

    legend = f"""
    <div style="
        position: fixed;
        bottom: 30px;
        left: 12px;
        z-index: 9999;
        background: rgba(20,20,30,0.92);
        color: #eee;
        padding: 12px 16px;
        border-radius: 10px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.5);
        font-family: 'Segoe UI', sans-serif;
        max-height: 80vh;
        overflow-y: auto;
        backdrop-filter: blur(8px);
    ">
        <div style="font-weight:bold;font-size:13px;margin-bottom:6px;border-bottom:1px solid #555;padding-bottom:4px;">
            ⚡ Power Grid Legend
        </div>
        {items}
    </div>
    """
    return legend


def main():
    print("=" * 60)
    print("  ⚡ Transmission Map Visualizer")
    print("=" * 60)

    # ── Load GeoJSON ──
    print(f"\n📂 Loading: {os.path.basename(GEOJSON_FILE)}")
    t0 = time.time()
    with open(GEOJSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("features", [])
    print(f"   ✔ Loaded {len(features):,} features in {time.time()-t0:.1f}s")

    # ── Classify features ──
    lines = []       # power=line
    minor_lines = [] # power=minor_line
    cables = []      # power=cable
    substations = [] # power=substation
    towers = []      # power=tower
    poles = []        # power=pole
    transformers = [] # power=transformer
    others = []

    for feat in features:
        props = feat.get("properties", {})
        power_type = props.get("power", "")
        geom = feat.get("geometry", {})

        if power_type == "line":
            lines.append(feat)
        elif power_type == "minor_line":
            minor_lines.append(feat)
        elif power_type == "cable":
            cables.append(feat)
        elif power_type == "substation":
            substations.append(feat)
        elif power_type == "tower":
            towers.append(feat)
        elif power_type == "pole":
            poles.append(feat)
        elif power_type == "transformer":
            transformers.append(feat)
        else:
            others.append(feat)

    print(f"\n📊 Feature Breakdown:")
    print(f"   Lines:        {len(lines):>7,}")
    print(f"   Minor Lines:  {len(minor_lines):>7,}")
    print(f"   Cables:       {len(cables):>7,}")
    print(f"   Substations:  {len(substations):>7,}")
    print(f"   Towers:       {len(towers):>7,}")
    print(f"   Poles:         {len(poles):>7,}")
    print(f"   Transformers: {len(transformers):>7,}")
    if others:
        print(f"   Others:       {len(others):>7,}")

    # ── Compute map center from lines ──
    all_lats, all_lons = [], []
    for feat in lines[:500]:  # sample first 500 lines for center
        coords = feat.get("geometry", {}).get("coordinates", [])
        for c in coords:
            if len(c) >= 2:
                all_lons.append(c[0])
                all_lats.append(c[1])

    center_lat = sum(all_lats) / len(all_lats) if all_lats else 28.6
    center_lon = sum(all_lons) / len(all_lons) if all_lons else 77.2
    print(f"\n🗺️  Map center: ({center_lat:.4f}, {center_lon:.4f})")

    # ── Create Map ──
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles=None,  # We'll add tiles manually
        prefer_canvas=True,  # Better performance for many features
    )

    # Add tile layers
    folium.TileLayer(
        tiles="cartodbdark_matter",
        name="🌑 Dark Mode",
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="cartodbpositron",
        name="☀️ Light Mode",
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="🛰️ Satellite",
        control=True,
    ).add_to(m)

    # ── 1. PLOT TRANSMISSION LINES (grouped by voltage) ──
    print("\n🔌 Plotting transmission lines...")
    t1 = time.time()

    # Group lines by voltage for efficient plotting
    voltage_groups = {}  # kv -> [features]
    for feat in lines:
        v_str = feat.get("properties", {}).get("voltage", "")
        kv = parse_voltage_kv(v_str)
        if kv not in voltage_groups:
            voltage_groups[kv] = []
        voltage_groups[kv].append(feat)

    # Plot each voltage group as a FeatureGroup
    for kv in sorted(voltage_groups.keys(), reverse=True):
        group_feats = voltage_groups[kv]
        style = get_voltage_style(kv)
        fg = folium.FeatureGroup(name=f"⚡ {style['label']} ({len(group_feats)} lines)", show=True)

        for feat in group_feats:
            coords = feat.get("geometry", {}).get("coordinates", [])
            if not coords:
                continue
            # Folium wants [lat, lon], GeoJSON has [lon, lat]
            latlon_coords = [[c[1], c[0]] for c in coords if len(c) >= 2]
            if len(latlon_coords) < 2:
                continue

            props = feat.get("properties", {})
            cables_str = props.get("cables", "?")
            operator = props.get("operator", "Unknown")
            name = props.get("name", "")
            voltage_raw = props.get("voltage", "?")

            tooltip_text = f"<b>{name}</b><br>" if name else ""
            tooltip_text += f"Voltage: {kv} kV<br>Cables: {cables_str}<br>Operator: {operator}"

            folium.PolyLine(
                locations=latlon_coords,
                color=style["color"],
                weight=style["width"],
                opacity=0.85,
                tooltip=tooltip_text,
            ).add_to(fg)

        fg.add_to(m)

    print(f"   ✔ {len(lines)} lines plotted in {time.time()-t1:.1f}s")

    # ── 2. PLOT MINOR LINES ──
    if minor_lines:
        print(f"🔗 Plotting {len(minor_lines)} minor lines...")
        fg_minor = folium.FeatureGroup(name=f"🔗 Minor Lines ({len(minor_lines)})", show=True)
        for feat in minor_lines:
            coords = feat.get("geometry", {}).get("coordinates", [])
            if not coords:
                continue
            latlon_coords = [[c[1], c[0]] for c in coords if len(c) >= 2]
            if len(latlon_coords) < 2:
                continue
            v_str = feat.get("properties", {}).get("voltage", "")
            kv = parse_voltage_kv(v_str)
            style = get_voltage_style(kv) if kv > 0 else {"color": "#78909C", "width": 1.5}
            folium.PolyLine(
                locations=latlon_coords,
                color=style["color"] if isinstance(style, dict) else "#78909C",
                weight=style.get("width", 1.5) if isinstance(style, dict) else 1.5,
                opacity=0.7,
                dash_array="5 3",
                tooltip=f"Minor Line | {kv} kV" if kv else "Minor Line",
            ).add_to(fg_minor)
        fg_minor.add_to(m)

    # ── 3. PLOT CABLES ──
    if cables:
        print(f"🔌 Plotting {len(cables)} underground cables...")
        fg_cable = folium.FeatureGroup(name=f"🔌 Underground Cables ({len(cables)})", show=True)
        for feat in cables:
            coords = feat.get("geometry", {}).get("coordinates", [])
            if not coords:
                continue
            latlon_coords = [[c[1], c[0]] for c in coords if len(c) >= 2]
            if len(latlon_coords) < 2:
                continue
            v_str = feat.get("properties", {}).get("voltage", "")
            kv = parse_voltage_kv(v_str)
            folium.PolyLine(
                locations=latlon_coords,
                color="#E040FB",
                weight=2.5,
                opacity=0.8,
                dash_array="8 6",
                tooltip=f"Underground Cable | {kv} kV" if kv else "Underground Cable",
            ).add_to(fg_cable)
        fg_cable.add_to(m)

    # ── 4. PLOT SUBSTATIONS ──
    if substations:
        print(f"🏭 Plotting {len(substations)} substations...")
        fg_sub = folium.FeatureGroup(name=f"🏭 Substations ({len(substations)})", show=True)
        for feat in substations:
            geom = feat.get("geometry", {})
            geom_type = geom.get("type", "")
            props = feat.get("properties", {})
            name = props.get("name", "Substation")
            voltage = props.get("voltage", "?")
            operator = props.get("operator", "")

            tooltip = f"<b>{name}</b><br>Voltage: {voltage}<br>"
            if operator:
                tooltip += f"Operator: {operator}"

            if geom_type == "Polygon":
                coords_ring = geom.get("coordinates", [[]])[0]
                latlon = [[c[1], c[0]] for c in coords_ring if len(c) >= 2]
                if latlon:
                    folium.Polygon(
                        locations=latlon,
                        color="#2E7D32",
                        fill=True,
                        fill_color="#4CAF50",
                        fill_opacity=0.35,
                        weight=2,
                        tooltip=tooltip,
                    ).add_to(fg_sub)
            elif geom_type == "Point":
                coords = geom.get("coordinates", [])
                if len(coords) >= 2:
                    folium.CircleMarker(
                        location=[coords[1], coords[0]],
                        radius=7,
                        color="#2E7D32",
                        fill=True,
                        fill_color="#4CAF50",
                        fill_opacity=0.7,
                        tooltip=tooltip,
                    ).add_to(fg_sub)
        fg_sub.add_to(m)

    # ── 5. PLOT TOWERS (clustered for performance) ──
    if towers:
        print(f"🗼 Plotting {len(towers):,} towers (as lightweight markers)...")
        fg_towers = folium.FeatureGroup(name=f"🗼 Towers ({len(towers):,})", show=False)
        # Use tiny CircleMarkers for all towers (much faster than MarkerCluster at 128k)
        for feat in towers:
            coords = feat.get("geometry", {}).get("coordinates", [])
            if not coords or len(coords) < 2:
                continue
            folium.CircleMarker(
                location=[coords[1], coords[0]],
                radius=1.5,
                color="#455A64",
                fill=True,
                fill_color="#607D8B",
                fill_opacity=0.6,
                weight=0.5,
            ).add_to(fg_towers)
        fg_towers.add_to(m)
        print(f"   ✔ Towers plotted (layer OFF by default — toggle in layer control)")

    # ── 6. PLOT POLES ──
    if poles:
        print(f"📍 Plotting {len(poles):,} poles...")
        fg_poles = folium.FeatureGroup(name=f"📍 Poles ({len(poles):,})", show=False)
        for feat in poles:
            coords = feat.get("geometry", {}).get("coordinates", [])
            if not coords or len(coords) < 2:
                continue
            folium.CircleMarker(
                location=[coords[1], coords[0]],
                radius=2,
                color="#8D6E63",
                fill=True,
                fill_color="#A1887F",
                fill_opacity=0.6,
                weight=0.5,
            ).add_to(fg_poles)
        fg_poles.add_to(m)

    # ── 7. PLOT TRANSFORMERS ──
    if transformers:
        print(f"🔧 Plotting {len(transformers)} transformers...")
        fg_trans = folium.FeatureGroup(name=f"🔧 Transformers ({len(transformers)})", show=True)
        for feat in transformers:
            geom = feat.get("geometry", {})
            geom_type = geom.get("type", "")
            coords = geom.get("coordinates", [])
            props = feat.get("properties", {})
            voltage = props.get("voltage", "?")

            if geom_type == "Point" and len(coords) >= 2:
                folium.CircleMarker(
                    location=[coords[1], coords[0]],
                    radius=5,
                    color="#7B1FA2",
                    fill=True,
                    fill_color="#CE93D8",
                    fill_opacity=0.7,
                    weight=1.5,
                    tooltip=f"Transformer | {voltage}",
                ).add_to(fg_trans)
        fg_trans.add_to(m)

    # ── Add Legend ──
    legend_html = build_legend_html()
    m.get_root().html.add_child(folium.Element(legend_html))

    # ── Add Layer Control ──
    folium.LayerControl(collapsed=False).add_to(m)

    # ── Add title ──
    title_html = """
    <div style="
        position: fixed;
        top: 12px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 9999;
        background: rgba(20,20,30,0.88);
        color: #fff;
        padding: 10px 24px;
        border-radius: 30px;
        font-family: 'Segoe UI', sans-serif;
        font-size: 15px;
        font-weight: 600;
        letter-spacing: 0.5px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.4);
        backdrop-filter: blur(10px);
    ">
        ⚡ Power Transmission Grid — India
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # ── Save ──
    print(f"\n💾 Saving map to: {os.path.basename(OUTPUT_HTML)}")
    t2 = time.time()
    m.save(OUTPUT_HTML)
    file_size_mb = os.path.getsize(OUTPUT_HTML) / (1024 * 1024)
    print(f"   ✔ Saved! ({file_size_mb:.1f} MB) in {time.time()-t2:.1f}s")

    print(f"\n{'=' * 60}")
    print(f"  ✅ Done! Open this file in your browser:")
    print(f"     {OUTPUT_HTML}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
