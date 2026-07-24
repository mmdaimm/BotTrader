'use client';

import React, { useState, useEffect } from 'react';
import CandlestickChart, { CandleData } from './components/CandlestickChart';

interface PairEval {
  symbol: string;
  signal: string;
  side?: string;
  price?: number;
  reason?: string;
  market_snapshot?: {
    ema800_1h?: number;
    ema200?: number;
    ema9?: number;
    ema21?: number;
    rsi?: number;
    adx?: number;
  };
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
  side: string;
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
  institutional_allocation?: {
    funding_rate_arbitrage_80pct?: {
      allocated_capital_usd: number;
      estimated_annual_apy_pct: number;
      status: string;
    };
    scalping_engine_20pct?: {
      allocated_capital_usd: number;
      current_capital_usd: number;
      status: string;
    };
  };
  active_positions?: ActivePosition[];
  trade_history?: TradeRecord[];
  reason?: string;
}

interface BacktestResult {
  symbol: string;
  status: string;
  days_simulated: number;
  candles_analyzed: number;
  initial_capital_usd: number;
  initial_capital_thb: number;
  architecture: string;
  allocation_breakdown: {
    funding_arbitrage_80pct: {
      allocated_capital_usd: number;
      final_capital_usd: number;
      accumulated_cashflow_usd: number;
      accumulated_cashflow_thb: number;
      annual_apy_pct: number;
    };
    scalping_engine_20pct: {
      allocated_capital_usd: number;
      final_capital_usd: number;
      net_profit_usd: number;
      net_profit_pct: number;
      profit_factor: number;
      total_trades: number;
      win_rate_pct: number;
      max_drawdown_pct: number;
    };
  };
  combined_portfolio_results: {
    final_capital_usd: number;
    final_capital_thb: number;
    net_profit_usd: number;
    net_profit_thb: number;
    net_profit_pct: number;
    verdict: string;
  };
  friction_deductions: string;
}

const DEFAULT_BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

const VETERAN_COINS = [
  { sym: 'BTC-USDT-SWAP', label: 'BTC Perpetual', tag: 'BTC', est: '2009' },
  { sym: 'ETH-USDT-SWAP', label: 'ETH Perpetual', tag: 'ETH', est: '2015' },
  { sym: 'XRP-USDT-SWAP', label: 'XRP Perpetual', tag: 'XRP', est: '2012' },
  { sym: 'LTC-USDT-SWAP', label: 'LTC Perpetual', tag: 'LTC', est: '2011' },
  { sym: 'BCH-USDT-SWAP', label: 'BCH Perpetual', tag: 'BCH', est: '2017' },
  { sym: 'ADA-USDT-SWAP', label: 'ADA Perpetual', tag: 'ADA', est: '2017' },
  { sym: 'SOL-USDT-SWAP', label: 'SOL Perpetual', tag: 'SOL', est: '2020' },
  { sym: 'DOGE-USDT-SWAP', label: 'DOGE Perpetual', tag: 'DOGE', est: '2013' },
  { sym: 'LINK-USDT-SWAP', label: 'LINK Perpetual', tag: 'LINK', est: '2017' },
  { sym: 'DOT-USDT-SWAP', label: 'DOT Perpetual', tag: 'DOT', est: '2020' },
  { sym: 'ATOM-USDT-SWAP', label: 'ATOM Perpetual', tag: 'ATOM', est: '2019' },
  { sym: 'ETC-USDT-SWAP', label: 'ETC Perpetual', tag: 'ETC', est: '2016' },
  { sym: 'XLM-USDT-SWAP', label: 'XLM Perpetual', tag: 'XLM', est: '2014' },
  { sym: 'TRX-USDT-SWAP', label: 'TRX Perpetual', tag: 'TRX', est: '2017' },
  { sym: 'AVAX-USDT-SWAP', label: 'AVAX Perpetual', tag: 'AVAX', est: '2020' },
];

