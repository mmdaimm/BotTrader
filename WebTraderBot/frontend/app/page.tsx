'use client';

import React, { useState, useEffect } from 'react';
import CandlestickChart, { CandleData } from './components/CandlestickChart';

interface PairEval {
  symbol: string;
  signal: string;
  side?: string;
  price?: number;
  reason?: string;
}

interface PairResult {
  last_price: number;
  eval: PairEval;
}

interface PaperSummary {
  initial_capital: number;
  current_capital: number;
  net_profit: number;
  net_profit_pct: number;
  total_trades: number;
  win_trades: number;
  loss_trades: number;
  win_rate_pct: number;
  active_positions_count: number;
}

interface ActivePosition {
  id: string;
  symbol: string;
  side: string; // "LONG" or "SHORT"
  leverage: number;
  entry_price: number;
  qty: number;
  order_value: number;
  margin_required: number;
  sl_price: number;
  tp_price: number;
  entry_time: string;
  status: string;
}

interface TradeRecord {
  id: string;
  symbol: string;
  side: string;
  type: string;
  entry_price: number;
  exit_price: number;
  net_pnl: number;
  pnl_pct: number;
  entry_time: string;
  exit_time: string;
}

interface StatusResponse {
  status: string;
  bot_state?: string;
  trading_mode?: string;
  active_symbols?: string[];
  last_price?: number;
  pair_results?: Record<string, PairResult>;
  paper_summary?: PaperSummary;
  active_positions?: ActivePosition[];
  trade_history?: TradeRecord[];
  reason?: string;
}

