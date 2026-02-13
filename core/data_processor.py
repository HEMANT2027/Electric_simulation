def process_osm_data(data):
    """
    Process OSM data into lists of poles and lines.
    """
    if not data:
        return [], [], []
        
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


def process_geojson_data(towers, geojson_lines):
    """
    Process GeoJSON tower and line data into OSM-like format.
    
    Args:
        towers: List of tower dicts with 'id', 'lat', 'lon', 'power', 'voltage'
        geojson_lines: List of line dicts with 'id', 'coordinates', 'voltage'
        
    Returns:
        Tuple of (nodes_dict, poles_list, lines_list) matching OSM format
    """
    nodes = {}
    poles = []
    lines = []
    
    # Process towers
    for tower in towers:
        node_id = tower['id']
        nodes[node_id] = {
            'lat': tower['lat'],
            'lon': tower['lon'],
            'tags': {
                'power': tower.get('power', 'tower'),
                'voltage': tower.get('voltage', ''),
            }
        }
        poles.append(node_id)
    
    # Process lines - create nodes for each coordinate
    line_node_counter = 9000000000
    
    for line in geojson_lines:
        line_nodes = []
        coords = line.get('coordinates', [])
        voltage = line.get('voltage', '11000')
        
        for coord in coords:
            lon, lat = coord[0], coord[1]
            node_id = line_node_counter
            line_node_counter += 1
            
            nodes[node_id] = {
                'lat': lat,
                'lon': lon,
                'tags': {}
            }
            line_nodes.append(node_id)
        
        if line_nodes:
            lines.append({
                'nodes': line_nodes,
                'voltage': voltage
            })
    
    return nodes, poles, lines

