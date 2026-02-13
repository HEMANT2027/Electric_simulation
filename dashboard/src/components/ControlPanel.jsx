import React from 'react';
import {
    Zap,
    Map as MapIcon,
    Layers,
    Settings,
    RotateCcw,
    Activity,
    AlertTriangle,
    Satellite,
    Sun,
    Moon,
    Radio,
    TowerControl
} from 'lucide-react';

export default function ControlPanel({
    gridData, simState, onEnergize, onDeenergize, onPlaceSensors,
    onTriggerFault, onTriggerBridgeFault, onRepairFault, onReset, layers, onToggleLayer,
    tileLayer, onChangeTile, isolateFault, onToggleIsolateFault
}) {
    const { energized, sensors, faultInfo } = simState;

    return (
        <div className="control-panel">
            {/* Tile Layers */}
            <div className="panel-section">
                <div className="section-title">
                    <MapIcon size={12} style={{ marginRight: 6 }} /> Map Style
                </div>
                <div className="tile-selector">
                    <button
                        className={`tile-btn ${tileLayer === 'dark' ? 'active' : ''}`}
                        onClick={() => onChangeTile('dark')}
                    >
                        <Moon size={10} style={{ marginRight: 4 }} /> Dark
                    </button>
                    <button
                        className={`tile-btn ${tileLayer === 'light' ? 'active' : ''}`}
                        onClick={() => onChangeTile('light')}
                    >
                        <Sun size={10} style={{ marginRight: 4 }} /> Light
                    </button>
                    <button
                        className={`tile-btn ${tileLayer === 'satellite' ? 'active' : ''}`}
                        onClick={() => onChangeTile('satellite')}
                    >
                        <Satellite size={10} style={{ marginRight: 4 }} /> Sat
                    </button>
                </div>
            </div>

            {/* Data Layers */}
            <div className="panel-section">
                <div className="section-title">
                    <Layers size={12} style={{ marginRight: 6 }} /> Layers
                </div>
                {[
                    { key: 'lines', label: 'Lines & Cables' },
                    { key: 'towers', label: 'Towers' },
                    { key: 'poles', label: 'Poles' },
                    { key: 'substations', label: 'Substations' },
                    { key: 'sensors', label: 'Sensors' },
                    { key: 'source', label: 'Power Source' },
                ].map(({ key, label }) => (
                    <div key={key} className={`toggle-row ${layers[key] ? 'active' : ''}`}>
                        <span className="toggle-label">{label}</span>
                        <div
                            className={`toggle-switch ${layers[key] ? 'on' : ''}`}
                            onClick={() => onToggleLayer(key)}
                        />
                    </div>
                ))}
            </div>

            {/* Grid Control */}
            <div className="panel-section">
                <div className="section-title">
                    <Settings size={12} style={{ marginRight: 6 }} /> Grid Control
                </div>

                <div className={`toggle-row ${energized ? 'active' : ''}`}>
                    <span className="toggle-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        {energized ? <Zap size={14} color="#FFD600" /> : <Zap size={14} color="#555" />}
                        {energized ? 'Energized' : 'De-energized'}
                    </span>
                    <div
                        className={`toggle-switch ${energized ? 'on' : ''}`}
                        onClick={energized ? onDeenergize : onEnergize}
                    />
                </div>
            </div>

            {/* Sensors */}
            <div className="panel-section">
                <div className="section-title">
                    <Radio size={12} style={{ marginRight: 6 }} /> Sensors
                </div>
                <button
                    className="btn"
                    onClick={onPlaceSensors}
                    disabled={!gridData || sensors.length > 0}
                >
                    <Radio size={14} /> Place √n Sensors
                </button>
                {sensors.length > 0 && (
                    <div style={{ fontSize: 11, color: '#666', textAlign: 'center', marginTop: 4 }}>
                        {sensors.length} sensors in {simState.blocks?.length || 0} blocks
                    </div>
                )}
            </div>

            {/* Fault Injection */}
            <div className="panel-section">
                <div className="section-title">
                    <Activity size={12} style={{ marginRight: 6 }} /> Fault Injection
                </div>
                <button
                    className="btn danger"
                    onClick={onTriggerBridgeFault}
                    disabled={!energized}
                    title={!energized ? "Energize grid first" : "Disconnect a critical bridge line"}
                >
                    <AlertTriangle size={14} /> Trigger Bridge Fault
                </button>
                <button
                    className="btn danger"
                    onClick={onTriggerFault}
                    disabled={!energized}
                    title={!energized ? "Energize grid first" : "Trigger a random line fault"}
                >
                    <AlertTriangle size={14} /> Random Fault
                </button>

                {faultInfo && (
                    <button
                        className="btn success"
                        onClick={onRepairFault}
                        title="Repair current fault and restore grid"
                        style={{ marginTop: 8 }}
                    >
                        <RotateCcw size={14} /> Repair Fault
                    </button>
                )}

                <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--border-light)' }}>
                    <div className={`toggle-row ${isolateFault ? 'active' : ''}`} style={{ justifyContent: 'space-between' }}>
                        <div>
                            <span className="toggle-label" style={{ fontSize: 12, fontWeight: 500 }}>Isolate Fault</span>
                            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                                Hide healthy lines
                            </div>
                        </div>
                        <div
                            className={`toggle-switch ${isolateFault ? 'on' : ''}`}
                            onClick={onToggleIsolateFault}
                            style={{ transform: 'scale(0.8)', transformOrigin: 'right center' }}
                        />
                    </div>
                </div>
            </div>

            {/* Reset */}
            <div className="panel-section">
                <button className="btn primary" onClick={onReset}>
                    <RotateCcw size={14} /> Reset Simulation
                </button>
            </div>
        </div>
    );
}
