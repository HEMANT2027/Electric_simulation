/**
 * Grid Simulation Engine
 * 
 * Client-side graph simulation using BFS/DFS.
 * Builds an adjacency list from line data and computes
 * energization status via graph reachability.
 */

/**
 * Build adjacency list from line data.
 * @param {Array} lines - [[idx, from, to, kv, name], ...]
 * @returns {Map<number, Array<{to: number, lineIdx: number}>>}
 */
export function buildAdjacencyList(lines) {
    const adj = new Map();
    for (const [idx, from, to] of lines) {
        if (!adj.has(from)) adj.set(from, []);
        if (!adj.has(to)) adj.set(to, []);
        adj.get(from).push({ to, lineIdx: idx });
        adj.get(to).push({ to: from, lineIdx: idx });
    }
    return adj;
}

/**
 * BFS from source through active edges only.
 * @param {Map} adj - adjacency list
 * @param {number} source - source bus ID
 * @param {Set<number>} disabledLines - set of faulted line indices
 * @returns {Set<number>} reachable bus IDs
 */
export function bfsFromSource(adj, source, disabledLines) {
    const visited = new Set();
    const queue = [source];
    visited.add(source);

    while (queue.length > 0) {
        const current = queue.shift();
        const neighbors = adj.get(current) || [];
        for (const { to, lineIdx } of neighbors) {
            if (!visited.has(to) && !disabledLines.has(lineIdx)) {
                visited.add(to);
                queue.push(to);
            }
        }
    }
    return visited;
}

/**
 * Get energized status for all buses.
 * @returns {Map<number, number>} busId -> 1 (live) or 0 (dead)
 */
export function getEnergizedStatus(adj, source, disabledLines, allBuses) {
    const reachable = bfsFromSource(adj, source, disabledLines);
    const status = new Map();
    for (const busId of allBuses) {
        status.set(busId, reachable.has(busId) ? 1 : 0);
    }
    return status;
}

/**
 * Find bridge edges using Tarjan's algorithm.
 * Handles multigraphs (parallel lines) by tracking edge IDs.
 */
export function findBridges(adj, lines) {
    const visited = new Set();
    const disc = new Map();
    const low = new Map();
    const bridges = [];
    let timer = 0;

    function dfs(u, parentLineIdx) {
        visited.add(u);
        disc.set(u, timer);
        low.set(u, timer);
        timer++;

        const neighbors = adj.get(u) || [];
        for (const { to: v, lineIdx } of neighbors) {
            if (lineIdx === parentLineIdx) continue; // Don't go back up the same edge

            if (visited.has(v)) {
                low.set(u, Math.min(low.get(u), disc.get(v)));
            } else {
                dfs(v, lineIdx);
                low.set(u, Math.min(low.get(u), low.get(v)));
                if (low.get(v) > disc.get(u)) {
                    bridges.push(lineIdx);
                }
            }
        }
    }

    // Start from first node
    const firstNode = adj.keys().next().value;
    if (firstNode !== undefined) {
        dfs(firstNode, -1);
    }

    return bridges;
}

/**
 * Find a good bridge fault — one that disconnects ~5-15% of buses.
 */
export function findGoodBridgeFault(adj, source, lines, allBuses) {
    const rawBridges = findBridges(adj, lines);
    if (rawBridges.length === 0) return null;

    // Filter out bridges that don't actually disconnect (double check)
    // or that only disconnect the leaf itself (if we want bigger impact)
    const totalBuses = allBuses.length;
    const targetDisconnect = Math.floor(totalBuses * 0.10); // Aim for 10%

    let bestLine = null;
    let bestDiff = Infinity;
    let foundAny = false;

    // Prioritize bridges with significant impact
    // Random sample to keep it fast
    const sample = rawBridges.length > 50
        ? rawBridges.sort(() => Math.random() - 0.5).slice(0, 50)
        : rawBridges;

    for (const lineIdx of sample) {
        const disabled = new Set([lineIdx]);
        const reachable = bfsFromSource(adj, source, disabled);
        const disconnected = totalBuses - reachable.size;

        // Must disconnect at least 1 node
        if (disconnected > 0) {
            foundAny = true;
            const diff = Math.abs(disconnected - targetDisconnect);
            if (diff < bestDiff) {
                bestDiff = diff;
                bestLine = lineIdx;
            }
        }
    }

    // If we found a bridge with impact, return it.
    // Otherwise fallback to first raw bridge (maybe it disconnects just 1 node)
    return bestLine !== null ? bestLine : (foundAny ? rawBridges[0] : null);
}
