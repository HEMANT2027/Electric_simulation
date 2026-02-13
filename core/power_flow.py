"""
Fault Engine / Power Flow Module
==================================
Handles grid energization, fault injection, and connectivity-based
energization status computation.

Works with the lightweight GridNetwork from grid_builder.py.
Energization = graph reachability from the ext_grid source.
"""

import networkx as nx
import numpy as np
from typing import Dict, Set, Optional, List


def energize_grid(grid) -> None:
    """Energize the entire grid: set all lines to in_service."""
    for line in grid.line_list:
        line['in_service'] = True
    print(f"⚡ Grid ENERGIZED — {len(grid.line_list)} lines in service")


def trigger_fault(grid, line_idx: int) -> dict:
    """
    Trigger a fault on a specific line by taking it out of service.
    
    Returns:
        Dict with fault info
    """
    if line_idx < 0 or line_idx >= len(grid.line_list):
        print(f"ERROR: Line index {line_idx} out of range!")
        return {}
    
    line = grid.line_list[line_idx]
    line['in_service'] = False
    
    fault_info = {
        'line_idx': line_idx,
        'from_bus': line['from_bus'],
        'to_bus': line['to_bus'],
        'line_name': line['name'],
        'voltage_kv': line['voltage_kv'],
    }
    
    print(f"💥 FAULT triggered on Line {line_idx}: {line['name']}")
    print(f"   From bus {line['from_bus']} → To bus {line['to_bus']}")
    print(f"   Voltage: {line['voltage_kv']} kV")
    
    return fault_info


def trigger_random_fault(grid, seed: int = None) -> dict:
    """Trigger a fault on a random in-service line."""
    in_service = [i for i, l in enumerate(grid.line_list) if l['in_service']]
    if not in_service:
        print("ERROR: No in-service lines to fault!")
        return {}
    
    if seed is not None:
        np.random.seed(seed)
    
    line_idx = np.random.choice(in_service)
    return trigger_fault(grid, line_idx)


def find_bridge_fault(grid, seed: int = None) -> dict:
    """
    Find and trigger a fault on a BRIDGE edge — an edge whose removal
    disconnects the graph. This guarantees that the fault will actually
    cause downstream buses to go dead, which is needed to demonstrate
    the √n sensor fault detection.
    
    Falls back to random fault if no bridges found.
    
    Returns:
        Dict with fault info
    """
    print("🔍 Searching for bridge edges (critical lines)...")
    
    # Find all bridges in the graph
    bridges = list(nx.bridges(grid.G))
    
    if not bridges:
        print("  No bridges found — grid is fully redundant. Using random fault.")
        return trigger_random_fault(grid, seed)
    
    print(f"  Found {len(bridges)} bridge edges")
    
    # Among bridges, find ones that disconnect a significant number of buses
    # (not just leaf nodes) — aim for ~5-20% of buses disconnected
    if seed is not None:
        np.random.seed(seed)
    
    best_fault_idx = -1
    best_disconnect_count = 0
    target_pct = 0.10  # Target ~10% disconnection
    target_count = int(grid.num_buses * target_pct)
    
    # Sample up to 50 bridges to check
    sample_bridges = bridges
    if len(bridges) > 50:
        indices = np.random.choice(len(bridges), 50, replace=False)
        sample_bridges = [bridges[i] for i in indices]
    
    for u, v in sample_bridges:
        # Find this edge in line_list
        for i, line in enumerate(grid.line_list):
            if ((line['from_bus'] == u and line['to_bus'] == v) or
                (line['from_bus'] == v and line['to_bus'] == u)):
                
                # Temporarily remove edge to count disconnected buses
                grid.G.remove_edge(u, v)
                try:
                    reachable = set(nx.descendants(grid.G, grid.ext_grid_bus)) | {grid.ext_grid_bus}
                    disconnected = grid.num_buses - len(reachable)
                except Exception:
                    disconnected = 0
                grid.G.add_edge(u, v)  # Restore
                
                # Pick the one closest to target_count
                if abs(disconnected - target_count) < abs(best_disconnect_count - target_count):
                    best_disconnect_count = disconnected
                    best_fault_idx = i
                
                break
    
    if best_fault_idx >= 0:
        print(f"  Selected bridge fault: line {best_fault_idx}")
        print(f"  Expected disconnection: ~{best_disconnect_count} buses "
              f"({100*best_disconnect_count/grid.num_buses:.1f}%)")
        return trigger_fault(grid, best_fault_idx)
    
    # Fallback to first bridge
    u, v = bridges[0]
    for i, line in enumerate(grid.line_list):
        if ((line['from_bus'] == u and line['to_bus'] == v) or
            (line['from_bus'] == v and line['to_bus'] == u)):
            return trigger_fault(grid, i)
    
    return trigger_random_fault(grid, seed)


def get_energized_status(grid) -> Dict[int, int]:
    """
    Determine which buses are energized based on graph connectivity
    from the ext_grid source through IN-SERVICE lines only.
    
    Returns:
        Dict mapping bus_id -> 1 (energized) or 0 (de-energized)
    """
    active_graph = grid.get_active_graph()
    
    start_bus = grid.ext_grid_bus
    if start_bus < 0 or start_bus not in active_graph:
        return {b: 0 for b in grid.G.nodes()}
    
    try:
        reachable = set(nx.descendants(active_graph, start_bus)) | {start_bus}
    except Exception:
        reachable = set()
    
    status = {}
    for bus in grid.G.nodes():
        status[bus] = 1 if bus in reachable else 0
    
    live = sum(1 for v in status.values() if v == 1)
    dead = sum(1 for v in status.values() if v == 0)
    print(f"Energization: {live} live, {dead} dead (out of {len(status)})")
    
    return status


def get_dead_buses(status: Dict[int, int]) -> Set[int]:
    """Return set of bus IDs that are de-energized."""
    return {b for b, s in status.items() if s == 0}
