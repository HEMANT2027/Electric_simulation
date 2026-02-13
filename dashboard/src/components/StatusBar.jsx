import React from 'react';
import { Zap, Activity, Radio, AlertTriangle, Cpu } from 'lucide-react';

export default function StatusBar({ gridData, simState }) {
    const { energized, sensors, sensorReadings, faultInfo, faultyBlock } = simState;

    const totalBuses = gridData ? gridData.stats.total_buses : 0;
    const totalLines = gridData ? gridData.stats.total_lines : 0;

    let liveBuses = 0, deadBuses = 0;
    if (simState.energizedStatus) {
        simState.energizedStatus.forEach((v) => {
            if (v === 1) liveBuses++;
            else deadBuses++;
        });
    }

    let liveSensors = 0, deadSensors = 0;
    if (sensorReadings) {
        sensorReadings.forEach((v) => {
            if (v === 1) liveSensors++;
            else deadSensors++;
        });
    }

    return (
        <div className="status-bar">
            <div className="logo">
                <Zap size={18} /> GRID SIMULATOR
            </div>
            <div className="divider" />

            <div className="stat-item">
                <span className="label">Buses</span>
                <span className="value">{totalBuses.toLocaleString()}</span>
            </div>

            <div className="stat-item">
                <span className="label">Lines</span>
                <span className="value">{totalLines.toLocaleString()}</span>
            </div>

            <div className="divider" />

            {energized && (
                <>
                    <div className="stat-item">
                        <span className="label">Live</span>
                        <span className="value live">{liveBuses.toLocaleString()}</span>
                    </div>
                    <div className="stat-item">
                        <span className="label">Dead</span>
                        <span className="value dead">{deadBuses.toLocaleString()}</span>
                    </div>
                    <div className="divider" />
                </>
            )}

            {sensors.length > 0 && (
                <>
                    <div className="stat-item">
                        <Radio size={14} style={{ marginRight: 4, color: '#555' }} />
                        <span className="value">{sensors.length}</span>
                    </div>
                    {sensorReadings && (
                        <>
                            <div className="stat-item">
                                <span className="value live">{liveSensors}</span>
                            </div>
                            <div className="stat-item">
                                <span className="value dead">{deadSensors}</span>
                            </div>
                        </>
                    )}
                    <div className="divider" />
                </>
            )}

            {faultInfo && (
                <div className="stat-item">
                    <Activity size={14} color="#FF0000" style={{ marginRight: 4 }} />
                    <span className="value fault">Line {faultInfo.lineIdx}</span>
                </div>
            )}

            {faultyBlock >= 0 && (
                <div className="stat-item">
                    <AlertTriangle size={14} color="#FF6D00" style={{ marginRight: 4 }} />
                    <span className="value fault">Block {faultyBlock + 1}</span>
                </div>
            )}

            {!energized && !faultInfo && sensors.length === 0 && (
                <div className="stat-item">
                    <Cpu size={14} style={{ marginRight: 4, color: '#555' }} />
                    <span className="value" style={{ color: '#555' }}>Ready</span>
                </div>
            )}
        </div>
    );
}