export default function Dashboard() {
  const [backendUrl, setBackendUrl] = useState<string>(DEFAULT_BACKEND);
  const [data, setData] = useState<StatusResponse | null>(null);
  const [logs, setLogs] = useState<string[]>([
    'Initializing Next.js OKX 15-Veteran Institutional Portfolio...',
    `Target Backend: ${DEFAULT_BACKEND}`
  ]);
  const [tradingMode, setTradingMode] = useState<string>('PAPER');

  // Chart State
  const [chartSymbol, setChartSymbol] = useState<string>('BTC-USDT-SWAP');
  const [chartResolution, setChartResolution] = useState<string>('15');
  const [candles, setCandles] = useState<CandleData[]>([]);

  // Log Coins Filter
  const [selectedLogCoins, setSelectedLogCoins] = useState<string[]>(['BTC', 'ETH', 'SOL', 'DOGE', 'LINK']);

  // Backtest State
  const [backtestRunning, setBacktestRunning] = useState<boolean>(false);
  const [backtestData, setBacktestData] = useState<BacktestResult | null>(null);

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

      const coinLogParts: string[] = [];
      selectedLogCoins.forEach((tag) => {
        const coinObj = VETERAN_COINS.find(c => c.tag === tag);
        if (coinObj) {
          const p = pr[coinObj.sym]?.last_price;
          if (p !== undefined && p !== null) {
            coinLogParts.push(`${tag}=$${p.toLocaleString()}`);
          }
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
      let res = await fetch(`${backendUrl}/api/candles?symbol=${chartSymbol}&resolution=${chartResolution}`).catch(() => null);
      if ((!res || res.status === 404) && backendUrl !== 'http://localhost:8000') {
        res = await fetch(`http://localhost:8000/api/candles?symbol=${chartSymbol}&resolution=${chartResolution}`).catch(() => null);
      }

      if (res && res.ok) {
        const result = await res.json();
        if (result.candles && result.candles.length > 0) {
          setCandles(result.candles);
        }
      }
    } catch (err) {
      console.error('Error fetching candles data:', err);
    }
  };

  const runBacktest = async () => {
    setBacktestRunning(true);
    setBacktestData(null);
    try {
      const res = await fetch(`${backendUrl}/api/backtest?symbol=${chartSymbol}&days=180`);
      const data = await res.json();
      const taskId = data.task_id;

      const pollInterval = setInterval(async () => {
        const pollRes = await fetch(`${backendUrl}/api/backtest-result?task_id=${taskId}`);
        const pollData = await pollRes.json();
        if (pollData.status === 'COMPLETED') {
          clearInterval(pollInterval);
          setBacktestRunning(false);
          setBacktestData(pollData.result);
        } else if (pollData.status === 'ERROR') {
          clearInterval(pollInterval);
          setBacktestRunning(false);
          alert('Backtest failed: ' + pollData.error);
        }
      }, 1000);
    } catch (e) {
      setBacktestRunning(false);
      alert('Failed to launch backtest: ' + e);
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
      const res = await fetch(`${backendUrl}/api/panic`, { method: 'POST' });
      const resData = await res.json();
      alert(resData.message);
      fetchStatus();
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
  const alloc = data?.institutional_allocation;

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
            <h1 style={{ fontSize: '20px', fontWeight: '700', margin: 0 }}>WebTraderBot — Institutional 80/20 Portfolio Terminal</h1>
            <p style={{ fontSize: '12px', color: '#9ca3af', margin: 0 }}>OKX Swaps (80% Delta-Neutral Arbitrage + 20% 1H MTF Scalper R:R 1:1.5)</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button onClick={runBacktest} disabled={backtestRunning} style={{
            background: 'linear-gradient(135deg, #a855f7, #6366f1)',
            color: 'white',
            border: 'none',
            padding: '8px 16px',
            borderRadius: '8px',
            fontWeight: '700',
            fontSize: '12px',
            cursor: backtestRunning ? 'not-allowed' : 'pointer',
            boxShadow: '0 4px 15px rgba(168, 85, 247, 0.4)'
          }}>
            {backtestRunning ? '⏳ Backtesting...' : `🧪 Backtest ${chartSymbol.split('-')[0]} (6 Months)`}
          </button>

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
            ▶️ Start
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
            ⏸️ Pause
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
      </header>

      {/* Backtest Result Modal/Panel */}
      {backtestData && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(0, 240, 144, 0.15), rgba(59, 130, 246, 0.15))',
          border: '1px solid #00f090',
          borderRadius: '16px',
          padding: '18px 22px',
          marginBottom: '24px',
          backdropFilter: 'blur(12px)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ margin: 0, fontSize: '15px', color: '#00f090', fontWeight: '700' }}>
              🧪 Institutional 80/20 Backtest Result: {backtestData.symbol} ({backtestData.days_simulated} Days / {backtestData.candles_analyzed} Candles)
            </h3>
            <span style={{ fontSize: '11px', color: '#38bdf8', fontWeight: '700' }}>{backtestData.combined_portfolio_results.verdict}</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '12px', fontSize: '12px' }}>
            <div>
              <div style={{ color: '#9ca3af' }}>Combined Net Profit</div>
              <div style={{ fontWeight: '700', color: backtestData.combined_portfolio_results.net_profit_usd >= 0 ? '#00f090' : '#ff3b69', fontSize: '15px' }}>
                +${backtestData.combined_portfolio_results.net_profit_usd} (+{backtestData.combined_portfolio_results.net_profit_pct}%)
              </div>
              <div style={{ fontSize: '10px', color: '#9ca3af' }}>+{backtestData.combined_portfolio_results.net_profit_thb} THB</div>
            </div>
            <div>
              <div style={{ color: '#9ca3af' }}>80% Funding Arbitrage</div>
              <div style={{ fontWeight: '700', color: '#38bdf8', fontSize: '14px' }}>
                +${backtestData.allocation_breakdown.funding_arbitrage_80pct.accumulated_cashflow_usd} USD
              </div>
              <div style={{ fontSize: '10px', color: '#9ca3af' }}>+{backtestData.allocation_breakdown.funding_arbitrage_80pct.accumulated_cashflow_thb} THB</div>
            </div>
            <div>
              <div style={{ color: '#9ca3af' }}>20% Scalping Net PnL</div>
              <div style={{ fontWeight: '700', color: backtestData.allocation_breakdown.scalping_engine_20pct.net_profit_usd >= 0 ? '#00f090' : '#ff3b69', fontSize: '14px' }}>
                ${backtestData.allocation_breakdown.scalping_engine_20pct.net_profit_usd} USD
              </div>
              <div style={{ fontSize: '10px', color: '#9ca3af' }}>{backtestData.allocation_breakdown.scalping_engine_20pct.total_trades} Trades</div>
            </div>
            <div>
              <div style={{ color: '#9ca3af' }}>Scalp Win Rate</div>
              <div style={{ fontWeight: '700', color: '#f59e0b', fontSize: '14px' }}>
                {backtestData.allocation_breakdown.scalping_engine_20pct.win_rate_pct}%
              </div>
            </div>
            <div>
              <div style={{ color: '#9ca3af' }}>Max Drawdown</div>
              <div style={{ fontWeight: '700', color: '#ef4444', fontSize: '14px' }}>
                {backtestData.allocation_breakdown.scalping_engine_20pct.max_drawdown_pct}%
              </div>
            </div>
            <div>
              <div style={{ color: '#9ca3af' }}>Final Portfolio</div>
              <div style={{ fontWeight: '700', color: '#00f090', fontSize: '15px' }}>
                ${backtestData.combined_portfolio_results.final_capital_usd} USD
              </div>
              <div style={{ fontSize: '10px', color: '#9ca3af' }}>{backtestData.combined_portfolio_results.final_capital_thb} THB</div>
            </div>
          </div>
        </div>
      )}

      {/* 15 OKX Perpetual Swap Instrument Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '12px',
        marginBottom: '24px'
      }}>
        {VETERAN_COINS.map((coin) => {
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
                borderRadius: '14px',
                padding: '12px',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px', fontSize: '11px', color: '#9ca3af' }}>
                <span style={{ fontWeight: '700', color: isSelected ? '#3b82f6' : '#9ca3af' }}>{coin.tag} ({coin.est})</span>
                <div style={{ display: 'flex', gap: '3px' }}>
                  <button onClick={(e) => { e.stopPropagation(); simTrade(coin.sym, 'LONG'); }} style={{
                    background: '#00f090',
                    color: '#000',
                    border: 'none',
                    padding: '2px 5px',
                    borderRadius: '4px',
                    fontWeight: '700',
                    fontSize: '9px',
                    cursor: 'pointer'
                  }}>
                    + LONG
                  </button>
                  <button onClick={(e) => { e.stopPropagation(); simTrade(coin.sym, 'SHORT'); }} style={{
                    background: '#ff3b69',
                    color: '#fff',
                    border: 'none',
                    padding: '2px 5px',
                    borderRadius: '4px',
                    fontWeight: '700',
                    fontSize: '9px',
                    cursor: 'pointer'
                  }}>
                    - SHORT
                  </button>
                </div>
              </div>
              <div style={{ fontSize: '16px', fontWeight: '700', fontFamily: 'monospace', marginBottom: '3px' }}>
                {price ? `$${price.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '$0.00'}
              </div>
              <div style={{
                fontSize: '10px',
                fontWeight: '600',
                color: sig.includes('BUY') ? '#00f090' : (sig.includes('SELL') ? '#ff3b69' : '#9ca3af')
              }}>
                Signal: {sig}
              </div>
            </div>
          );
        })}
      </div>

      {/* Side-By-Side Row: Interactive Candlestick Chart (Left 3fr) + Terminal Feed Log (Right 2fr) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '3fr 2fr',
        gap: '20px',
        marginBottom: '24px'
      }}>
        {/* Left Box: Candlestick Chart */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <h2 style={{ fontSize: '14px', fontWeight: '700', margin: 0 }}>📊 Candlestick & Indicators Chart ({chartSymbol})</h2>
              <div style={{ display: 'flex', gap: '4px' }}>
                {['5', '15', '60'].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setChartResolution(tf)}
                    style={{
                      background: chartResolution === tf ? '#3b82f6' : 'rgba(255, 255, 255, 0.05)',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      color: chartResolution === tf ? '#fff' : '#9ca3af',
                      padding: '2px 6px',
                      borderRadius: '4px',
                      fontSize: '10px',
                      fontWeight: '700',
                      cursor: 'pointer'
                    }}
                  >
                    {tf === '60' ? '1h' : `${tf}m`}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', gap: '8px', fontSize: '10px', fontWeight: '600' }}>
              <span style={{ color: '#a855f7' }}>🟪 EMA 200</span>
              <span style={{ color: '#3b82f6' }}>🔷 EMA 9</span>
              <span style={{ color: '#f97316' }}>🍊 EMA 21</span>
              <span style={{ color: '#38bdf8' }}>🩵 VWAP</span>
              <span style={{ color: '#ef4444' }}>🔴 ADX (14)</span>
            </div>
          </div>

          <CandlestickChart candles={candles} symbol={chartSymbol} resolution={chartResolution} />
        </div>

        {/* Right Box: Terminal Feed Log */}
        <div style={{
          background: 'rgba(18, 24, 38, 0.75)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between'
        }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <span style={{ fontWeight: '700', fontSize: '14px' }}>📡 Terminal Feed Log</span>
              <button onClick={() => { fetchStatus(); fetchCandles(); }} style={{
                background: 'transparent',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                color: '#9ca3af',
                padding: '3px 8px',
                borderRadius: '6px',
                fontSize: '11px',
                cursor: 'pointer'
              }}>
                Refresh
              </button>
            </div>

            <div style={{ display: 'flex', gap: '4px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '12px' }}>
              <span style={{ fontSize: '10px', color: '#9ca3af', marginRight: '2px' }}>Log Coins:</span>
              <button onClick={() => setSelectedLogCoins(VETERAN_COINS.map(c => c.tag))} style={{
                background: 'rgba(59, 130, 246, 0.2)',
                border: '1px solid #3b82f6',
                color: '#3b82f6',
                borderRadius: '4px',
                padding: '2px 5px',
                fontSize: '9px',
                fontWeight: '700',
                cursor: 'pointer'
              }}>
                All 15
              </button>
              <button onClick={() => setSelectedLogCoins(['BTC', 'ETH', 'SOL', 'DOGE', 'LINK'])} style={{
                background: 'rgba(0, 240, 144, 0.2)',
                border: '1px solid #00f090',
                color: '#00f090',
                borderRadius: '4px',
                padding: '2px 5px',
                fontSize: '9px',
                fontWeight: '700',
                cursor: 'pointer'
              }}>
                Top 5
              </button>
              {VETERAN_COINS.map((coin) => {
                const isChecked = selectedLogCoins.includes(coin.tag);
                return (
                  <button
                    key={coin.tag}
                    onClick={() => toggleLogCoin(coin.tag)}
                    style={{
                      background: isChecked ? '#3b82f6' : 'rgba(255, 255, 255, 0.05)',
                      color: isChecked ? '#ffffff' : '#6b7280',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      borderRadius: '4px',
                      padding: '2px 4px',
                      fontSize: '9px',
                      fontWeight: '700',
                      cursor: 'pointer'
                    }}
                  >
                    {isChecked ? `✓ ${coin.tag}` : coin.tag}
                  </button>
                );
              })}
            </div>

            <div style={{
              background: '#06080d',
              border: '1px solid rgba(255, 255, 255, 0.05)',
              borderRadius: '12px',
              padding: '14px',
              fontFamily: 'monospace',
              fontSize: '11px',
              color: '#a7f3d0',
              height: '410px',
              overflowY: 'auto',
              lineHeight: '1.6'
            }}>
              {logs.map((log, idx) => (
                <div key={idx} style={{ marginBottom: '4px', wordBreak: 'break-all' }}>{log}</div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Institutional 80/20 Allocation & Portfolio Summary Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
        {/* 80% Weight Funding Rate Arbitrage Engine */}
        <div style={{
          background: 'rgba(18, 24, 38, 0.75)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(0, 240, 144, 0.3)',
          borderRadius: '16px',
          padding: '20px'
        }}>
          <h2 style={{ fontWeight: '700', fontSize: '14px', marginBottom: '16px', color: '#00f090' }}>
            🏛️ 80% Funding Arbitrage Engine
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Allocated Capital (80%)</span>
              <span style={{ fontWeight: '700', color: '#00f090', fontFamily: 'monospace' }}>$8,000.00 USD</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Annual Funding APY</span>
              <span style={{ fontWeight: '700', color: '#38bdf8', fontFamily: 'monospace' }}>~15.33% APY</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Est. Daily Cash Flow</span>
              <span style={{ fontWeight: '700', color: '#a855f7' }}>+$3.36 USD / Day</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#9ca3af' }}>Delta-Neutral Shield</span>
              <span style={{ fontWeight: '600', color: '#00f090' }}>🟢 ACTIVE (1x Spot + 1x Short)</span>
            </div>
          </div>
        </div>

        {/* 20% Weight 15m Scalping Engine */}
        <div style={{
          background: 'rgba(18, 24, 38, 0.75)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          borderRadius: '16px',
          padding: '20px'
        }}>
          <h2 style={{ fontWeight: '700', fontSize: '14px', marginBottom: '16px', color: '#3b82f6' }}>
            🎯 20% Scalping Engine (1H MTF)
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Allocated Capital (20%)</span>
              <span style={{ fontWeight: '700', color: '#3b82f6', fontFamily: 'monospace' }}>$2,000.00 USD</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Macro Filter</span>
              <span style={{ fontWeight: '700', color: '#00f090' }}>1H Trend Alignment (EMA800)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Risk-to-Reward Ratio</span>
              <span style={{ fontWeight: '700', color: '#f59e0b' }}>R:R = 1 : 1.5 (TP 2.25x ATR)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#9ca3af' }}>Max Drawdown Guard</span>
              <span style={{ fontWeight: '600', color: '#00f090' }}>🟢 Restricted to 20% Pool</span>
            </div>
          </div>
        </div>

        {/* Active Positions Table */}
        <div style={{
          background: 'rgba(18, 24, 38, 0.75)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '20px'
        }}>
          <h2 style={{ fontWeight: '600', fontSize: '14px', marginBottom: '12px' }}>📍 Active Positions</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px' }}>
            <thead>
              <tr style={{ color: '#9ca3af', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', textAlign: 'left' }}>
                <th style={{ paddingBottom: '6px' }}>Symbol</th>
                <th style={{ paddingBottom: '6px' }}>Side</th>
                <th style={{ paddingBottom: '6px' }}>Entry</th>
                <th style={{ paddingBottom: '6px' }}>SL / TP</th>
              </tr>
            </thead>
            <tbody>
              {data?.active_positions && data.active_positions.length > 0 ? (
                data.active_positions.map((pos) => {
                  const isLong = pos.side === 'LONG';
                  return (
                    <tr key={pos.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      <td style={{ padding: '6px 0', fontWeight: 'bold' }}>{pos.symbol.split('-')[0]}</td>
                      <td style={{ padding: '6px 0' }}>
                        <span style={{
                          padding: '2px 5px',
                          borderRadius: '4px',
                          fontWeight: '700',
                          fontSize: '9px',
                          background: isLong ? 'rgba(0, 240, 144, 0.15)' : 'rgba(255, 59, 105, 0.15)',
                          color: isLong ? '#00f090' : '#ff3b69'
                        }}>
                          {pos.side}
                        </span>
                      </td>
                      <td style={{ padding: '6px 0', fontFamily: 'monospace' }}>${pos.entry_price?.toLocaleString()}</td>
                      <td style={{ padding: '6px 0', fontFamily: 'monospace' }}>
                        <span style={{ color: '#ff3b69' }}>${pos.sl_price?.toLocaleString()}</span> / <span style={{ color: '#00f090' }}>${pos.tp_price?.toLocaleString()}</span>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={4} style={{ padding: '16px 0', color: '#6b7280', textAlign: 'center' }}>No active positions</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