const DEFAULT_BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export default function Dashboard() {
  const [backendUrl, setBackendUrl] = useState<string>(DEFAULT_BACKEND);
  const [data, setData] = useState<StatusResponse | null>(null);
  const [logs, setLogs] = useState<string[]>([
    'Initializing Next.js OKX Futures Dashboard...',
    `Target Backend: ${DEFAULT_BACKEND}`
  ]);
  const [tradingMode, setTradingMode] = useState<string>('PAPER');

  // Candlestick & Indicators Chart State
  const [chartSymbol, setChartSymbol] = useState<string>('BTC-USDT-SWAP');
  const [chartResolution, setChartResolution] = useState<string>('15');
  const [candles, setCandles] = useState<CandleData[]>([]);

  // Feed Log Coin Filter State (User can toggle which coins to view in log)
  const [selectedLogCoins, setSelectedLogCoins] = useState<string[]>(['BTC', 'ETH', 'DOGE']);

  const toggleLogCoin = (coinTag: string) => {
    if (selectedLogCoins.includes(coinTag)) {
      if (selectedLogCoins.length > 1) {
        setSelectedLogCoins(selectedLogCoins.filter((c) => c !== coinTag));
      }
    } else {
      setSelectedLogCoins([...selectedLogCoins, coinTag]);
    }
  };

  const fetchStatus = async () => {
    try {
      let res = await fetch(`${backendUrl}/api/status`).catch(() => null);
      if (!res && backendUrl === 'http://localhost:8000') {
        const railwayUrl = process.env.NEXT_PUBLIC_RAILWAY_URL;
        if (railwayUrl) {
          res = await fetch(`${railwayUrl}/api/status`).catch(() => null);
          if (res) setBackendUrl(railwayUrl);
        }
      }

      if (!res) return;

      const result: StatusResponse = await res.json();
      setData(result);
      if (result.trading_mode) setTradingMode(result.trading_mode);

      const now = new Date().toLocaleTimeString();
      const pr = result.pair_results || {};

      // Dynamic Terminal Log Formatting based on user's selectedLogCoins
      const coinLogParts: string[] = [];
      const coinMap: Record<string, string> = {
        'BTC': 'BTC-USDT-SWAP',
        'ETH': 'ETH-USDT-SWAP',
        'SOL': 'SOL-USDT-SWAP',
        'XRP': 'XRP-USDT-SWAP',
        'DOGE': 'DOGE-USDT-SWAP'
      };

      selectedLogCoins.forEach((tag) => {
        const sym = coinMap[tag];
        const p = pr[sym]?.last_price;
        if (p !== undefined && p !== null) {
          coinLogParts.push(`${tag}=$${p.toLocaleString()}`);
        }
      });

      if (coinLogParts.length > 0) {
        setLogs((prev) => [
          ...prev.slice(-18),
          `[${now}] State: ${result.bot_state || result.status} | ${coinLogParts.join(' | ')}`
        ]);
      }
    } catch (err) {
      console.error('Error fetching backend status:', err);
    }
  };

  const fetchCandles = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/candles?symbol=${chartSymbol}&resolution=${chartResolution}`);
      const result = await res.json();
      if (result.candles) {
        setCandles(result.candles);
      }
    } catch (err) {
      console.error('Error fetching candles data:', err);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchCandles();
    const interval = setInterval(() => {
      fetchStatus();
      fetchCandles();
    }, 5000);
    return () => clearInterval(interval);
  }, [backendUrl, chartSymbol, chartResolution, selectedLogCoins]);

  const startBot = async () => {
    const res = await fetch(`${backendUrl}/api/start`, { method: 'POST' });
    const resData = await res.json();
    alert(resData.message);
    fetchStatus();
  };

  const pauseBot = async () => {
    const res = await fetch(`${backendUrl}/api/pause`, { method: 'POST' });
    const resData = await res.json();
    alert(resData.message);
    fetchStatus();
  };

  const triggerPanic = async () => {
    if (confirm('🚨 EMERGENCY PANIC STOP:\nคุณต้องการยกเลิกออเดอร์ทั้งหมด และหยุด Bot ทันทีหรือไม่?')) {
      try {
        const res = await fetch(`${backendUrl}/api/panic`, { method: 'POST' });
        const resData = await res.json();
        alert(resData.message);
        fetchStatus();
      } catch (e) {
        console.error('Panic trigger error:', e);
      }
    }
  };

  const toggleMode = async () => {
    const res = await fetch(`${backendUrl}/api/toggle-mode`, { method: 'POST' });
    const resData = await res.json();
    setTradingMode(resData.mode);
    alert(`Switched to: ${resData.mode} TRADING MODE`);
  };

  const simTrade = async (symbol: string, side: string) => {
    const res = await fetch(`${backendUrl}/api/sim-buy?symbol=${symbol}&side=${side}`, { method: 'POST' });
    const resData = await res.json();
    alert(resData.message);
    fetchStatus();
    fetchCandles();
  };

  const pairs = data?.pair_results || {};
  const summary = data?.paper_summary;
  const botState = data?.bot_state || (data?.status === 'OK' ? 'RUNNING' : data?.status || 'RUNNING');

  // Status Styling Logic
  let statusBg = 'rgba(0, 240, 144, 0.1)';
  let statusBorder = '1px solid rgba(0, 240, 144, 0.2)';
  let statusColor = '#00f090';
  let statusLabel = '🟢 OKX FUTURES BOT RUNNING';

  if (botState === 'PAUSED') {
    statusBg = 'rgba(245, 158, 11, 0.1)';
    statusBorder = '1px solid rgba(245, 158, 11, 0.3)';
    statusColor = '#f59e0b';
    statusLabel = '🟡 BOT PAUSED';
  } else if (botState === 'ERROR') {
    statusBg = 'rgba(255, 59, 105, 0.15)';
    statusBorder = '1px solid rgba(255, 59, 105, 0.3)';
    statusColor = '#ff3b69';
    statusLabel = '🔴 PANIC / CIRCUIT BROKEN';
  }

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#0a0d14',
      color: '#f3f4f6',
      padding: '24px',
      fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      backgroundImage: 'radial-gradient(circle at 15% 15%, rgba(0, 240, 144, 0.05) 0%, transparent 40%), radial-gradient(circle at 85% 85%, rgba(139, 92, 246, 0.05) 0%, transparent 40%)'
    }}>
      {/* Header Bar */}
      <header style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingBottom: '20px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
        marginBottom: '24px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #00f090, #3b82f6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold',
            fontSize: '20px',
            color: '#000'
          }}>
            O
          </div>
          <div>
            <h1 style={{ fontSize: '20px', fontWeight: '700', margin: 0 }}>WebTraderBot — Custom Log Filters & Indicators</h1>
            <p style={{ fontSize: '12px', color: '#9ca3af', margin: 0 }}>OKX Perpetual Swaps (EMA 200, EMA 9, EMA 21, VWAP, ADX, Volume)</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            borderRadius: '20px',
            background: statusBg,
            border: statusBorder,
            color: statusColor,
            fontSize: '13px',
            fontWeight: '700'
          }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: statusColor
            }} />
            {statusLabel}
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={startBot} style={{
              background: 'rgba(0, 240, 144, 0.15)',
              border: '1px solid rgba(0, 240, 144, 0.3)',
              color: '#00f090',
              padding: '8px 14px',
              borderRadius: '8px',
              fontWeight: '700',
              fontSize: '12px',
              cursor: 'pointer'
            }}>
              ▶️ เริ่มทำงาน
            </button>

            <button onClick={pauseBot} style={{
              background: 'rgba(245, 158, 11, 0.15)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              color: '#f59e0b',
              padding: '8px 14px',
              borderRadius: '8px',
              fontWeight: '700',
              fontSize: '12px',
              cursor: 'pointer'
            }}>
              ⏸️ หยุดพัก
            </button>

            <button onClick={toggleMode} style={{
              background: 'rgba(59, 130, 246, 0.15)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              color: '#3b82f6',
              padding: '8px 14px',
              borderRadius: '8px',
              fontWeight: '700',
              fontSize: '12px',
              cursor: 'pointer'
            }}>
              MODE: {tradingMode}
            </button>

            <button onClick={triggerPanic} style={{
              background: 'linear-gradient(135deg, #ff3b69, #dc2626)',
              color: 'white',
              border: 'none',
              padding: '8px 16px',
              borderRadius: '8px',
              fontWeight: '700',
              fontSize: '12px',
              cursor: 'pointer',
              boxShadow: '0 4px 15px rgba(255, 59, 105, 0.4)'
            }}>
              🚨 PANIC STOP
            </button>
          </div>
        </div>
      </header>

      {/* OKX Perpetual Swap Instrument Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
        gap: '16px',
        marginBottom: '24px'
      }}>
        {[
          { sym: 'BTC-USDT-SWAP', label: 'BTC Perpetual', tag: 'BTC' },
          { sym: 'ETH-USDT-SWAP', label: 'ETH Perpetual', tag: 'ETH' },
          { sym: 'SOL-USDT-SWAP', label: 'SOL Perpetual', tag: 'SOL' },
          { sym: 'XRP-USDT-SWAP', label: 'XRP Perpetual', tag: 'XRP' },
          { sym: 'DOGE-USDT-SWAP', label: 'DOGE Perpetual', tag: 'DOGE' },
        ].map((coin) => {
          const item = pairs[coin.sym];
          const price = item?.last_price;
          const sig = item?.eval?.signal || 'NONE';
          const isSelected = chartSymbol === coin.sym;
          return (
            <div key={coin.sym} 
              onClick={() => setChartSymbol(coin.sym)}
              style={{
                background: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'rgba(18, 24, 38, 0.75)',
                backdropFilter: 'blur(12px)',
                border: isSelected ? '2px solid #3b82f6' : '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '16px',
                padding: '16px',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', fontSize: '11px', color: '#9ca3af' }}>
                <span style={{ fontWeight: '700', color: isSelected ? '#3b82f6' : '#9ca3af' }}>{coin.label}</span>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button onClick={(e) => { e.stopPropagation(); simTrade(coin.sym, 'LONG'); }} style={{
                    background: '#00f090',
                    color: '#000',
                    border: 'none',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontWeight: '700',
                    fontSize: '10px',
                    cursor: 'pointer'
                  }}>
                    + LONG
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); simTrade(coin.sym, 'SHORT'); }} style={{
                    background: '#ff3b69',
                    color: '#fff',
                    border: 'none',
                    padding: '2px 6px',
                    borderRadius: '4px',
                    fontWeight: '700',
                    fontSize: '10px',
                    cursor: 'pointer'
                  }}>
                    - SHORT
                  </button>
                </div>
              </div>
              <div style={{ fontSize: '18px', fontWeight: '700', fontFamily: 'monospace', marginBottom: '4px' }}>
                {price ? `$${price.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '$0.00'}
              </div>
              <div style={{
                fontSize: '11px',
                fontWeight: '600',
                color: sig.includes('BUY') ? '#00f090' : (sig.includes('SELL') ? '#ff3b69' : '#9ca3af')
              }}>
                Signal: {sig}
              </div>
            </div>
          );
        })}
      </div>

      {/* Interactive Candlestick Chart Section */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <h2 style={{ fontSize: '15px', fontWeight: '700', margin: 0 }}>📊 Live Candlestick & Multi-Indicator Chart ({chartSymbol})</h2>
            <div style={{ display: 'flex', gap: '6px' }}>
              {['5', '15', '60'].map((tf) => (
                <button
                  key={tf}
                  onClick={() => setChartResolution(tf)}
                  style={{
                    background: chartResolution === tf ? '#3b82f6' : 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    color: chartResolution === tf ? '#fff' : '#9ca3af',
                    padding: '3px 8px',
                    borderRadius: '6px',
                    fontSize: '11px',
                    fontWeight: '700',
                    cursor: 'pointer'
                  }}
                >
                  {tf === '60' ? '1h' : `${tf}m`}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '12px', fontSize: '11px', fontWeight: '600' }}>
            <span style={{ color: '#a855f7' }}>🟪 EMA 200</span>
            <span style={{ color: '#3b82f6' }}>🔷 EMA 9</span>
            <span style={{ color: '#f97316' }}>🍊 EMA 21</span>
            <span style={{ color: '#38bdf8' }}>🩵 VWAP</span>
            <span style={{ color: '#ef4444' }}>🔴 ADX (14)</span>
          </div>
        </div>

        <CandlestickChart candles={candles} symbol={chartSymbol} resolution={chartResolution} />
      </div>

      {/* Main Layout Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '20px', marginBottom: '24px' }}>
        {/* Terminal Log */}
        <div style={{
          background: 'rgba(18, 24, 38, 0.75)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '20px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontWeight: '600', fontSize: '14px' }}>📡 Terminal Feed Log</span>
              
              {/* Coin Log Filter Selectors */}
              <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', color: '#9ca3af', marginRight: '4px' }}>Log Coins:</span>
                {['BTC', 'ETH', 'SOL', 'XRP', 'DOGE'].map((coin) => {
                  const isChecked = selectedLogCoins.includes(coin);
                  return (
                    <button
                      key={coin}
                      onClick={() => toggleLogCoin(coin)}
                      style={{
                        background: isChecked ? '#3b82f6' : 'rgba(255, 255, 255, 0.05)',
                        color: isChecked ? '#ffffff' : '#6b7280',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        borderRadius: '4px',
                        padding: '2px 6px',
                        fontSize: '10px',
                        fontWeight: '700',
                        cursor: 'pointer'
                      }}
                    >
                      {isChecked ? `✓ ${coin}` : coin}
                    </button>
                  );
                })}
              </div>
            </div>

            <button onClick={() => { fetchStatus(); fetchCandles(); }} style={{
              background: 'transparent',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#9ca3af',
              padding: '4px 10px',
              borderRadius: '6px',
              fontSize: '12px',
              cursor: 'pointer'
            }}>
              Refresh
            </button>
          </div>
          <div style={{
            background: '#06080d',
            border: '1px solid rgba(255, 255, 255, 0.05)',
            borderRadius: '12px',
            padding: '16px',
            fontFamily: 'monospace',
            fontSize: '12px',
            color: '#a7f3d0',
            height: '240px',
            overflowY: 'auto',
            lineHeight: '1.6'
          }}>
            {logs.map((log, idx) => (
              <div key={idx} style={{ marginBottom: '4px' }}>{log}</div>
            ))}
          </div>
        </div>

        {/* Paper Portfolio Summary */}
        <div style={{
          background: 'rgba(18, 24, 38, 0.75)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '20px'
        }}>
          <h2 style={{ fontWeight: '600', fontSize: '14px', marginBottom: '16px' }}>💼 OKX Futures Portfolio Summary</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Current Balance</span>
              <span style={{ fontWeight: '700', fontFamily: 'monospace' }}>${summary?.current_capital?.toLocaleString() || '10,000.00'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Net Profit</span>
              <span style={{ fontWeight: '700', fontFamily: 'monospace', color: (summary?.net_profit || 0) >= 0 ? '#00f090' : '#ff3b69' }}>
                ${summary?.net_profit || '0.00'} ({summary?.net_profit_pct || 0}%)
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Win Rate</span>
              <span style={{ fontWeight: '700', fontFamily: 'monospace' }}>{summary?.win_rate_pct || 0}% ({summary?.total_trades || 0} Trades)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#9ca3af' }}>OKX Leverage / Fee</span>
              <span style={{ fontWeight: '600', color: '#d1d5db' }}>3x Isolated | ~0.05% Fee</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tables Section */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Active Positions */}
        <div style={{
          background: 'rgba(18, 24, 38, 0.75)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '20px'
        }}>
          <h2 style={{ fontWeight: '600', fontSize: '14px', marginBottom: '12px' }}>📍 Active OKX Futures Positions</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ color: '#9ca3af', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', textAlign: 'left' }}>
                <th style={{ paddingBottom: '8px' }}>Instrument</th>
                <th style={{ paddingBottom: '8px' }}>Side</th>
                <th style={{ paddingBottom: '8px' }}>Entry</th>
                <th style={{ paddingBottom: '8px' }}>SL / TP</th>
                <th style={{ paddingBottom: '8px' }}>Margin (3x)</th>
              </tr>
            </thead>
            <tbody>
              {data?.active_positions && data.active_positions.length > 0 ? (
                data.active_positions.map((pos) => {
                  const isLong = pos.side === 'LONG';
                  return (
                    <tr key={pos.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      <td style={{ padding: '8px 0', fontWeight: 'bold' }}>{pos.symbol}</td>
                      <td style={{ padding: '8px 0' }}>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontWeight: '700',
                          fontSize: '10px',
                          background: isLong ? 'rgba(0, 240, 144, 0.15)' : 'rgba(255, 59, 105, 0.15)',
                          color: isLong ? '#00f090' : '#ff3b69'
                        }}>
                          {pos.side} 3x
                        </span>
                      </td>
                      <td style={{ padding: '8px 0', fontFamily: 'monospace' }}>${pos.entry_price?.toLocaleString()}</td>
                      <td style={{ padding: '8px 0', fontFamily: 'monospace' }}>
                        <span style={{ color: '#ff3b69' }}>${pos.sl_price?.toLocaleString()}</span> / <span style={{ color: '#00f090' }}>${pos.tp_price?.toLocaleString()}</span>
                      </td>
                      <td style={{ padding: '8px 0', fontFamily: 'monospace' }}>${pos.margin_required?.toLocaleString()}</td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={5} style={{ padding: '16px 0', color: '#6b7280', textAlign: 'center' }}>No active positions</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Closed History */}
        <div style={{
          background: 'rgba(18, 24, 38, 0.75)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '20px'
        }}>
          <h2 style={{ fontWeight: '600', fontSize: '14px', marginBottom: '12px' }}>📜 Closed Trade History</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ color: '#9ca3af', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', textAlign: 'left' }}>
                <th style={{ paddingBottom: '8px' }}>Instrument</th>
                <th style={{ paddingBottom: '8px' }}>Side / Result</th>
                <th style={{ paddingBottom: '8px' }}>Entry &rarr; Exit</th>
                <th style={{ paddingBottom: '8px' }}>Net PnL</th>
              </tr>
            </thead>
            <tbody>
              {data?.trade_history && data.trade_history.length > 0 ? (
                data.trade_history.map((tr) => {
                  const isWin = tr.net_pnl >= 0;
                  const isLong = tr.side === 'LONG';
                  return (
                    <tr key={tr.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      <td style={{ padding: '8px 0', fontWeight: 'bold' }}>{tr.symbol}</td>
                      <td style={{ padding: '8px 0' }}>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontWeight: '700',
                          fontSize: '10px',
                          marginRight: '4px',
                          background: isLong ? 'rgba(0, 240, 144, 0.15)' : 'rgba(255, 59, 105, 0.15)',
                          color: isLong ? '#00f090' : '#ff3b69'
                        }}>
                          {tr.side}
                        </span>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontWeight: '700',
                          fontSize: '10px',
                          background: isWin ? 'rgba(0, 240, 144, 0.15)' : 'rgba(255, 59, 105, 0.15)',
                          color: isWin ? '#00f090' : '#ff3b69'
                        }}>
                          {tr.type}
                        </span>
                      </td>
                      <td style={{ padding: '8px 0', fontFamily: 'monospace' }}>${tr.entry_price?.toLocaleString()} &rarr; ${tr.exit_price?.toLocaleString()}</td>
                      <td style={{ padding: '8px 0', fontFamily: 'monospace', fontWeight: '700', color: isWin ? '#00f090' : '#ff3b69' }}>
                        ${tr.net_pnl} ({tr.pnl_pct}%)
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={4} style={{ padding: '16px 0', color: '#6b7280', textAlign: 'center' }}>No closed trades yet</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
