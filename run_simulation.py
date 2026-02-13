"""
Run Simulation — Main Orchestrator
====================================
Executes the full grid simulation workflow step-by-step:

    Step 1: Load GeoJSON → Build Grid
    Step 2: Energize Grid → All lines alive
    Step 3: Place √n Sensors → Show sensor positions
    Step 4: Trigger Fault → A line is cut
    Step 5: Read Sensors → Downstream sensors go DEAD, identify faulty block

Each step generates an HTML map in sim_output/.

Usage:
    python run_simulation.py
    python run_simulation.py --max-lines 2000
    python run_simulation.py --fault-line 42
"""

import os
import sys
import time
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from core.geojson_loader import load_overpass_geojson
from core.grid_builder import build_grid_from_geojson
from core.power_flow import (
    energize_grid, trigger_fault, trigger_random_fault,
    find_bridge_fault, get_energized_status
)
from core.sensors import (
    place_sensors_sqrt_n, read_sensors,
    identify_faulty_block, get_sensor_summary
)
from core.sim_visualizer import render_simulation_map

GEOJSON_FILE = os.path.join(os.path.dirname(__file__), "export (1).geojson")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "sim_output")


def banner(step: int, title: str):
    print()
    print("=" * 60)
    print(f"  STEP {step}: {title}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Grid Simulation Runner")
    parser.add_argument("--max-lines", type=int, default=4200,
                        help="Max transmission lines to load (default: 4200)")
    parser.add_argument("--fault-line", type=int, default=None,
                        help="Specific line index to fault (default: random)")
    parser.add_argument("--geojson", type=str, default=GEOJSON_FILE,
                        help="Path to GeoJSON file")
    args = parser.parse_args()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║       ⚡ GRID SIMULATION — √n SENSOR ALGORITHM ⚡       ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  GeoJSON:    {os.path.basename(args.geojson)}")
    print(f"  Max Lines:  {args.max_lines}")
    print(f"  Output Dir: {OUTPUT_DIR}")
    
    t_start = time.time()
    
    # ═══════════════════════════════════════
    # STEP 1: Load GeoJSON → Build Grid
    # ═══════════════════════════════════════
    banner(1, "LOAD GEOJSON & BUILD GRID")
    
    t1 = time.time()
    classified = load_overpass_geojson(args.geojson)
    
    if not classified['lines']:
        print("ERROR: No transmission lines found!")
        sys.exit(1)
    
    grid = build_grid_from_geojson(classified, max_lines=args.max_lines)
    
    if grid.num_buses == 0:
        print("ERROR: Grid has no buses!")
        sys.exit(1)
    
    print(f"\n✔ Grid built in {time.time()-t1:.1f}s")
    print(f"  Buses: {grid.num_buses}")
    print(f"  Lines: {grid.num_lines}")
    
    # All lines de-energized initially
    status_off = {b: 0 for b in grid.G.nodes()}
    render_simulation_map(
        grid, status_off,
        step_name="sim_step_1_grid_loaded",
        output_dir=OUTPUT_DIR,
        title="Step 1: Grid Loaded (De-energized)"
    )
    
    # ═══════════════════════════════════════
    # STEP 2: Energize Grid
    # ═══════════════════════════════════════
    banner(2, "ENERGIZE GRID")
    
    energize_grid(grid)
    status_on = get_energized_status(grid)
    
    live_count = sum(1 for v in status_on.values() if v == 1)
    print(f"  {live_count}/{len(status_on)} buses energized")
    
    render_simulation_map(
        grid, status_on,
        step_name="sim_step_2_energized",
        output_dir=OUTPUT_DIR,
        title="Step 2: Grid Energized ⚡"
    )
    
    # ═══════════════════════════════════════
    # STEP 3: Place √n Sensors
    # ═══════════════════════════════════════
    banner(3, "PLACE √n SENSORS")
    
    sensors, blocks = place_sensors_sqrt_n(grid)
    
    if not sensors:
        print("ERROR: No sensors placed!")
        sys.exit(1)
    
    sensor_readings_ok = read_sensors(sensors, status_on)
    
    render_simulation_map(
        grid, status_on,
        sensors=sensors,
        sensor_readings=sensor_readings_ok,
        blocks=blocks,
        step_name="sim_step_3_sensors_placed",
        output_dir=OUTPUT_DIR,
        title=f"Step 3: {len(sensors)} Sensors Placed (√n)"
    )
    
    # ═══════════════════════════════════════
    # STEP 4: Trigger Fault
    # ═══════════════════════════════════════
    banner(4, "TRIGGER FAULT")
    
    if args.fault_line is not None:
        fault_info = trigger_fault(grid, args.fault_line)
    else:
        # Use bridge fault — guaranteed to disconnect downstream buses
        fault_info = find_bridge_fault(grid, seed=42)
    
    if not fault_info:
        print("ERROR: Failed to trigger fault!")
        sys.exit(1)
    
    status_fault = get_energized_status(grid)
    
    live_after = sum(1 for v in status_fault.values() if v == 1)
    dead_after = sum(1 for v in status_fault.values() if v == 0)
    print(f"  After fault: {live_after} live, {dead_after} dead")
    
    render_simulation_map(
        grid, status_fault,
        sensors=sensors,
        sensor_readings=read_sensors(sensors, status_fault),
        blocks=blocks,
        fault_info=fault_info,
        step_name="sim_step_4_fault_triggered",
        output_dir=OUTPUT_DIR,
        title="Step 4: Fault Triggered 💥"
    )
    
    # ═══════════════════════════════════════
    # STEP 5: Read Sensors & Identify Fault
    # ═══════════════════════════════════════
    banner(5, "SENSOR READINGS & FAULT IDENTIFICATION")
    
    sensor_readings_fault = read_sensors(sensors, status_fault)
    faulty_block_idx = identify_faulty_block(sensor_readings_fault, sensors, blocks)
    
    report = get_sensor_summary(sensors, sensor_readings_fault, blocks, faulty_block_idx)
    print(report)
    
    render_simulation_map(
        grid, status_fault,
        sensors=sensors,
        sensor_readings=sensor_readings_fault,
        blocks=blocks,
        fault_info=fault_info,
        faulty_block_idx=faulty_block_idx,
        step_name="sim_step_5_fault_identified",
        output_dir=OUTPUT_DIR,
        title=f"Step 5: Fault in Block {faulty_block_idx + 1} 🔍"
    )
    
    # ═══════════════════════════════════════
    # DONE
    # ═══════════════════════════════════════
    total_time = time.time() - t_start
    
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║              ✅ SIMULATION COMPLETE                      ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Total time:       {total_time:.1f}s")
    print(f"  Grid:             {grid.num_buses} buses, {grid.num_lines} edges")
    print(f"  Sensors placed:   {len(sensors)}")
    print(f"  Fault on line:    {fault_info.get('line_idx', '?')}")
    print(f"  Faulty block:     {faulty_block_idx + 1 if faulty_block_idx >= 0 else 'None'}")
    print()
    print("  📂 Output files:")
    for f in sorted(os.listdir(OUTPUT_DIR)):
        if f.endswith('.html'):
            fpath = os.path.join(OUTPUT_DIR, f)
            fsize = os.path.getsize(fpath) / (1024 * 1024)
            print(f"     • {f} ({fsize:.1f} MB)")
    print()
    print("  Open any HTML file in your browser to explore!")


if __name__ == "__main__":
    main()
