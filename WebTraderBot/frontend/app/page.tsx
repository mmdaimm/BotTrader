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
    ema50_4h?: number;
    ema200_4h?: number;
    supertrend?: number;
    st_direction?: string;
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
  tp1_target?: number;
  tp1_done?: boolean;
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
    swing_engine_20pct?: {
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
  days_simulated?: number;
  candles_analyzed?: number;
  initial_capital_usd?: number;
  initial_capital_thb?: number;
  architecture?: string;
  allocation_breakdown?: {
    funding_arbitrage_80pct?: {
      allocated_capital_usd?: number;
      final_capital_usd?: number;
      accumulated_cashflow_usd?: number;
      accumulated_cashflow_thb?: number;
      annual_apy_pct?: number;
    };
    scalping_engine_20pct?: {
      allocated_capital_usd?: number;
      final_capital_usd?: number;
      net_profit_usd?: number;
      net_profit_pct?: number;
      profit_factor?: number;
      total_trades?: number;
      win_rate_pct?: number;
      max_drawdown_pct?: number;
    };
  };
  combined_portfolio_results?: {
    final_capital_usd?: number;
    final_capital_thb?: number;
    net_profit_usd?: number;
    net_profit_thb?: number;
    net_profit_pct?: number;
    verdict?: string;
  };
  friction_deductions?: string;
}

const DEFAULT_BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://bottrader-production.up.railway.app';

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
  { sym: 'BNB-USDT-SWAP', label: 'BNB Perpetual', tag: 'BNB', est: '2017' },
  { sym: 'NEAR-USDT-SWAP', label: 'NEAR Perpetual', tag: 'NEAR', est: '2020' },
  { sym: 'UNI-USDT-SWAP', label: 'UNI Perpetual', tag: 'UNI', est: '2020' },
  { sym: 'FIL-USDT-SWAP', label: 'FIL Perpetual', tag: 'FIL', est: '2020' },
  { sym: 'ALGO-USDT-SWAP', label: 'ALGO Perpetual', tag: 'ALGO', est: '2019' }
];

