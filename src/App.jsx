import React, { useState, useEffect, useRef } from 'react';

// Color mappings matching exact specification
const SEVERITY_COLORS = {
  normal: {
    hex: '#22c55e',
    text: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
    glow: 'rgba(34, 197, 94, 0.25)',
    cardBorder: 'hover:border-emerald-500/40',
    rowBg: 'bg-emerald-950/20 hover:bg-emerald-900/30',
  },
  warning: {
    hex: '#eab308',
    text: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    glow: 'rgba(234, 179, 8, 0.25)',
    cardBorder: 'hover:border-amber-500/40',
    rowBg: 'bg-amber-950/20 hover:bg-amber-900/30',
  },
  critical: {
    hex: '#ef4444',
    text: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/30',
    badge: 'bg-red-500/20 text-red-300 border-red-500/40',
    glow: 'rgba(239, 68, 68, 0.35)',
    cardBorder: 'hover:border-red-500/40',
    rowBg: 'bg-red-950/25 hover:bg-red-900/35',
  },
};

// Inline Oscilloscope Sine Wave Component
function OscilloscopeWave({ classification, severity, line }) {
  const [phase, setPhase] = useState(0);
  const animRef = useRef(null);
  const color = SEVERITY_COLORS[severity] ? SEVERITY_COLORS[severity].hex : '#22c55e';

  // Smooth continuous animation loop
  useEffect(() => {
    let currentPhase = 0;
    const animate = () => {
      currentPhase = (currentPhase + 0.07) % (Math.PI * 2);
      setPhase(currentPhase);
      animRef.current = requestAnimationFrame(animate);
    };
    animRef.current = requestAnimationFrame(animate);

    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, []);

  // Compute waveform shape depending on the disturbance class
  const generatePath = () => {
    const width = 460;
    const height = 110;
    const centerY = height / 2;
    const points = [];
    const totalPoints = 120;

    for (let i = 0; i <= totalPoints; i++) {
      const x = (i / totalPoints) * width;
      const angle = (i / totalPoints) * Math.PI * 6 + phase; // 3 full sine cycles

      let yOffset = 0;
      const nominalAmp = 38;

      switch (classification) {
        case 'Voltage Sag':
          // Reduced amplitude ~50%
          yOffset = Math.sin(angle) * (nominalAmp * 0.48);
          break;

        case 'Voltage Swell':
          // Increased amplitude ~130%
          yOffset = Math.sin(angle) * (nominalAmp * 1.35);
          break;

        case 'Interruption':
          // Near-flat near zero with minor electrical jitter
          yOffset = (Math.sin(angle) * 3) + (Math.sin(angle * 5) * 1.5);
          break;

        case 'Flicker':
          // Amplitude modulation: envelope changes cyclically
          const modEnvelope = 0.55 + 0.45 * Math.sin(phase * 1.5 + (i / totalPoints) * Math.PI * 2);
          yOffset = Math.sin(angle) * (nominalAmp * modEnvelope);
          break;

        case 'Transient Spike':
          // Standard sine with a sharp impulsive spike near 60% of the screen
          const isSpikeRange = i >= 65 && i <= 75;
          const spikeMag = isSpikeRange ? (1 - Math.abs(i - 70) / 5) * 45 : 0;
          yOffset = Math.sin(angle) * nominalAmp + (Math.sin(angle) > 0 ? spikeMag : -spikeMag);
          break;

        case 'Harmonic Distortion':
          // 3rd harmonic distortion (THD > 5%)
          yOffset = Math.sin(angle) * (nominalAmp * 0.85) + Math.sin(angle * 3) * (nominalAmp * 0.35);
          break;

        case 'Notching':
          // Periodic notches cut into the waveform
          const notchCycle = (i + Math.round(phase * 10)) % 24;
          const notchDamp = notchCycle < 4 ? 0.25 : 1.0;
          yOffset = Math.sin(angle) * (nominalAmp * notchDamp);
          break;

        case 'Normal':
        default:
          // Clean 50Hz sine
          yOffset = Math.sin(angle) * nominalAmp;
          break;
      }

      // Constrain within SVG height bounds
      const clampedY = Math.max(6, Math.min(height - 6, centerY - yOffset));
      points.push(`${i === 0 ? 'M' : 'L'} ${x.toFixed(1)},${clampedY.toFixed(1)}`);
    }

    return points.join(' ');
  };

  const pathD = generatePath();
  const gradientId = `wave-grad-${line}`;

  return (
    <div className="relative w-full h-28 bg-[#0b1120] rounded-xl border border-slate-800/80 p-2 overflow-hidden shadow-inner">
      {/* Oscilloscope Grid Background */}
      <svg className="absolute inset-0 w-full h-full opacity-20 pointer-events-none">
        <defs>
          <pattern id={`grid-${line}`} width="28" height="28" patternUnits="userSpaceOnUse">
            <path d="M 28 0 L 0 0 0 28" fill="none" stroke="#475569" strokeWidth="0.75" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill={`url(#grid-${line})`} />
        {/* Center horizontal zero-reference line */}
        <line x1="0" y1="50%" x2="100%" y2="50%" stroke="#64748b" strokeWidth="1" strokeDasharray="3 3" />
      </svg>

      {/* Oscilloscope Channel Badge */}
      <div className="absolute top-2 left-3 z-10 flex items-center space-x-2">
        <span className="text-[10px] font-mono tracking-wider px-2 py-0.5 rounded bg-slate-900/90 text-slate-400 border border-slate-700/60 uppercase">
          CH-{line} • 50 Hz
        </span>
      </div>

      {/* Active Waveform */}
      <svg viewBox="0 0 460 110" preserveAspectRatio="none" className="w-full h-full relative z-0">
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="0.4" />
            <stop offset="100%" stopColor={color} stopOpacity="0.0" />
          </linearGradient>
          <filter id={`glow-${line}`} x="-10%" y="-10%" width="120%" height="120%">
            <feGaussianBlur stdDeviation="2.5" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Shaded Area under wave */}
        <path
          d={`${pathD} L 460,110 L 0,110 Z`}
          fill={`url(#${gradientId})`}
          className="transition-colors duration-300"
        />

        {/* Glowing Main Wave Stroke */}
        <path
          d={pathD}
          fill="none"
          stroke={color}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          filter={`url(#glow-${line})`}
          className="transition-colors duration-300"
        />
      </svg>
    </div>
  );
}

