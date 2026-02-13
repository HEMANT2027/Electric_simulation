import plotly.graph_objects as go
import re

def get_voltage_color(voltage_kv):
    """
    User requested high contrast: Yellow, Blue, Red etc.
    """
    if voltage_kv < 11: 
        return '#00E5FF' # Cyan (LT)
    if voltage_kv == 11: 
        return '#2979FF' # Blue (HT)
    if voltage_kv == 33: 
        return '#FFC400' # Amber/Yellow (EHT)
    if voltage_kv > 33: 
        return '#FF1744' # Red (Transmission)
    return '#9E9E9E'     # Gray (Unknown)

def get_line_voltage(name):
    try:
        return float(re.findall(r"_([\d.]+)kV", name)[0])
    except:
        return 11.0

def create_plotly_map(net, energized_status, fault_line_idx, sensors):
    # Base Coords
    bus_x = net.bus.geo.apply(lambda x: x[0]).tolist()
    bus_y = net.bus.geo.apply(lambda x: x[1]).tolist()
    
    fig = go.Figure()

    # 1. LINES
    # Group by Voltage and Status (Energized vs De-energized)
    
    # We iterate and build lists for efficiency, but for different colors we need different traces
    # or a single trace with custom colors (Plotly support for custom line colors in one trace is tricky for segments).
    # We will group by (Voltage, IsEnergized).
    
    line_groups = {} # Key: (volts, is_live) -> ([x], [y])
    
    off_lines_x = []
    off_lines_y = []
    
    # Pre-process Fault Line (to color it Red specifically if we want, or just dead)
    # If fault_line_idx is set, that line is BROKEN.
    
    for idx, row in net.line.iterrows():
        try:
            fb = net.bus.loc[row.from_bus]
            tb = net.bus.loc[row.to_bus]
            
            xs = [fb.geo[0], tb.geo[0], None]
            ys = [fb.geo[1], tb.geo[1], None]
            
            # Check if this is the faulty line itself
            if fault_line_idx is not None and idx == fault_line_idx:
                # Plot as Broken/Red/Flashy? 
                # We'll add a specific trace for the fault location later.
                # For the line itself, it's effectively open, so maybe dashed red.
                label = (999, False) # Special key
            else:
                volts = get_line_voltage(row['name'])
                
                # Check energization
                # Both ends must be energized for the line to be "live" flowing
                is_live = (energized_status.get(row.from_bus, 0) == 1 and 
                           energized_status.get(row.to_bus, 0) == 1)
                
                label = (volts, is_live)

            if label not in line_groups:
                line_groups[label] = ([], [])
            line_groups[label][0].extend(xs)
            line_groups[label][1].extend(ys)
            
        except:
            pass
            
    # Plot Groups
    for (volts, is_live), (gx, gy) in line_groups.items():
        if volts == 999: # Fault Line
            fig.add_trace(go.Scattermapbox(
                lon=gx, lat=gy,
                mode='lines',
                line=dict(width=4, color='red'),
                name='FAULTED LINE',
                hoverinfo='text',
                text='FAULT LOCATION'
            ))
            continue
            
        if is_live:
            color = get_voltage_color(volts)
            op = 1.0
            width = 3 if volts >= 33 else 2
            name = f"{volts}kV (Live)"
        else:
            color = '#424242' # Dark Gray
            op = 0.5
            width = 2
            name = f"{volts}kV (Dead)"
            
        fig.add_trace(go.Scattermapbox(
            lon=gx, lat=gy,
            mode='lines',
            line=dict(width=width, color=color),
            opacity=op,
            name=name,
            hoverinfo='none' # Reduce clutter
        ))

    # 2. POLES (Buses)
    # Color active vs inactive poles
    
    bus_x_live = []
    bus_y_live = []
    bus_x_dead = []
    bus_y_dead = []
    
    for b in net.bus.index:
        geo = net.bus.loc[b, 'geo']
        if energized_status.get(b, 0) == 1:
            bus_x_live.append(geo[0])
            bus_y_live.append(geo[1])
        else:
            bus_x_dead.append(geo[0])
            bus_y_dead.append(geo[1])
            
    fig.add_trace(go.Scattermapbox(
        lon=bus_x_dead, lat=bus_y_dead,
        mode='markers',
        marker=dict(size=5, color='#B0BEC5'),
        name='Poles (De-energized)'
    ))
    
    fig.add_trace(go.Scattermapbox(
        lon=bus_x_live, lat=bus_y_live,
        mode='markers',
        marker=dict(size=6, color='#000000'), 
        name='Poles (Energized)'
    ))

    # 3. SENSORS
    if sensors:
        s_x = []
        s_y = []
        s_colors = []
        s_text = []
        
        for s in sensors:
            if s in net.bus.index:
                geo = net.bus.loc[s, 'geo']
                s_x.append(geo[0])
                s_y.append(geo[1])
                
                # Check status
                is_live = energized_status.get(s, 0) == 1
                s_colors.append('#00E676' if is_live else '#FF1744') # Green if OK, Red if Dead
                s_text.append(f"Sensor {s}: {'LIVE' if is_live else 'NO POWER'}")
        
        fig.add_trace(go.Scattermapbox(
            lon=s_x, lat=s_y,
            mode='markers',
            marker=dict(size=14, color=s_colors, symbol='circle'),
            text=s_text,
            name='Sensors'
        ))

    # 4. SUBSTATION
    if len(net.ext_grid) > 0:
        sub_bus = net.ext_grid.bus.iloc[0]
        geo = net.bus.loc[sub_bus, 'geo']
        fig.add_trace(go.Scattermapbox(
            lon=[geo[0]], lat=[geo[1]],
            mode='markers',
            marker=dict(size=18, color='#6200EA', symbol='star'),
            name='Substation'
        ))

    # LAYOUT
    center_lat = sum(bus_y)/len(bus_y) if bus_y else 28.61
    center_lon = sum(bus_x)/len(bus_x) if bus_x else 77.20
    
    fig.update_layout(
        mapbox=dict(
            style="carto-positron", # Light UI
            center=dict(lat=center_lat, lon=center_lon),
            zoom=14
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            bgcolor="rgba(255,255,255,0.8)",
            font=dict(color="black")
        ),
        height=700
    )
    
    return fig
