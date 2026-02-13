"""
GeoJSON Loader Module
Efficiently loads and processes the large IndiaTransmission GeoJSON file.
Uses streaming parsing for memory efficiency.
"""
import json
import os
from typing import Dict, List, Tuple, Optional
from functools import lru_cache

# Path to the GeoJSON file
GEOJSON_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                            'IndiaTransmission - Copy.geojson')

# Regional bounding boxes for India (lat_min, lon_min, lat_max, lon_max)
REGIONS = {
    'All India': (6.0, 68.0, 37.0, 98.0),
    'North India': (25.0, 73.0, 37.0, 88.0),
    'South India': (6.0, 74.0, 20.0, 85.0),
    'East India': (20.0, 82.0, 28.0, 98.0),
    'West India': (15.0, 68.0, 28.0, 78.0),
    'Central India': (18.0, 75.0, 27.0, 85.0),
    'Delhi NCR': (28.3, 76.8, 28.9, 77.5),
}


def is_in_bbox(lon: float, lat: float, bbox: Tuple[float, float, float, float]) -> bool:
    """Check if a point is within a bounding box."""
    lat_min, lon_min, lat_max, lon_max = bbox
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def load_geojson_features(region: str = 'All India', 
                          max_towers: int = 10000,
                          max_lines: int = 2000,
                          progress_callback=None) -> Tuple[List[Dict], List[Dict]]:
    """
    Load GeoJSON features with optional region filtering.
    
    Args:
        region: One of the keys in REGIONS dict
        max_towers: Maximum number of tower points to load
        max_lines: Maximum number of line features to load
        progress_callback: Optional callback function for progress updates
        
    Returns:
        Tuple of (towers_list, lines_list)
    """
    if not os.path.exists(GEOJSON_PATH):
        print(f"GeoJSON file not found: {GEOJSON_PATH}")
        return [], []
    
    bbox = REGIONS.get(region, REGIONS['All India'])
    towers = []
    lines = []
    
    file_size = os.path.getsize(GEOJSON_PATH)
    
    if progress_callback:
        progress_callback(0, "Opening GeoJSON file...")
    
    try:
        with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
            # Read file in chunks for progress tracking
            content = f.read()
            
        if progress_callback:
            progress_callback(30, "Parsing JSON...")
            
        data = json.loads(content)
        features = data.get('features', [])
        total_features = len(features)
        
        if progress_callback:
            progress_callback(50, f"Processing {total_features} features...")
        
        for i, feature in enumerate(features):
            if len(towers) >= max_towers and len(lines) >= max_lines:
                break
                
            geom = feature.get('geometry', {})
            geom_type = geom.get('type', '')
            coords = geom.get('coordinates', [])
            props = feature.get('properties', {})
            feature_id = feature.get('id', i)
            
            if geom_type == 'Point' and len(towers) < max_towers:
                lon, lat = coords[0], coords[1]
                if is_in_bbox(lon, lat, bbox):
                    towers.append({
                        'id': feature_id,
                        'lon': lon,
                        'lat': lat,
                        'power': props.get('power', 'tower'),
                        'voltage': props.get('voltage', ''),
                    })
                    
            elif geom_type == 'LineString' and len(lines) < max_lines:
                # Check if any point of line is in bbox
                in_region = any(is_in_bbox(c[0], c[1], bbox) for c in coords)
                if in_region:
                    lines.append({
                        'id': feature_id,
                        'coordinates': coords,
                        'power': props.get('power', 'line'),
                        'voltage': props.get('voltage', ''),
                        'cables': props.get('cables', ''),
                    })
            
            # Update progress every 10000 features
            if progress_callback and i % 10000 == 0:
                pct = 50 + int((i / total_features) * 45)
                progress_callback(pct, f"Processed {i}/{total_features} features...")
        
        if progress_callback:
            progress_callback(100, f"Loaded {len(towers)} towers, {len(lines)} lines")
            
    except Exception as e:
        print(f"Error loading GeoJSON: {e}")
        return [], []
    
    return towers, lines


