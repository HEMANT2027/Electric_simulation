from core.osm_client import fetch_osm_data
from core.data_processor import process_osm_data
from core.grid_manager import build_network, sort_buses_linearly
from core.power_flow import simulate_fault
from core.sensors import apply_sensor_strategy
from core.visualizer import create_plotly_map

def main():
    print("=== Smart Grid Simulator (Modular) ===")
    
    # 1. Fetch Data
    osm_data = fetch_osm_data()
    if not osm_data:
        print("Required data not found. Exiting.")
        return

    nodes, poles, lines = process_osm_data(osm_data)
    if not poles:
        print("No poles found in data. Exiting.")
        return
        
    # 2. Build Network
    net = build_network(nodes, poles, lines)
    if len(net.bus) == 0:
        return

    # 3. Sort Poles
    sorted_buses = sort_buses_linearly(net)
    print(f"Sorted {len(sorted_buses)} buses for sensor placement.")
    
    # 4. Simulate Fault
    fault_idx = simulate_fault(net)
    if fault_idx is not None:
        print(f"Simulated fault on Line Index: {fault_idx}")
    else:
        print("Could not simulate fault/power flow.")
        
    # 5. Apply Sensors
    sensors, blocks, faulty_block_idx = apply_sensor_strategy(net, sorted_buses)
    
    # 6. Visualize (This function returns a fig, need to show or save it)
    # For CLI, we might skip full visualization or just save generic HTML
    # We can perform a simplified check or use the visualizer to save html manually
    print("Simulation complete. Use 'streamlit run app.py' for interactive visualization.")

if __name__ == "__main__":
    main()
