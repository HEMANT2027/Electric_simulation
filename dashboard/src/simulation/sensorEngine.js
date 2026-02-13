/**
 * Sensor Placement Engine
 * 
 * Implements the √n optimal sensor placement strategy.
 * Runs entirely client-side for real-time interaction.
 */

/**
 * DFS preorder traversal from source.
 */
function dfsPreorder(adj, source) {
    const visited = new Set();
    const order = [];
    const stack = [source];

    while (stack.length > 0) {
        const node = stack.pop();
        if (visited.has(node)) continue;
        visited.add(node);
        order.push(node);

        const neighbors = (adj.get(node) || []).map(n => n.to);
        // Reverse so we process in consistent order
        for (let i = neighbors.length - 1; i >= 0; i--) {
            if (!visited.has(neighbors[i])) {
                stack.push(neighbors[i]);
            }
        }
    }
    return order;
}

/**
 * Place √n sensors using DFS ordering.
 * @param {Map} adj - adjacency list
 * @param {number} source - ext_grid bus
 * @returns {{ sensors: number[], blocks: number[][] }}
 */
export function placeSensorsSqrtN(adj, source) {
    const ordering = dfsPreorder(adj, source);
    const n = ordering.length;
    if (n === 0) return { sensors: [], blocks: [] };

    const k = Math.ceil(Math.sqrt(n));
    const blocks = [];
    for (let i = 0; i < n; i += k) {
        blocks.push(ordering.slice(i, i + k));
    }

    const sensors = blocks.map(block => block[block.length - 1]);

    return { sensors, blocks };
}

/**
 * Read sensor status from energized map.
 * @returns {Map<number, number>} sensorBus -> 0|1
 */
export function readSensors(sensors, energizedStatus) {
    const readings = new Map();
    for (const s of sensors) {
        readings.set(s, energizedStatus.get(s) || 0);
    }
    return readings;
}

/**
 * Find the first dead sensor's block index.
 * @returns {number} block index or -1
 */
export function identifyFaultyBlock(sensors, sensorReadings) {
    for (let i = 0; i < sensors.length; i++) {
        if ((sensorReadings.get(sensors[i]) || 0) === 0) {
            return i;
        }
    }
    return -1;
}
