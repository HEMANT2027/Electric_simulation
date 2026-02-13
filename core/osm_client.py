import requests

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