export default function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [lastHeartbeat, setLastHeartbeat] = useState(null);

  // Line States
  const [lineA, setLineA] = useState({
    line: 'A',
    classification: 'Normal',
    features: { rms: 0.707, crest_factor: 1.414, thd: 0.003, band_energy: 0.001 },
    severity: 'normal',
    relay_action: 'HOLD',
    timestamp: '--',
  });

  const [lineB, setLineB] = useState({
    line: 'B',
    classification: 'Normal',
    features: { rms: 0.707, crest_factor: 1.414, thd: 0.003, band_energy: 0.001 },
    severity: 'normal',
    relay_action: 'HOLD',
    timestamp: '--',
  });

  // Event Log (last 50 events)
  const [events, setEvents] = useState([]);

  // Fetch initial events from backend REST endpoint on mount
  useEffect(() => {
    fetch('http://localhost:8000/events')
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setEvents(data.slice(0, 50));
        }
      })
      .catch((err) => console.log('Notice: /events endpoint initial load:', err.message));
  }, []);

  // WebSocket Connection with Auto-Reconnect
  useEffect(() => {
    let ws = null;
    let reconnectTimeout = null;
    let isUnmounted = false;

    const connectWebSocket = () => {
      try {
        ws = new WebSocket('ws://localhost:8000/ws');

        ws.onopen = () => {
          if (isUnmounted) return;
          console.log('Connected to GridGuard WebSocket server');
          setIsConnected(true);
        };

        ws.onmessage = (event) => {
          if (isUnmounted) return;
          try {
            const data = JSON.parse(event.data);
            setLastHeartbeat(new Date());

            if (data.line === 'A') {
              setLineA(data);
            } else if (data.line === 'B') {
              setLineB(data);
            }

            // Prepend new event to log and maintain max 50 items
            setEvents((prev) => [data, ...prev].slice(0, 50));
          } catch (e) {
            console.error('Error parsing incoming WebSocket payload:', e);
          }
        };

        ws.onclose = () => {
          if (isUnmounted) return;
          console.log('WebSocket disconnected. Reconnecting in 2 seconds...');
          setIsConnected(false);
          reconnectTimeout = setTimeout(connectWebSocket, 2000);
        };

        ws.onerror = (err) => {
          console.warn('WebSocket error observed:', err);
          ws.close();
        };
      } catch (err) {
        console.error('Failed to instantiate WebSocket:', err);
        reconnectTimeout = setTimeout(connectWebSocket, 2000);
      }
    };

    connectWebSocket();

    return () => {
      isUnmounted = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, []);

  // Render Line Status Card
  const renderLineCard = (lineData, roleSubtitle) => {
    const sev = SEVERITY_COLORS[lineData.severity] || SEVERITY_COLORS.normal;
    const isTrip = lineData.relay_action === 'TRIP';

    return (
      <div
        className={`relative bg-slate-900/90 backdrop-blur-md rounded-2xl p-6 border border-slate-800 transition-all duration-300 shadow-xl flex flex-col justify-between ${sev.cardBorder}`}
        style={{
          boxShadow: `0 10px 30px -10px ${sev.glow}`,
        }}
      >
        {/* Card Header: Line Identifier & Role */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center space-x-3">
              <span className="text-2xl font-black font-['Outfit'] tracking-tight text-white">
                LINE {lineData.line}
              </span>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700/80 uppercase">
                {roleSubtitle}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-mono mt-1">
              Last event: {lineData.timestamp || 'Waiting for signal...'}
            </p>
          </div>

          {/* Relay Action Pill Indicator */}
          <div className="text-right">
            <span className="text-[10px] uppercase tracking-wider text-slate-400 block mb-1 font-mono">
              SSR Relay
            </span>
            <div
              className={`inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg border font-black text-sm font-mono tracking-wider transition-all duration-300 ${
                isTrip
                  ? 'bg-red-500/20 text-red-400 border-red-500/50 shadow-[0_0_15px_rgba(239,68,68,0.4)] animate-pulse'
                  : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50 shadow-[0_0_15px_rgba(34,197,94,0.25)]'
              }`}
            >
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  isTrip ? 'bg-red-500 shadow-[0_0_8px_#ef4444]' : 'bg-emerald-500 shadow-[0_0_8px_#22c55e]'
                }`}
              />
              <span>{lineData.relay_action}</span>
            </div>
          </div>
        </div>

        {/* Primary Classification & Severity Badge */}
        <div className="bg-slate-950/60 rounded-xl p-4 border border-slate-800/80 mb-5">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs uppercase font-mono tracking-wider text-slate-400">
              AI Classification
            </span>
            {/* Severity Badge */}
            <span
              className={`text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${sev.badge}`}
            >
              {lineData.severity}
            </span>
          </div>
          <div className="text-3xl font-extrabold tracking-tight font-['Outfit'] text-white">
            {lineData.classification}
          </div>
        </div>

        {/* Real-time Oscilloscope Sine Wave */}
        <div className="mb-5">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2 font-mono">
            <span>LIVE WAVEFORM SYNTHESIS</span>
            <span className={sev.text}>
              {lineData.severity === 'normal' ? 'Sinusoidal nominal' : 'Disturbance detected'}
            </span>
          </div>
          <OscilloscopeWave
            classification={lineData.classification}
            severity={lineData.severity}
            line={lineData.line}
          />
        </div>

        {/* 4 Feature Values Grid */}
        <div>
          <span className="text-[11px] font-mono uppercase tracking-wider text-slate-400 block mb-2">
            Extracted Features (FFT)
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
            <div className="bg-slate-950/70 border border-slate-800/90 rounded-lg p-2.5 text-center">
              <span className="text-[10px] text-slate-400 block uppercase font-mono">RMS</span>
              <span className="text-base font-bold font-mono text-slate-100">
                {typeof lineData.features?.rms === 'number' ? lineData.features.rms.toFixed(3) : '--'}
              </span>
            </div>

            <div className="bg-slate-950/70 border border-slate-800/90 rounded-lg p-2.5 text-center">
              <span className="text-[10px] text-slate-400 block uppercase font-mono">Crest Factor</span>
              <span className="text-base font-bold font-mono text-slate-100">
                {typeof lineData.features?.crest_factor === 'number'
                  ? lineData.features.crest_factor.toFixed(3)
                  : '--'}
              </span>
            </div>

            <div className="bg-slate-950/70 border border-slate-800/90 rounded-lg p-2.5 text-center">
              <span className="text-[10px] text-slate-400 block uppercase font-mono">THD</span>
              <span className="text-base font-bold font-mono text-slate-100">
                {typeof lineData.features?.thd === 'number' ? lineData.features.thd.toFixed(3) : '--'}
              </span>
            </div>

            <div className="bg-slate-950/70 border border-slate-800/90 rounded-lg p-2.5 text-center">
              <span className="text-[10px] text-slate-400 block uppercase font-mono">Band Energy</span>
              <span className="text-base font-bold font-mono text-slate-100">
                {typeof lineData.features?.band_energy === 'number'
                  ? lineData.features.band_energy.toFixed(3)
                  : '--'}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 flex flex-col font-['Plus_Jakarta_Sans',sans-serif]">
      {/* Top Header Section */}
      <header className="border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
          {/* Logo & Tagline */}
          <div className="flex items-center space-x-3.5">
            <div className="w-11 h-11 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <svg className="w-6 h-6 text-slate-950" fill="currentColor" viewBox="0 0 24 24">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-2xl font-black tracking-tight font-['Outfit'] text-white">
                  GridGuard
                </h1>
                <span className="text-[10px] font-mono tracking-widest bg-slate-800 text-teal-400 px-2 py-0.5 rounded border border-teal-500/30 uppercase font-semibold">
                  v1.0 • RF AI
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium">
                AI-Powered Power Quality Monitor
              </p>
            </div>
          </div>

          {/* Connection Status & Live Badge */}
          <div className="flex items-center space-x-4">
            <div className="hidden md:flex items-center space-x-2 text-xs font-mono text-slate-400">
              <span className="text-slate-400">Broker:</span>
              <span className="text-slate-200">localhost:1883</span>
              <span className="text-slate-600">•</span>
              <span className="text-slate-400">Latency:</span>
              <span className="text-emerald-400 font-bold">&lt; 50ms</span>
            </div>

            {/* LIVE WebSocket Badge */}
            <div
              className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-full border text-xs font-mono font-bold tracking-wider transition-all duration-300 ${
                isConnected
                  ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300 shadow-[0_0_15px_rgba(34,197,94,0.3)]'
                  : 'bg-red-500/15 border-red-500/40 text-red-300 animate-pulse shadow-[0_0_15px_rgba(239,68,68,0.3)]'
              }`}
            >
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  isConnected
                    ? 'bg-[#22c55e] shadow-[0_0_8px_#22c55e] animate-ping'
                    : 'bg-[#ef4444] shadow-[0_0_8px_#ef4444]'
                }`}
              />
              <span>{isConnected ? 'LIVE' : 'DISCONNECTED'}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Dashboard Workspace */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Dual Line Status Cards Grid */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold font-['Outfit'] tracking-tight text-white flex items-center space-x-2">
              <span>Dual-Line Real-Time Channels</span>
              <span className="text-xs font-normal text-slate-400 font-mono">
                (Split ESP32 Sensing + Pi AI Inference)
              </span>
            </h2>
            <div className="text-xs text-slate-400 font-mono flex items-center space-x-4">
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-[#22c55e]" />
                <span>Normal</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-[#eab308]" />
                <span>Warning</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="w-2 h-2 rounded-full bg-[#ef4444]" />
                <span>Critical</span>
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {renderLineCard(lineA, 'Clean Reference (FG-1)')}
            {renderLineCard(lineB, 'Injected Faults (FG-2)')}
          </div>
        </section>

        {/* Event Log Table Section */}
        <section className="bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-800 shadow-xl overflow-hidden">
          <div className="p-5 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h3 className="text-lg font-bold font-['Outfit'] tracking-tight text-white">
                Live Disturbance Event Log
              </h3>
              <p className="text-xs text-slate-400 font-mono">
                Last 50 events captured in-memory • Newest first
              </p>
            </div>
            <div className="flex items-center space-x-3 text-xs font-mono text-slate-400">
              <span className="px-2.5 py-1 rounded bg-slate-800/90 border border-slate-700/60">
                Total Logged: <strong className="text-white">{events.length}</strong>
              </span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse font-mono">
              <thead>
                <tr className="bg-slate-950/80 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-800">
                  <th className="py-3.5 px-4 font-semibold">Timestamp</th>
                  <th className="py-3.5 px-4 font-semibold">Line</th>
                  <th className="py-3.5 px-4 font-semibold">Classification</th>
                  <th className="py-3.5 px-4 font-semibold">Severity</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Relay Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {events.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="py-12 text-center text-slate-400 text-xs">
                      No disturbance events recorded yet. Waiting for MQTT feature stream...
                    </td>
                  </tr>
                ) : (
                  events.map((evt, idx) => {
                    const sev = SEVERITY_COLORS[evt.severity] || SEVERITY_COLORS.normal;
                    const isTrip = evt.relay_action === 'TRIP';

                    return (
                      <tr
                        key={`${evt.timestamp}-${idx}`}
                        className={`transition-colors duration-150 ${sev.rowBg}`}
                      >
                        {/* Timestamp */}
                        <td className="py-3 px-4 text-xs text-slate-300 whitespace-nowrap">
                          {evt.timestamp || '--'}
                        </td>

                        {/* Line */}
                        <td className="py-3 px-4 font-bold text-white whitespace-nowrap">
                          <span
                            className={`inline-block px-2 py-0.5 rounded text-xs ${
                              evt.line === 'A'
                                ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                                : 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
                            }`}
                          >
                            Line {evt.line}
                          </span>
                        </td>

                        {/* Classification */}
                        <td className="py-3 px-4 font-bold text-white whitespace-nowrap font-['Plus_Jakarta_Sans',sans-serif]">
                          {evt.classification}
                        </td>

                        {/* Severity */}
                        <td className="py-3 px-4 whitespace-nowrap">
                          <span
                            className={`inline-block text-xs uppercase px-2.5 py-0.5 rounded-full font-bold border ${sev.badge}`}
                          >
                            {evt.severity}
                          </span>
                        </td>

                        {/* Relay Action */}
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          <span
                            className={`inline-flex items-center space-x-1.5 px-2.5 py-0.5 rounded text-xs font-bold border ${
                              isTrip
                                ? 'bg-red-500/20 text-red-400 border-red-500/40'
                                : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                            }`}
                          >
                            <span
                              className={`w-1.5 h-1.5 rounded-full ${
                                isTrip ? 'bg-red-500' : 'bg-emerald-500'
                              }`}
                            />
                            <span>{evt.relay_action}</span>
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-4 bg-slate-950/60 text-center text-xs text-slate-400 font-mono">
        GridGuard • Amrita Vishwa Vidyapeetham • 23CCE381 Open Lab I • Sub-50ms Split Architecture
      </footer>
    </div>
  );
}
