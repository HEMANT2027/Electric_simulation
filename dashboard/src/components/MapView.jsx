import React, { useEffect, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, useMap, CircleMarker, Polyline, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const TILES = {
    dark: {
        url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        attr: '&copy; CartoDB'
    },
    light: {
        url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        attr: '&copy; CartoDB'
    },
    satellite: {
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr: '&copy; Esri'
    }
};

const VOLTAGE_COLORS = {
    800: '#FF0040',
    765: '#FF1744',
    400: '#FF6D00',
    345: '#FF9100',
    230: '#FFEA00',
    220: '#FFD600',
    132: '#76FF03',
    110: '#00E676',
    66: '#00B0FF',
    33: '#2979FF',
    22: '#7C4DFF',
    11: '#AA00FF',
};

function getVoltageColor(kv) {
    if (kv >= 765) return VOLTAGE_COLORS[765];
    if (kv >= 400) return VOLTAGE_COLORS[400];
    if (kv >= 220) return VOLTAGE_COLORS[220];
    if (kv >= 132) return VOLTAGE_COLORS[132];
    if (kv >= 110) return VOLTAGE_COLORS[110];
    if (kv >= 66) return VOLTAGE_COLORS[66];
    if (kv >= 33) return VOLTAGE_COLORS[33];
    if (kv >= 22) return VOLTAGE_COLORS[22];
    if (kv >= 11) return VOLTAGE_COLORS[11];
    return '#666666';
}

// Component to dynamically change tile layer
function TileLayerSwitcher({ tileLayer }) {
    const map = useMap();
    const tileRef = useRef(null);

    useEffect(() => {
        if (tileRef.current) {
            map.removeLayer(tileRef.current);
        }
        const L = window.L || require('leaflet');
        const tileConfig = TILES[tileLayer] || TILES.dark;
        const layer = L.tileLayer(tileConfig.url, {
            attribution: tileConfig.attr,
            maxZoom: 19,
        });
        layer.addTo(map);
        tileRef.current = layer;

        return () => {
            if (tileRef.current) map.removeLayer(tileRef.current);
        };
    }, [tileLayer, map]);

    return null;
}

// Render transmission lines
function LineLayer({ gridData, simState, busGeoMap, isolateFault, onTriggerFault }) {
    const { energized, energizedStatus, faultInfo } = simState;

    return useMemo(() => {
        if (!gridData) return null;
        const lines = gridData.lines;
        const elements = [];

        for (let i = 0; i < lines.length; i++) {
            const [idx, fromBus, toBus, kv] = lines[i];
            const fromGeo = busGeoMap.get(fromBus);
            const toGeo = busGeoMap.get(toBus);
            if (!fromGeo || !toGeo) continue;

            const isFaulted = faultInfo && faultInfo.lineIdx === idx;

            // If isolation mode is on, skip non-faulted lines
            if (isolateFault && !isFaulted) continue;

            let color = '#333';
            let weight = 1;
            let opacity = 0.4;
            let dashArray = null;

            if (isFaulted) {
                color = '#FF0000';
                weight = 3;
                opacity = 1;
                dashArray = '8 4';
            } else if (energized) {
                const fromLive = energizedStatus ? (energizedStatus.get(fromBus) || 0) : 1;
                const toLive = energizedStatus ? (energizedStatus.get(toBus) || 0) : 1;
                if (fromLive && toLive) {
                    color = getVoltageColor(kv);
                    weight = kv >= 220 ? 2 : 1;
                    opacity = 0.7;
                } else {
                    color = '#2a2a2a';
                    weight = 1;
                    opacity = 0.3;
                }
            }

            elements.push(
                <Polyline
                    key={idx}
                    positions={[[fromGeo[1], fromGeo[0]], [toGeo[1], toGeo[0]]]}
                    pathOptions={{ color, weight, opacity, dashArray }}
                    eventHandlers={{
                        click: () => {
                            if (onTriggerFault) onTriggerFault(idx);
                        }
                    }}
                >
                    <Tooltip sticky>
                        <div style={{ fontSize: '12px', fontFamily: 'Inter, sans-serif' }}>
                            <strong>Line {idx}</strong><br />
                            {isFaulted ? <span style={{ color: '#FF1744' }}>⚠️ FAULTED</span> : <span>{kv} kV</span>}<br />
                            Bus {fromBus} ➝ Bus {toBus}
                            {!isFaulted && <div style={{ marginTop: 4, fontSize: 10, color: '#aaa' }}>(Click to fault)</div>}
                        </div>
                    </Tooltip>
                </Polyline>
            );
        }

        return <>{elements}</>;
    }, [gridData, energized, energizedStatus, faultInfo, busGeoMap, isolateFault, onTriggerFault]);
}

// Render tower markers
function TowerLayer({ gridData }) {
    if (!gridData || !gridData.towers) return null;
    return (
        <>
            {gridData.towers.map(([lon, lat], i) => (
                <CircleMarker
                    key={`t${i}`}
                    center={[lat, lon]}
                    radius={3}
                    pathOptions={{ color: '#666', fillColor: '#888', fillOpacity: 0.6, weight: 1 }}
                >
                    <Tooltip>
                        Tower<br />
                        {lat.toFixed(4)}, {lon.toFixed(4)}
                    </Tooltip>
                </CircleMarker>
            ))}
        </>
    );
}

// Render pole markers
function PoleLayer({ gridData }) {
    if (!gridData || !gridData.poles) return null;
    return (
        <>
            {gridData.poles.map(([lon, lat], i) => (
                <CircleMarker
                    key={`p${i}`}
                    center={[lat, lon]}
                    radius={2}
                    pathOptions={{ color: '#555', fillColor: '#777', fillOpacity: 0.5, weight: 1 }}
                >
                    <Tooltip>
                        Pole<br />
                        {lat.toFixed(4)}, {lon.toFixed(4)}
                    </Tooltip>
                </CircleMarker>
            ))}
        </>
    );
}

// Render substations
function SubstationLayer({ gridData }) {
    if (!gridData || !gridData.substations) return null;
    return (
        <>
            {gridData.substations.map(([lon, lat, voltage, name], i) => (
                <CircleMarker
                    key={`s${i}`}
                    center={[lat, lon]}
                    radius={3}
                    pathOptions={{ color: '#888', fillColor: '#DDD', fillOpacity: 0.8, weight: 1 }}
                >
                    {name && (
                        <Tooltip>
                            <div style={{ fontFamily: 'Inter, sans-serif', fontSize: '11px' }}>
                                <strong>{name}</strong><br />
                                {voltage ? `${voltage}` : 'Unknown Voltage'}
                            </div>
                        </Tooltip>
                    )}
                </CircleMarker>
            ))}
        </>
    );
}

// Render sensor markers
function SensorLayer({ simState, busGeoMap }) {
    const { sensors, sensorReadings } = simState;
    if (!sensors || sensors.length === 0) return null;

    return (
        <>
            {sensors.map((busId, i) => {
                const geo = busGeoMap.get(busId);
                if (!geo) return null;
                const isLive = sensorReadings ? (sensorReadings.get(busId) || 0) === 1 : true;
                const color = isLive ? '#00E676' : '#FF1744';

                return (
                    <CircleMarker
                        key={`sen${i}`}
                        center={[geo[1], geo[0]]}
                        radius={5}
                        pathOptions={{
                            color: color,
                            fillColor: color,
                            fillOpacity: 0.9,
                            weight: 2,
                        }}
                    >
                        <Tooltip>Sensor S{i + 1} | Bus {busId} | {isLive ? 'LIVE' : 'DEAD'}</Tooltip>
                    </CircleMarker>
                );
            })}
        </>
    );
}

// Render power source marker
function SourceMarker({ gridData, busGeoMap }) {
    if (!gridData) return null;
    const geo = busGeoMap.get(gridData.ext_grid_bus);
    if (!geo) return null;

    return (
        <CircleMarker
            center={[geo[1], geo[0]]}
            radius={6}
            pathOptions={{
                color: '#E040FB',
                fillColor: '#E040FB',
                fillOpacity: 1,
                weight: 2,
            }}
        >
            <Tooltip>Power Source (Bus {gridData.ext_grid_bus})</Tooltip>
        </CircleMarker>
    );
}

export default function MapView({ gridData, simState, layers, tileLayer, isolateFault, onTriggerFault }) {
    // Build bus geo lookup
    const busGeoMap = useMemo(() => {
        const m = new Map();
        if (gridData) {
            for (const [id, lon, lat] of gridData.buses) {
                m.set(id, [lon, lat]);
            }
        }
        return m;
    }, [gridData]);

    // Default center on India
    const center = useMemo(() => {
        if (gridData && gridData.buses.length > 0) {
            let sumLat = 0, sumLon = 0, count = 0;
            // Sample 500 buses for center
            const step = Math.max(1, Math.floor(gridData.buses.length / 500));
            for (let i = 0; i < gridData.buses.length; i += step) {
                sumLon += gridData.buses[i][1];
                sumLat += gridData.buses[i][2];
                count++;
            }
            return [sumLat / count, sumLon / count];
        }
        return [22.5, 78.5]; // India center
    }, [gridData]);

    if (!gridData) {
        return (
            <div className="map-container">
                <div className="map-loading">
                    <div className="spinner" />
                    <div className="text">Loading grid data...</div>
                </div>
            </div>
        );
    }

    return (
        <div className="map-container">
            <MapContainer
                center={center}
                zoom={5}
                style={{ width: '100%', height: '100%' }}
                preferCanvas={true}
                zoomControl={true}
            >
                <TileLayerSwitcher tileLayer={tileLayer} />

                {layers.lines && (
                    <LineLayer
                        gridData={gridData}
                        simState={simState}
                        busGeoMap={busGeoMap}
                        isolateFault={isolateFault}
                        onTriggerFault={onTriggerFault}
                    />
                )}
                {layers.towers && <TowerLayer gridData={gridData} />}
                {layers.poles && <PoleLayer gridData={gridData} />}
                {layers.substations && <SubstationLayer gridData={gridData} />}
                {layers.sensors && <SensorLayer simState={simState} busGeoMap={busGeoMap} />}
                {layers.source && <SourceMarker gridData={gridData} busGeoMap={busGeoMap} />}
            </MapContainer>

            {/* Voltage Legend */}
            <div className="map-legend">
                <div className="legend-title">Voltage</div>
                {[
                    ['765+ kV', '#FF1744'],
                    ['400 kV', '#FF6D00'],
                    ['220 kV', '#FFD600'],
                    ['132 kV', '#76FF03'],
                    ['110 kV', '#00E676'],
                    ['66 kV', '#00B0FF'],
                    ['33 kV', '#2979FF'],
                    ['11 kV', '#AA00FF'],
                ].map(([label, color]) => (
                    <div key={label} className="legend-item">
                        <div className="legend-line" style={{ background: color }} />
                        <span>{label}</span>
                    </div>
                ))}
                <div style={{ marginTop: 6 }} />
                <div className="legend-item">
                    <div className="legend-dot" style={{ background: '#00E676' }} />
                    <span>Sensor Live</span>
                </div>
                <div className="legend-item">
                    <div className="legend-dot" style={{ background: '#FF1744' }} />
                    <span>Sensor Dead</span>
                </div>
                <div className="legend-item">
                    <div className="legend-line" style={{ background: '#FF0000', height: 2, borderTop: '1px dashed #FF0000' }} />
                    <span>Fault Line</span>
                </div>
            </div>
        </div>
    );
}
