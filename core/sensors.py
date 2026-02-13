"""
Sensor Placement Module
========================
Implements the √n optimal sensor placement strategy on GridNetwork.

Algorithm:
  1. DFS traversal from the ext_grid (power source)
  2. Divide the ordering into blocks of size √n
  3. Place one sensor at the END of each block
  4. The first sensor that reads DEAD identifies the faulty block
"""

import math
import networkx as nx
from typing import List, Tuple, Dict


def place_sensors_sqrt_n(grid) -> Tuple[List[int], List[List[int]]]:
    """
    Place √n sensors on the grid using DFS ordering from the power source.
    
    Args:
        grid: A GridNetwork with ext_grid_bus defined
        
    Returns:
        (sensors, blocks) where:
          - sensors: list of bus IDs where sensors are placed
          - blocks: list of lists, each block containing bus IDs in DFS order
    """
    if grid.ext_grid_bus < 0:
        print("ERROR: No power source in the grid!")
        return [], []
    
    # Use the full graph for DFS ordering (all edges, not just in-service)
    ordering = list(nx.dfs_preorder_nodes(grid.G, source=grid.ext_grid_bus))
    n = len(ordering)
    
    if n == 0:
        return [], []
    
    k = math.ceil(math.sqrt(n))
    
    # Divide into blocks of size k
    blocks = []
    for i in range(0, n, k):
        blocks.append(ordering[i:i + k])
    
    # Place sensor at the LAST bus of each block
    sensors = [block[-1] for block in blocks]
    
    print(f"√n Sensor Placement:")
    print(f"  Total buses (n): {n}")
    print(f"  Block size (√n): {k}")
    print(f"  Num blocks:      {len(blocks)}")
    print(f"  Sensors placed:  {len(sensors)}")
    
    return sensors, blocks


def read_sensors(sensors: List[int],
                 energized_status: Dict[int, int]) -> Dict[int, int]:
    """
    Read the status of each sensor.
    
    Returns:
        Dict mapping sensor bus_id -> 1 (live) or 0 (dead)
    """
    return {s: energized_status.get(s, 0) for s in sensors}


def identify_faulty_block(sensor_readings: Dict[int, int],
                          sensors: List[int],
                          blocks: List[List[int]]) -> int:
    """
    Identify which block contains the fault by finding the FIRST dead sensor.
    
    Returns:
        Index of the faulty block (-1 if no fault detected)
    """
    for i, sensor_bus in enumerate(sensors):
        if sensor_readings.get(sensor_bus, 1) == 0:
            return i
    return -1


def get_sensor_summary(sensors: List[int], sensor_readings: Dict[int, int],
                       blocks: List[List[int]], faulty_block_idx: int) -> str:
    """Generate a human-readable summary of sensor status."""
    lines = []
    lines.append("=" * 55)
    lines.append("  SENSOR STATUS REPORT")
    lines.append("=" * 55)
    
    live_count = sum(1 for v in sensor_readings.values() if v == 1)
    dead_count = sum(1 for v in sensor_readings.values() if v == 0)
    
    lines.append(f"  Total sensors: {len(sensors)}")
    lines.append(f"  Live sensors:  {live_count} 🟢")
    lines.append(f"  Dead sensors:  {dead_count} 🔴")
    lines.append("")
    
    for i, sensor_bus in enumerate(sensors):
        status = "🟢 LIVE" if sensor_readings.get(sensor_bus, 0) == 1 else "🔴 DEAD"
        block_size = len(blocks[i]) if i < len(blocks) else 0
        marker = " ◀ FAULT BLOCK" if i == faulty_block_idx else ""
        lines.append(f"  S{i+1:3d} (Bus {sensor_bus:6d}) | "
                     f"Block: {block_size:4d} buses | {status}{marker}")
    
    if faulty_block_idx >= 0:
        lines.append("")
        lines.append(f"  ⚠️  FAULT DETECTED in Block {faulty_block_idx + 1}")
        lines.append(f"     Block contains {len(blocks[faulty_block_idx])} buses")
    else:
        lines.append("")
        lines.append("  ✅ No faults detected — all sensors report LIVE")
    
    lines.append("=" * 55)
    return "\n".join(lines)
