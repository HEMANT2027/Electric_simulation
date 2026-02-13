import React from 'react';
import { Radio, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';

export default function SensorPanel({ simState }) {
    const { sensors, sensorReadings, blocks, faultyBlock } = simState;

    if (sensors.length === 0) {
        return (
            <div className="sensor-panel">
                <div className="panel-header">
                    <h3><Radio size={14} style={{ marginRight: 8 }} /> Sensors</h3>
                </div>
                <div className="empty-state">
                    <div className="icon"><Radio size={32} /></div>
                    <div style={{ marginTop: 12 }}>No sensors placed</div>
                    <div style={{ fontSize: 11, color: '#444' }}>
                        Click "Place √n Sensors" to begin
                    </div>
                </div>
            </div>
        );
    }

    let liveSensors = 0, deadSensors = 0;
    if (sensorReadings) {
        sensorReadings.forEach((v) => {
            if (v === 1) liveSensors++;
            else deadSensors++;
        });
    }

    return (
        <div className="sensor-panel">
            <div className="panel-header">
                <h3><Radio size={14} style={{ marginRight: 8 }} /> Sensors ({sensors.length})</h3>
            </div>

            {sensorReadings && (
                <div className="sensor-summary">
                    <span className="live-count" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <CheckCircle size={12} /> {liveSensors} Live
                    </span>
                    <span className="dead-count" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <XCircle size={12} /> {deadSensors} Dead
                    </span>
                </div>
            )}



            {faultyBlock >= 0 && (
                <div style={{
                    padding: '12px 16px',
                    background: 'var(--surface-hover)',
                    borderBottom: '1px solid var(--border)',
                    marginBottom: 10
                }}>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase' }}>
                        Fault Analysis
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {/* Last Live Sensor */}
                        {faultyBlock > 0 ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                                <CheckCircle size={14} color="var(--sensor-live)" />
                                <div>
                                    <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>Sensor S{faultyBlock}</span>
                                    <span style={{ margin: '0 6px', color: '#666' }}>→</span>
                                    <span style={{ color: 'var(--sensor-live)' }}>Last Live Point</span>
                                </div>
                            </div>
                        ) : (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                                <AlertTriangle size={14} color="var(--sensor-dead)" />
                                <span style={{ color: 'var(--text-muted)' }}>Fault is before first sensor</span>
                            </div>
                        )}

                        {/* Connection Line */}
                        <div style={{ marginLeft: 6, height: 12, borderLeft: '1px dashed #666' }} />

                        {/* First Dead Sensor */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                            <XCircle size={14} color="var(--sensor-dead)" />
                            <div>
                                <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>Sensor S{faultyBlock + 1}</span>
                                <span style={{ margin: '0 6px', color: '#666' }}>→</span>
                                <span style={{ color: 'var(--sensor-dead)' }}>First Dead Point</span>
                            </div>
                        </div>

                        <div style={{ marginTop: 8, fontSize: 11, color: '#f59e0b', background: 'rgba(245, 158, 11, 0.1)', padding: 6, borderRadius: 4 }}>
                            Fault isolated between <strong>S{faultyBlock > 0 ? faultyBlock : 'Source'}</strong> and <strong>S{faultyBlock + 1}</strong>
                        </div>
                    </div>
                </div>
            )}

            <div className="sensor-list">
                {sensors.map((busId, i) => {
                    const isLive = sensorReadings ? (sensorReadings.get(busId) || 0) === 1 : true;
                    const isFaultBlock = faultyBlock === i;
                    const blockSize = blocks && blocks[i] ? blocks[i].length : 0;

                    return (
                        <div
                            key={busId}
                            className={`sensor-item ${isFaultBlock ? 'fault-block' : ''}`}
                        >
                            <div className={`sensor-dot ${isLive ? 'live' : 'dead'}`} />
                            <span className="sensor-id">S{i + 1}</span>
                            <span className="sensor-bus">B{busId}</span>
                            <span className="sensor-bus" style={{ fontSize: 10, color: '#555' }}>
                                [{blockSize}]
                            </span>
                            <span className={`sensor-status ${isLive ? 'live' : 'dead'}`}>
                                {isLive ? 'LIVE' : 'DEAD'}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