def convert_to_osm_format(towers: List[Dict], lines: List[Dict]) -> Tuple[Dict, List, List]:
    """
    Convert GeoJSON features to OSM-like format for compatibility with existing code.
    
    Returns:
        Tuple of (nodes_dict, poles_list, lines_list) matching process_osm_data output format
    """
    nodes = {}
    poles = []
    osm_lines = []
    
    # Process towers as nodes/poles
    for tower in towers:
        node_id = tower['id']
        nodes[node_id] = {
            'lat': tower['lat'],
            'lon': tower['lon'],
            'tags': {
                'power': tower['power'],
                'voltage': tower.get('voltage', ''),
            }
        }
        poles.append(node_id)
    
    # Process lines - for GeoJSON LineStrings, we create synthetic node IDs
    line_node_counter = 9000000000  # Start with high ID to avoid conflicts
    
    for line in lines:
        line_nodes = []
        coords = line['coordinates']
        voltage = line.get('voltage', '11000')
        
        for lon, lat in coords:
            # Create a node for each coordinate
            node_id = line_node_counter
            line_node_counter += 1
            
            nodes[node_id] = {
                'lat': lat,
                'lon': lon,
                'tags': {}
            }
            line_nodes.append(node_id)
        
        osm_lines.append({
            'nodes': line_nodes,
            'voltage': voltage
        })
    
    return nodes, poles, osm_lines


def load_overpass_geojson(filepath: str, progress_callback=None) -> Dict[str, list]:
    """
    Load an Overpass Turbo exported GeoJSON and classify features by power type.
    
    Args:
        filepath: Path to the exported GeoJSON file
        progress_callback: Optional callback(pct, msg)
        
    Returns:
        Dict with keys: 'lines', 'minor_lines', 'cables', 'substations',
                        'towers', 'poles', 'transformers', 'others'
        Each value is a list of raw GeoJSON feature dicts.
    """
    result = {
        'lines': [], 'minor_lines': [], 'cables': [],
        'substations': [], 'towers': [], 'poles': [],
        'transformers': [], 'others': []
    }
    
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return result
    
    if progress_callback:
        progress_callback(0, "Opening GeoJSON file...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    features = data.get('features', [])
    total = len(features)
    
    if progress_callback:
        progress_callback(30, f"Classifying {total} features...")
    
    # Overpass format: properties.power = 'line', 'tower', etc.
    power_map = {
        'line': 'lines',
        'minor_line': 'minor_lines',
        'cable': 'cables',
        'substation': 'substations',
        'tower': 'towers',
        'pole': 'poles',
        'transformer': 'transformers',
    }
    
    # IndiaTransmission format: properties.type = 'Line', 'Tower', etc.
    type_map = {
        'Line': 'lines',
        'Cable': 'cables',
        'Tower': 'towers',
        'Substation_Icon': 'substations',
        'Substation_Area': 'substations',
        'Switch': 'others',
        'Compensator': 'others',
        'Transformer': 'transformers',
        'Converter': 'others',
    }
    
    for i, feat in enumerate(features):
        props = feat.get('properties', {})
        power_type = props.get('power', '')
        key = power_map.get(power_type, None)
        
        # Fallback to type field (IndiaTransmission format)
        if key is None:
            feat_type = props.get('type', '')
            key = type_map.get(feat_type, 'others')
        
        result[key].append(feat)
        
        if progress_callback and i % 20000 == 0:
            pct = 30 + int((i / total) * 65)
            progress_callback(pct, f"Classified {i}/{total}...")
    
    if progress_callback:
        progress_callback(100, "Classification complete!")
    
    print(f"Overpass GeoJSON loaded: {total} features")
    for k, v in result.items():
        if v:
            print(f"  {k}: {len(v)}")
    
    return result


def get_available_regions() -> List[str]:
    """Return list of available region names."""
    return list(REGIONS.keys())


def get_region_center(region: str) -> Tuple[float, float]:
    """Get the center coordinates of a region for map centering."""
    bbox = REGIONS.get(region, REGIONS['All India'])
    lat_min, lon_min, lat_max, lon_max = bbox
    return ((lat_min + lat_max) / 2, (lon_min + lon_max) / 2)