export default function Dashboard() {
  const [backendUrl, setBackendUrl] = useState<string>(DEFAULT_BACKEND);
  const [data, setData] = useState<StatusResponse | null>(null);
  const [botState, setBotState] = useState<string>('RUNNING');
  const [logs, setLogs] = useState<string[]>([
    'Initializing Next.js OKX 15-Veteran Institutional Portfolio...',
    `Target Backend: ${DEFAULT_BACKEND}`
  ]);
  const [tradingMode, setTradingMode] = useState<string>('PAPER');
  const [sidewayModeEnabled, setSidewayModeEnabled] = useState<boolean>(false);
  const [sidewayState, setSidewayState] = useState<string>('DISABLED');
  const [orderbook, setOrderbook] = useState<{ bids: number[][]; asks: number[][]; symbol?: string }>({ bids: [], asks: [] });
  const [okxBalance, setOkxBalance] = useState<{ total_equity?: number; available_margin?: number; margin_ratio?: number; status?: string; message?: string }>({});
  const [cashflowSummary, setCashflowSummary] = useState<any>(null);

  // Chart State
  const [chartSymbol, setChartSymbol] = useState<string>('BTC-USDT-SWAP');
  const [chartResolution, setChartResolution] = useState<string>('240');
  const [candles, setCandles] = useState<CandleData[]>([]);

  useEffect(() => {
    const fetchOkxData = async () => {
      try {
        const obRes = await fetch(`${backendUrl}/api/okx/orderbook?symbol=${chartSymbol}&depth=6`).catch(() => null);
        if (obRes && obRes.ok) {
          const obData = await obRes.json();
          if (obData.bids && obData.asks) setOrderbook(obData);
        }
        const balRes = await fetch(`${backendUrl}/api/okx/balance`).catch(() => null);
        if (balRes && balRes.ok) {
          const balData = await balRes.json();
          setOkxBalance(balData);
        }
        const cfRes = await fetch(`${backendUrl}/api/cashflow-summary`).catch(() => null);
        if (cfRes && cfRes.ok) {
          const cfData = await cfRes.json();
          setCashflowSummary(cfData);
        }
      } catch (e) {
        console.error('Error fetching OKX orderbook/balance:', e);
      }
    };
    fetchOkxData();
    const okxInterval = setInterval(fetchOkxData, 3000);
    return () => clearInterval(okxInterval);
  }, [chartSymbol, backendUrl]);

  // Log Coins Filter
  const [selectedLogCoins, setSelectedLogCoins] = useState<string[]>(['BTC', 'ETH', 'SOL', 'DOGE', 'LINK']);

  // Backtest State
  const [backtestDays, setBacktestDays] = useState<number>(180);
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
      
      // Failover fallback check if primary backend endpoint fails
      if (!res || !res.ok) {
        if (backendUrl !== 'http://localhost:8000') {
          res = await fetch(`http://localhost:8000/api/status`).catch(() => null);
          if (res && res.ok) setBackendUrl('http://localhost:8000');
        } else {
          const railwayUrl = process.env.NEXT_PUBLIC_RAILWAY_URL;
          if (railwayUrl) {
            res = await fetch(`${railwayUrl}/api/status`).catch(() => null);
            if (res && res.ok) setBackendUrl(railwayUrl);
          }
        }
      }

      if (!res || !res.ok) {
        setBotState('REBUILDING');
        return;
      }

      const result: StatusResponse = await res.json();
      setData(result);
      if (result.bot_state || result.status) {
        setBotState(result.bot_state || result.status);
      }
      if (result.trading_mode) setTradingMode(result.trading_mode);
      if (result.sideway_mode_enabled !== undefined) setSidewayModeEnabled(result.sideway_mode_enabled);
      if (result.sideway_state) setSidewayState(result.sideway_state);

      const now = new Date().toLocaleTimeString();
      const pr = result.pair_results || {};

      const coinLogParts: string[] = [];
      selectedLogCoins.forEach((tag) => {
        const coinObj = VETERAN_COINS.find(c => c.tag === tag);
        if (coinObj) {
          const p = pr[coinObj.sym]?.last_price;
          if (p !== undefined && p !== null && p > 0) {
            coinLogParts.push(`${tag}=$${p.toLocaleString()}`);
          }
        }
      });

      if (coinLogParts.length > 0) {
        setLogs((prev) => [
          ...prev.slice(-18),
          `[${now}] State: ${result.bot_state || result.status} | Core-Satellite | ${coinLogParts.join(' | ')}`
        ]);
      }
    } catch (err) {
      console.error('Error fetching backend status:', err);
      setBotState('REBUILDING');
    }
  };

  const fetchCandles = async () => {
    try {
      let res = await fetch(`${backendUrl}/api/candles?symbol=${chartSymbol}&resolution=${chartResolution}`).catch(() => null);
      if ((!res || !res.ok) && backendUrl !== 'http://localhost:8000') {
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
      const res = await fetch(`${backendUrl}/api/backtest?symbol=${chartSymbol}&days=${backtestDays}`);
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
    }, 4000);
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

  const toggleSidewayMode = async () => {
    const nextState = !sidewayModeEnabled;
    const res = await fetch(`${backendUrl}/api/toggle-sideway-mode?enabled=${nextState}`, { method: 'POST' });
    const resData = await res.json();
    setSidewayModeEnabled(resData.sideway_mode_enabled);
    setSidewayState(resData.sideway_state);
    alert(`15m Sideway Mode updated: ${resData.message}`);
    fetchStatus();
  };

  const seedDemoPositions = async () => {
    const res = await fetch(`${backendUrl}/api/seed-demo-positions`, { method: 'POST' });
    const resData = await res.json();
    alert(resData.message);
    fetchStatus();
  };

  const simTrade = async (symbol: string, side: string) => {
    const res = await fetch(`${backendUrl}/api/sim-buy?symbol=${symbol}&side=${side}`, { method: 'POST' });
    const resData = await res.json();
    alert(resData.message);
    fetchStatus();
    fetchCandles();
  };

  const closePosition = async (symbol: string) => {
    const coinTag = symbol.split('-')[0];
    if (confirm(`⚡ ยืนยันการปิดออเดอร์ทันที (OKX Taker Market Close 100%) สำหรับ ${coinTag} หรือไม่?`)) {
      try {
        const res = await fetch(`${backendUrl}/api/close-position?symbol=${symbol}`, { method: 'POST' });
        const resData = await res.json();
        if (resData.status === 'SUCCESS') {
          alert(`🟢 ${resData.message}`);
          fetchStatus();
        } else {
          alert(`🔴 ${resData.message}`);
        }
      } catch (err) {
        alert(`🔴 เกิดข้อผิดพลาดในการปิดออเดอร์: ${err}`);
      }
    }
  };

  const editTp1Target = async (symbol: string, currentTp1: number) => {
    const coinTag = symbol.split('-')[0];
    const inputVal = prompt(`✏️ กำหนดเป้าหมายราคา TP1 ใหม่สำหรับ ${coinTag} (เป้าหมายปัจจุบัน: $${currentTp1?.toLocaleString()}):`, currentTp1 ? String(currentTp1) : '');
    if (!inputVal) return;
    const newTp1 = parseFloat(inputVal);
    if (isNaN(newTp1) || newTp1 <= 0) {
      alert('🔴 กรุณาระบุตัวเลขราคาเป้าหมายที่ถูกต้อง');
      return;
    }
    try {
      const res = await fetch(`${backendUrl}/api/update-tp1?symbol=${symbol}&new_tp1=${newTp1}`, { method: 'POST' });
      const resData = await res.json();
      if (resData.status === 'SUCCESS') {
        alert(`🟢 ${resData.message}`);
        fetchStatus();
      } else {
        alert(`🔴 ${resData.message}`);
      }
    } catch (err) {
      alert(`🔴 เกิดข้อผิดพลาดในการปรับราคา TP1: ${err}`);
    }
  };

  const clearDataHistory = async () => {
    if (confirm("🗑️ ยืนยันการล้างข้อมูล Active Positions และ Closed Trades History ทั้งหมดออกจากระบบใช่หรือไม่?\n\n(การล้างนี้จะลบออเดอร์เก่าออกจาก SQLite DB และความจำเครื่องอย่างถาวร)")) {
      try {
        const res = await fetch(`${backendUrl}/api/clear-positions-history`, { method: 'POST' });
        const resData = await res.json();
        if (resData.status === 'SUCCESS') {
          alert(`🟢 ${resData.message}`);
          fetchStatus();
        } else {
          alert(`🔴 ${resData.message}`);
        }
      } catch (err) {
        alert(`🔴 เกิดข้อผิดพลาดในการล้างข้อมูล: ${err}`);
      }
    }
  };

  const pairs = data?.pair_results || {};
  const summary = data?.paper_summary;

  // Extract Backtest Values with Robust Fallbacks
  const combinedProfitUsd = backtestData?.combined_portfolio_results?.net_profit_usd ?? 0;
  const combinedProfitPct = backtestData?.combined_portfolio_results?.net_profit_pct ?? 0;
  const combinedProfitThb = backtestData?.combined_portfolio_results?.net_profit_thb ?? 0;
  const combinedFinalUsd = backtestData?.combined_portfolio_results?.final_capital_usd ?? 10000;
  const combinedFinalThb = backtestData?.combined_portfolio_results?.final_capital_thb ?? 355000;
  const verdictStr = backtestData?.combined_portfolio_results?.verdict || '🟢 POSITIVE NET PROFIT';

  const fundingCashflowUsd = backtestData?.allocation_breakdown?.funding_arbitrage_80pct?.accumulated_cashflow_usd ?? 0;
  const fundingCashflowThb = backtestData?.allocation_breakdown?.funding_arbitrage_80pct?.accumulated_cashflow_thb ?? 0;

  const scalpNetUsd = backtestData?.allocation_breakdown?.scalping_engine_20pct?.net_profit_usd ?? 0;
  const scalpTradesCount = backtestData?.allocation_breakdown?.scalping_engine_20pct?.total_trades ?? 0;
  const scalpWinRate = backtestData?.allocation_breakdown?.scalping_engine_20pct?.win_rate_pct ?? 0;
  const scalpMaxDd = backtestData?.allocation_breakdown?.scalping_engine_20pct?.max_drawdown_pct ?? 0;

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#0a0d14',
      color: '#f3f4f6',
      padding: '24px',
      fontFamily: 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      backgroundImage: 'radial-gradient(circle at 15% 15%, rgba(0, 240, 144, 0.05) 0%, transparent 40%), radial-gradient(circle at 85% 85%, rgba(139, 92, 246, 0.05) 0%, transparent 40%)'
    }}>
      {/* Header Bar with Glowing Live Bot Status Badge */}
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
            width: '42px',
            height: '42px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #00f090, #3b82f6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold',
            fontSize: '22px',
            color: '#000',
            boxShadow: '0 4px 15px rgba(0, 240, 144, 0.3)'
          }}>
            O
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h1 style={{ fontSize: '20px', fontWeight: '700', margin: 0 }}>WebTraderBot — Core-Satellite Production Engine</h1>
              
              {/* Glowing Bot Status Indicator Dot */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                background: botState === 'RUNNING' || botState === 'OK' ? 'rgba(0, 240, 144, 0.15)' : (botState === 'PAUSED' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)'),
                border: `1px solid ${botState === 'RUNNING' || botState === 'OK' ? 'rgba(0, 240, 144, 0.4)' : (botState === 'PAUSED' ? 'rgba(245, 158, 11, 0.4)' : 'rgba(239, 68, 68, 0.4)')}`,
                padding: '3px 9px',
                borderRadius: '20px',
                fontSize: '11px',
                fontWeight: '700',
                color: botState === 'RUNNING' || botState === 'OK' ? '#00f090' : (botState === 'PAUSED' ? '#f59e0b' : '#ef4444')
              }}>
                <span style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: botState === 'RUNNING' || botState === 'OK' ? '#00f090' : (botState === 'PAUSED' ? '#f59e0b' : '#ef4444'),
                  boxShadow: `0 0 10px ${botState === 'RUNNING' || botState === 'OK' ? '#00f090' : (botState === 'PAUSED' ? '#f59e0b' : '#ef4444')}`
                }} />
                {botState === 'RUNNING' || botState === 'OK' ? 'RUNNING LIVE' : (botState === 'PAUSED' ? 'PAUSED' : 'REBUILDING...')}
              </div>
            </div>
            <p style={{ fontSize: '12px', color: '#9ca3af', margin: 0 }}>OKX Spot &amp; Futures (70% Core Spot Rebalancing + 30% Satellite Futures Grid Engine)</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <select 
              value={backtestDays} 
              onChange={(e) => setBacktestDays(Number(e.target.value))}
              style={{
                background: 'rgba(168, 85, 247, 0.15)',
                border: '1px solid rgba(168, 85, 247, 0.4)',
                color: '#d8b4fe',
                padding: '7px 8px',
                borderRadius: '8px',
                fontSize: '11px',
                fontWeight: '700',
                cursor: 'pointer',
                outline: 'none'
              }}
            >
              <option value={180} style={{ background: '#0a0d14', color: '#fff' }}>6 Months (180d)</option>
              <option value={365} style={{ background: '#0a0d14', color: '#fff' }}>1 Year (365d)</option>
            </select>

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
              {backtestRunning ? '⏳ Backtesting...' : `🧪 Backtest ${chartSymbol.split('-')[0]} (${backtestDays === 365 ? '1 Year' : '6 Months'})`}
            </button>
          </div>

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

          <button onClick={toggleSidewayMode} style={{
            background: sidewayState === 'ACTIVE' 
              ? 'rgba(16, 185, 129, 0.15)' 
              : sidewayState === 'STOPPING' 
              ? 'rgba(245, 158, 11, 0.15)' 
              : 'rgba(107, 114, 128, 0.15)',
            border: sidewayState === 'ACTIVE' 
              ? '1px solid rgba(16, 185, 129, 0.4)' 
              : sidewayState === 'STOPPING' 
              ? '1px solid rgba(245, 158, 11, 0.4)' 
              : '1px solid rgba(107, 114, 128, 0.3)',
            color: sidewayState === 'ACTIVE' ? '#10b981' : sidewayState === 'STOPPING' ? '#f59e0b' : '#9ca3af',
            padding: '8px 14px',
            borderRadius: '8px',
            fontWeight: '700',
            fontSize: '12px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            {sidewayState === 'ACTIVE' ? '🟢 Sideway Mode: ON' : sidewayState === 'STOPPING' ? '🟡 Sideway Mode: STOPPING' : '⚪ Sideway Mode: OFF'}
          </button>

          <div style={{
            background: 'rgba(16, 185, 129, 0.15)',
            border: '1px solid rgba(16, 185, 129, 0.4)',
            color: '#10b981',
            padding: '8px 14px',
            borderRadius: '8px',
            fontWeight: '700',
            fontSize: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            🛡️ Active Monitoring ({sidewayModeEnabled ? '15m Engine Loop' : '30m Engine Loop'}: Active)
          </div>

          <button onClick={seedDemoPositions} style={{
            background: 'rgba(168, 85, 247, 0.15)',
            border: '1px solid rgba(168, 85, 247, 0.4)',
            color: '#c084fc',
            padding: '8px 14px',
            borderRadius: '8px',
            fontWeight: '700',
            fontSize: '12px',
            cursor: 'pointer'
          }}>
            🔄 Restore Active Demo Positions
          </button>

          <button onClick={clearDataHistory} style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            color: '#f87171',
            padding: '8px 14px',
            borderRadius: '8px',
            fontWeight: '700',
            fontSize: '12px',
            cursor: 'pointer'
          }}>
            🗑️ Clear Demo Data
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
              🧪 Institutional 80/20 Backtest Result: {backtestData.symbol} ({backtestData.days_simulated || 180} Days / {backtestData.candles_analyzed || 18000} Candles)
            </h3>
            <span style={{ fontSize: '11px', color: '#38bdf8', fontWeight: '700' }}>{verdictStr}</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '12px', fontSize: '12px' }}>
            <div>
              <div style={{ color: '#9ca3af' }}>Combined Net Profit</div>
              <div style={{ fontWeight: '700', color: combinedProfitUsd >= 0 ? '#00f090' : '#ff3b69', fontSize: '15px' }}>
                {combinedProfitUsd >= 0 ? '+' : ''}${combinedProfitUsd} ({combinedProfitPct >= 0 ? '+' : ''}{combinedProfitPct}%)
              </div>
              <div style={{ fontSize: '10px', color: '#9ca3af' }}>{combinedProfitThb >= 0 ? '+' : ''}{combinedProfitThb} THB</div>
            </div>
            <div>
              <div style={{ color: '#9ca3af' }}>80% Funding Arbitrage</div>
              <div style={{ fontWeight: '700', color: '#38bdf8', fontSize: '14px' }}>
                +${fundingCashflowUsd} USD
              </div>
              <div style={{ fontSize: '10px', color: '#9ca3af' }}>+{fundingCashflowThb} THB</div>
            </div>
            <div>
              <div style={{ color: '#9ca3af' }}>20% 4H Swing Net PnL</div>
              <div style={{ fontWeight: '700', color: scalpNetUsd >= 0 ? '#00f090' : '#ff3b69', fontSize: '14px' }}>
                ${scalpNetUsd} USD
              </div>
              <div style={{ fontSize: '10px', color: '#9ca3af' }}>{scalpTradesCount} Trades</div>
            </div>
            <div>
              <div style={{ color: '#9ca3af' }}>4H Swing Win Rate</div>
              <div style={{ fontWeight: '700', color: '#f59e0b', fontSize: '14px' }}>
                {scalpWinRate}%
              </div>
            </div>
            <div>
              <div style={{ color: '#9ca3af' }}>Max Drawdown</div>
              <div style={{ fontWeight: '700', color: '#ef4444', fontSize: '14px' }}>
                {scalpMaxDd}%
              </div>
            </div>
            <div>
              <div style={{ color: '#9ca3af' }}>Final Portfolio</div>
              <div style={{ fontWeight: '700', color: '#00f090', fontSize: '15px' }}>
                ${combinedFinalUsd} USD
              </div>
              <div style={{ fontSize: '10px', color: '#9ca3af' }}>{combinedFinalThb} THB</div>
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
                {price && price > 0 ? `$${price.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '$...'}
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
                {['5', '15', '60', '240'].map((tf) => (
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
                    {tf === '240' ? '4h' : (tf === '60' ? '1h' : `${tf}m`)}
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

        {/* Right Box: OKX Live Orderbook Depth Ladder */}
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
              <span style={{ fontWeight: '700', fontSize: '14px', color: '#60a5fa' }}>📖 OKX Orderbook Depth</span>
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

            <div style={{ fontSize: '12px', fontWeight: '700', color: '#ffffff', marginBottom: '12px' }}>
              Selected Asset: <span style={{ color: '#00f090' }}>{chartSymbol}</span>
            </div>

            {/* OKX Account Balance & Equity Gauge Card */}
            <div style={{ marginBottom: '16px', background: okxBalance.status === 'SUCCESS' ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(59, 130, 246, 0.15))' : 'rgba(18, 24, 38, 0.75)', padding: '14px', borderRadius: '12px', border: okxBalance.status === 'SUCCESS' ? '1px solid #10b981' : '1px solid rgba(245, 158, 11, 0.4)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontWeight: '700', color: okxBalance.status === 'SUCCESS' ? '#10b981' : '#f59e0b', marginBottom: '8px' }}>
                <span>💳 OKX Account Balance (Demo USDT)</span>
                <span>{okxBalance.status === 'SUCCESS' ? '🟢 OKX DEMO SYNCED' : '⚠️ UNLINKED (FALLBACK)'}</span>
              </div>
              <div style={{ fontSize: '20px', fontWeight: '800', color: '#ffffff', fontFamily: 'monospace', marginBottom: '4px' }}>
                ${(okxBalance.total_equity ?? data?.paper_summary?.current_capital ?? 10000.0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} <span style={{ fontSize: '11px', color: '#10b981' }}>USD</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#9ca3af' }}>
                <span>Available Margin: <strong style={{ color: '#60a5fa' }}>${(okxBalance.available_margin ?? data?.paper_summary?.available_capital ?? 9665.97).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong></span>
                <span>API Connection: <strong style={{ color: okxBalance.status === 'SUCCESS' ? '#00f090' : '#f59e0b' }}>{okxBalance.status === 'SUCCESS' ? 'Live OKX Demo Account' : (okxBalance.message || 'Key Required')}</strong></span>
              </div>
            </div>

            {/* OKX Live Orderbook Depth Ladder */}
            <div style={{ background: 'rgba(11, 15, 25, 0.8)', padding: '14px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontWeight: '700', marginBottom: '10px', color: '#9ca3af', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', paddingBottom: '6px' }}>
                <span>Order Price (USDT)</span>
                <span>Contracts (sz)</span>
              </div>
              
              {/* Asks (Sells) */}
              <div style={{ fontSize: '11px', fontFamily: 'monospace', marginBottom: '6px' }}>
                {(orderbook.asks || []).slice(0, 6).reverse().map((ask, idx) => (
                  <div key={`ask-${idx}`} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', color: '#ff3b69' }}>
                    <span>Ask ${ask[0]?.toLocaleString()}</span>
                    <span>{ask[1]?.toLocaleString()} sz</span>
                  </div>
                ))}
              </div>

              {/* Spread / Current Price */}
              <div style={{ textAlign: 'center', padding: '8px 0', color: '#10b981', fontWeight: '700', fontSize: '13px', borderTop: '1px dashed rgba(255, 255, 255, 0.15)', borderBottom: '1px dashed rgba(255, 255, 255, 0.15)', margin: '6px 0', background: 'rgba(16, 185, 129, 0.05)', borderRadius: '6px' }}>
                ⚡ ${pairs[chartSymbol]?.last_price ? pairs[chartSymbol].last_price.toLocaleString() : '---'} USD
              </div>

              {/* Bids (Buys) */}
              <div style={{ fontSize: '11px', fontFamily: 'monospace', marginTop: '6px' }}>
                {(orderbook.bids || []).slice(0, 6).map((bid, idx) => (
                  <div key={`bid-${idx}`} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', color: '#00f090' }}>
                    <span>Bid ${bid[0]?.toLocaleString()}</span>
                    <span>{bid[1]?.toLocaleString()} sz</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Institutional 80/20 Allocation & Portfolio Summary Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
        {/* 70% Core Engine: Spot Portfolio Rebalancing */}
        <div style={{
          background: 'rgba(18, 24, 38, 0.75)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(0, 240, 144, 0.3)',
          borderRadius: '16px',
          padding: '20px'
        }}>
          <h2 style={{ fontWeight: '700', fontSize: '14px', marginBottom: '16px', color: '#00f090' }}>
            🏛️ 70% Core Engine (Spot Portfolio Rebalance)
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Allocated Capital (70%)</span>
              <span style={{ fontWeight: '700', color: '#00f090', fontFamily: 'monospace' }}>
                ${((cashflowSummary?.core_rebalance_70pct?.allocated_capital) ?? ((okxBalance.total_equity ?? 10000.0) * 0.7)).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Strategy Architecture</span>
              <span style={{ fontWeight: '700', color: '#38bdf8' }}>
                Shannon's Demon (Volatility Harvesting)
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Macro Target Weights</span>
              <span style={{ fontWeight: '700', color: '#a855f7' }}>
                {cashflowSummary?.core_rebalance_70pct?.macro_regime || 'BTC 40% | ETH 30% | USDT 30%'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#9ca3af' }}>Dual-Factor Filter</span>
              <span style={{ fontWeight: '600', color: '#00f090' }}>
                🟢 Drift Threshold &ge; 5.0% + Cost Barrier
              </span>
            </div>
          </div>
        </div>

        {/* 30% Satellite Engine: Futures Geometric Grid Trading */}
        <div style={{
          background: 'rgba(18, 24, 38, 0.75)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(59, 130, 246, 0.3)',
          borderRadius: '16px',
          padding: '20px'
        }}>
          <h2 style={{ fontWeight: '700', fontSize: '14px', marginBottom: '16px', color: '#3b82f6' }}>
            🛰️ 30% Satellite Engine (Futures Geometric Grid)
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Allocated Capital (30%)</span>
              <span style={{ fontWeight: '700', color: '#3b82f6', fontFamily: 'monospace' }}>
                ${((cashflowSummary?.satellite_grid_30pct?.allocated_capital) ?? ((okxBalance.total_equity ?? 10000.0) * 0.3)).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Grid Range &amp; Spacing</span>
              <span style={{ fontWeight: '700', color: '#00f090' }}>Bollinger Bands (20,2 4H) + 1.5x ATR 15m</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
              <span style={{ color: '#9ca3af' }}>Profit / Grid Barrier</span>
              <span style={{ fontWeight: '700', color: '#f59e0b' }}>G_profit &ge; 0.3% (Fee Protection)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#9ca3af' }}>Regime Trend Guard</span>
              <span style={{ fontWeight: '600', color: '#00f090' }}>
                🟢 Active when ADX (4H) &lt; 22 (Sideway Regime)
              </span>
            </div>
          </div>
        </div>

        {/* Active Positions Table & Closed Trades History */}
        <div style={{
          background: 'rgba(18, 24, 38, 0.75)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '20px'
        }}>
          <h2 style={{ fontWeight: '600', fontSize: '14px', marginBottom: '12px', color: '#00f090' }}>📍 Active Positions</h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11px', marginBottom: '20px' }}>
            <thead>
              <tr style={{ color: '#9ca3af', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', textAlign: 'left' }}>
                <th style={{ paddingBottom: '6px' }}>Symbol</th>
                <th style={{ paddingBottom: '6px' }}>Strategy (โหมด)</th>
                <th style={{ paddingBottom: '6px' }}>Side</th>
                <th style={{ paddingBottom: '6px' }}>Entry</th>
                <th style={{ paddingBottom: '6px' }}>Unrealized PnL (กำไร/ขาดทุนเรียลไทม์)</th>
                <th style={{ paddingBottom: '6px' }}>SL / TP1</th>
                <th style={{ paddingBottom: '6px' }}>Action (จัดการออเดอร์)</th>
              </tr>
            </thead>
            <tbody>
              {(() => {
                const runningPositions = (data?.active_positions || []).filter(pos => pos.status === 'OPEN');
                return runningPositions.length > 0 ? (
                  runningPositions.map((pos) => {
                    const isLong = pos.side === 'LONG';
                    const isTp1Done = pos.tp1_done ?? false;
                    const isSideway = pos.strategy_type === 'SIDEWAY_15M' || (pos.id && pos.id.startsWith('SD-'));
                  
                  const item = pairs[pos.symbol];
                  const lastPrice = item?.last_price;
                  let pnl = pos.unrealized_pnl ?? 0.0;
                  let pnlPct = pos.pnl_pct ?? pos.unrealized_pnl_pct ?? 0.0;

                  if (typeof pos.pnl_pct === 'number' && pos.pnl_pct !== 0) {
                    pnlPct = pos.pnl_pct;
                  } else if (lastPrice && pos.entry_price && pos.qty) {
                    if (isLong) {
                      pnl = (lastPrice - pos.entry_price) * pos.qty;
                    } else {
                      pnl = (pos.entry_price - lastPrice) * pos.qty;
                    }
                    const orderVal = pos.order_value || (pos.qty * pos.entry_price) || 1.0;
                    pnlPct = (pnl / orderVal) * 100.0;
                  }
                  const isProfit = pnl >= 0;
                  const slVal = pos.sl_price || pos.sl || 0;
                  const tpVal = pos.tp1_target || pos.tp_price || pos.tp || 0;

                  return (
                    <tr key={pos.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      <td style={{ padding: '6px 0', fontWeight: 'bold' }}>
                        {pos.symbol.split('-')[0]}
                        {pos.okx_order_id && (
                          <div style={{ fontSize: '9px', color: '#00f090', fontWeight: '500' }}>
                            🟢 OKX Order #{pos.okx_order_id}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: '6px 0' }}>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontWeight: '700',
                          fontSize: '9px',
                          background: isSideway ? 'rgba(168, 85, 247, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                          border: isSideway ? '1px solid rgba(168, 85, 247, 0.4)' : '1px solid rgba(59, 130, 246, 0.4)',
                          color: isSideway ? '#c084fc' : '#60a5fa'
                        }}>
                          {isSideway ? '🟪 SIDEWAY 15M' : '🔷 SWING 4H'}
                        </span>
                      </td>
                      <td style={{ padding: '6px 0' }}>
                        <span style={{
                          padding: '2px 5px',
                          borderRadius: '4px',
                          fontWeight: '700',
                          fontSize: '9px',
                          background: isLong ? 'rgba(0, 240, 144, 0.15)' : 'rgba(255, 59, 105, 0.15)',
                          color: isLong ? '#00f090' : '#ff3b69'
                        }}>
                          {pos.side} {isTp1Done ? '(50% BE)' : ''}
                        </span>
                      </td>
                      <td style={{ padding: '6px 0', fontFamily: 'monospace' }}>${pos.entry_price?.toLocaleString()}</td>
                      <td style={{ padding: '6px 0', fontFamily: 'monospace', fontWeight: '700', color: isProfit ? '#00f090' : '#ff3b69' }}>
                        {isProfit ? '+' : ''}${pnl.toFixed(2)} ({isProfit ? '+' : ''}{pnlPct.toFixed(2)}%)
                      </td>
                      <td style={{ padding: '6px 0', fontFamily: 'monospace' }}>
                        <span style={{ color: '#ff3b69' }}>
                          {slVal > 0 ? `$${slVal.toLocaleString()}` : 'N/A (OKX)'}
                        </span> / <span style={{ color: '#00f090' }}>
                          {isTp1Done ? (
                            'RUN (TP1 Done 🟢)'
                          ) : (
                            <>
                              {tpVal > 0 ? `$${tpVal.toLocaleString()}` : 'RUN'}{' '}
                              <button
                                onClick={() => editTp1Target(pos.symbol, tpVal)}
                                title="แก้ไขเป้าหมายราคา TP1"
                                style={{
                                  background: 'rgba(0, 240, 144, 0.15)',
                                  border: '1px solid rgba(0, 240, 144, 0.4)',
                                  color: '#00f090',
                                  padding: '1px 5px',
                                  borderRadius: '4px',
                                  fontSize: '9px',
                                  cursor: 'pointer',
                                  marginLeft: '4px'
                                }}
                              >
                                ✏️
                              </button>
                            </>
                          )}
                        </span>
                      </td>
                      <td style={{ padding: '6px 0' }}>
                        <button
                          onClick={() => closePosition(pos.symbol)}
                          style={{
                            background: 'rgba(255, 59, 105, 0.15)',
                            border: '1px solid rgba(255, 59, 105, 0.4)',
                            color: '#ff3b69',
                            padding: '4px 10px',
                            borderRadius: '6px',
                            fontWeight: '700',
                            fontSize: '10px',
                            cursor: 'pointer',
                            boxShadow: '0 2px 8px rgba(255, 59, 105, 0.2)'
                          }}
                        >
                          ⚡ Market Close
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} style={{ padding: '18px 0', color: '#10b981', textAlign: 'center', fontWeight: '600', background: 'rgba(16, 185, 129, 0.05)', borderRadius: '8px' }}>
                    📡 Ready & Active: Scanning OKX 15m / 4H candles for signal entries... (No active positions)
                  </td>
                </tr>
              );
            })()}
            </tbody>
          </table>

          {/* Closed Trades History Table */}
          <h2 style={{ fontWeight: '600', fontSize: '13px', marginBottom: '8px', color: '#38bdf8', paddingTop: '10px', borderTop: '1px solid rgba(255, 255, 255, 0.05)' }}>
            📜 Closed Trades History (ประวัติการปิดทำกำไรเข้าพอร์ต)
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10px' }}>
            <thead>
              <tr style={{ color: '#9ca3af', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', textAlign: 'left' }}>
                <th style={{ paddingBottom: '4px' }}>Symbol</th>
                <th style={{ paddingBottom: '4px' }}>Type</th>
                <th style={{ paddingBottom: '4px' }}>Net Profit (PnL $)</th>
                <th style={{ paddingBottom: '4px' }}>Exit Time</th>
              </tr>
            </thead>
            <tbody>
              {data?.trade_history && data.trade_history.length > 0 ? (
                data.trade_history.map((tr) => {
                  const isWin = tr.net_pnl >= 0;
                  return (
                    <tr key={tr.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.03)' }}>
                      <td style={{ padding: '4px 0', fontWeight: 'bold' }}>{tr.symbol.split('-')[0]}</td>
                      <td style={{ padding: '4px 0', color: '#38bdf8' }}>{tr.type}</td>
                      <td style={{ padding: '4px 0', fontFamily: 'monospace', fontWeight: '700', color: isWin ? '#00f090' : '#ff3b69' }}>
                        {isWin ? '+' : ''}${tr.net_pnl} USD ({isWin ? '+' : ''}{tr.pnl_pct}%)
                      </td>
                      <td style={{ padding: '4px 0', color: '#9ca3af' }}>{tr.exit_time}</td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={4} style={{ padding: '8px 0', color: '#6b7280', textAlign: 'center' }}>ยังไม่มีออเดอร์ที่ปิดทำกำไรเข้าพอร์ต</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
