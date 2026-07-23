'use client';

import React, { useRef, useEffect, useState } from 'react';

export interface CandleData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema200?: number | null;
  ema9?: number | null;
  ema21?: number | null;
  rsi?: number | null;
  adx?: number | null;
  vwap?: number | null;
  vol_sma?: number | null;
}

interface CandlestickChartProps {
  candles: CandleData[];
  symbol: string;
  resolution: string;
}

export default function CandlestickChart({ candles, symbol, resolution }: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);
  const [dimensions, setDimensions] = useState<{ width: number; height: number }>({ width: 600, height: 440 });

  // Dedicated ResizeObserver to handle container size changes cleanly without triggering size shifts on hover
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setDimensions({
            width: Math.floor(entry.contentRect.width),
            height: 440
          });
        }
      }
    });

    resizeObserver.observe(container);
    return () => resizeObserver.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !candles || candles.length === 0 || dimensions.width === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Fixed High-DPR Crisp Canvas Setup using dimensions state
    const dpr = window.devicePixelRatio || 1;
    const width = dimensions.width;
    const height = dimensions.height;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    ctx.scale(dpr, dpr);

    // Layout Dimensions
    const paddingRight = 60;
    const paddingTop = 30;
    const chartHeight = 230; // Main Candlestick Panel
    const volTop = 275;
    const volHeight = 65;    // Volume Sub-panel
    const adxTop = 355;
    const adxHeight = 65;    // ADX Sub-panel

    const chartWidth = width - paddingRight;

    // Display last N candles (e.g., 60 candles)
    const visibleCount = Math.min(60, candles.length);
    const visibleCandles = candles.slice(-visibleCount);
    const candleWidth = chartWidth / visibleCount;

    // Dynamic Y-Axis Price Auto-Scaling (Main Panel)
    const prices = visibleCandles.flatMap(c => [c.high, c.low]);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const priceRange = (maxPrice - minPrice) || 1.0;

    const getPriceY = (p: number) => {
      return paddingTop + chartHeight - ((p - minPrice) / priceRange) * chartHeight;
    };

    // Dynamic Y-Axis Volume Scaling
    const maxVol = Math.max(...visibleCandles.map(c => c.volume)) || 1.0;
    const getVolY = (v: number) => {
      return volTop + volHeight - (v / maxVol) * volHeight;
    };

    // Dynamic Y-Axis ADX Scaling (0 to 100)
    const getAdxY = (val: number) => {
      return adxTop + adxHeight - (val / 100.0) * adxHeight;
    };

    // Clear Canvas Background
    ctx.fillStyle = '#0b0e17';
    ctx.fillRect(0, 0, width, height);

    // Horizontal Grid Lines & Price Labels
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#9ca3af';
    ctx.font = '10px monospace';

    const priceSteps = 4;
    for (let i = 0; i <= priceSteps; i++) {
      const p = minPrice + (priceRange / priceSteps) * i;
      const y = getPriceY(p);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(chartWidth, y);
      ctx.stroke();

      ctx.fillText(p.toLocaleString(undefined, { minimumFractionDigits: 2 }), chartWidth + 4, y + 3);
    }

    // Sub-Panel Separator Lines & Thresholds
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.beginPath();
    ctx.moveTo(0, volTop - 8);
    ctx.lineTo(width, volTop - 8);
    ctx.moveTo(0, adxTop - 8);
    ctx.lineTo(width, adxTop - 8);
    ctx.stroke();

    // Sub-panel Labels
    ctx.fillStyle = '#9ca3af';
    ctx.fillText('Volume & Vol SMA (20)', 8, volTop - 2);
    ctx.fillText('ADX (14) Trend Strength (>20)', 8, adxTop - 2);

    // ADX Threshold Line (20 Level)
    const adx20Y = getAdxY(20);
    ctx.strokeStyle = 'rgba(239, 68, 68, 0.4)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, adx20Y);
    ctx.lineTo(chartWidth, adx20Y);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#ef4444';
    ctx.fillText('20', chartWidth + 4, adx20Y + 3);

    // Render Volume Bars
    visibleCandles.forEach((c, idx) => {
      const x = idx * candleWidth + candleWidth / 2;
      const barW = Math.max(candleWidth * 0.7, 2);
      const isGreen = c.close >= c.open;
      ctx.fillStyle = isGreen ? 'rgba(0, 240, 144, 0.3)' : 'rgba(255, 59, 105, 0.3)';

      const vY = getVolY(c.volume);
      ctx.fillRect(x - barW / 2, vY, barW, volTop + volHeight - vY);
    });

    // Render Indicators Lines (EMA 200, EMA 9, EMA 21, VWAP)
    const drawLineSeries = (key: keyof CandleData, color: string, widthPx: number = 1.5) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = widthPx;
      ctx.beginPath();
      let started = false;

      visibleCandles.forEach((c, idx) => {
        const val = c[key] as number | null | undefined;
        if (val !== null && val !== undefined && !isNaN(val)) {
          const x = idx * candleWidth + candleWidth / 2;
          const y = key === 'adx' ? getAdxY(val) : getPriceY(val);
          if (!started) {
            ctx.moveTo(x, y);
            started = true;
          } else {
            ctx.lineTo(x, y);
          }
        }
      });
      if (started) ctx.stroke();
    };

    // Draw Main Overlay Lines
    drawLineSeries('ema200', '#a855f7', 2); // Purple EMA 200
    drawLineSeries('ema9', '#3b82f6', 1.5);  // Blue EMA 9
    drawLineSeries('ema21', '#f97316', 1.5); // Orange EMA 21
    drawLineSeries('vwap', '#38bdf8', 1.5);  // Light Blue VWAP
    drawLineSeries('adx', '#ef4444', 1.5);   // Red ADX Line in Sub-panel

    // Render Candlestick Bars (OHLCV)
    visibleCandles.forEach((c, idx) => {
      const x = idx * candleWidth + candleWidth / 2;
      const openY = getPriceY(c.open);
      const closeY = getPriceY(c.close);
      const highY = getPriceY(c.high);
      const lowY = getPriceY(c.low);
      const isGreen = c.close >= c.open;
      const color = isGreen ? '#00f090' : '#ff3b69';

      // High-Low Wick Line
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(x, highY);
      ctx.lineTo(x, lowY);
      ctx.stroke();

      // Open-Close Body Rect
      const bodyTop = Math.min(openY, closeY);
      const bodyHeight = Math.max(Math.abs(closeY - openY), 2);
      const bodyW = Math.max(candleWidth * 0.65, 3);

      ctx.fillStyle = color;
      ctx.fillRect(x - bodyW / 2, bodyTop, bodyW, bodyHeight);
    });

    // Render Interactive Crosshair & Tooltip if Hovering
    if (hoverIndex !== null && hoverIndex >= 0 && hoverIndex < visibleCandles.length && mousePos) {
      const x = hoverIndex * candleWidth + candleWidth / 2;

      // Draw Vertical & Horizontal Crosshair Lines
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.moveTo(0, mousePos.y);
      ctx.lineTo(chartWidth, mousePos.y);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Chart Legend Header
    ctx.font = '700 10px monospace';
    let legendX = 8;
    const drawLegend = (text: string, color: string) => {
      ctx.fillStyle = color;
      ctx.fillText(text, legendX, 16);
      legendX += ctx.measureText(text).width + 10;
    };

    const lastCandle = visibleCandles[visibleCandles.length - 1];
    drawLegend(`${symbol} (${resolution}m)`, '#ffffff');
    if (lastCandle) {
      drawLegend(`O:${lastCandle.open}`, '#9ca3af');
      drawLegend(`H:${lastCandle.high}`, '#9ca3af');
      drawLegend(`L:${lastCandle.low}`, '#9ca3af');
      drawLegend(`C:${lastCandle.close}`, lastCandle.close >= lastCandle.open ? '#00f090' : '#ff3b69');
      drawLegend(`EMA200:${lastCandle.ema200 || '-'}`, '#a855f7');
      drawLegend(`EMA9:${lastCandle.ema9 || '-'}`, '#3b82f6');
      drawLegend(`EMA21:${lastCandle.ema21 || '-'}`, '#f97316');
      drawLegend(`VWAP:${lastCandle.vwap || '-'}`, '#38bdf8');
      drawLegend(`ADX:${lastCandle.adx || '-'}`, '#ef4444');
    }
  }, [candles, symbol, resolution, hoverIndex, mousePos, dimensions]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !candles || candles.length === 0) return;

    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const paddingRight = 60;
    const chartWidth = rect.width - paddingRight;

    const visibleCount = Math.min(60, candles.length);
    const candleWidth = chartWidth / visibleCount;
    const idx = Math.floor(x / candleWidth);

    if (idx >= 0 && idx < visibleCount) {
      setHoverIndex(idx);
      setMousePos({ x, y });
    } else {
      setHoverIndex(null);
      setMousePos(null);
    }
  };

  const handleMouseLeave = () => {
    setHoverIndex(null);
    setMousePos(null);
  };

  return (
    <div ref={containerRef} style={{
      width: '100%',
      boxSizing: 'border-box',
      background: 'rgba(11, 14, 23, 0.9)',
      backdropFilter: 'blur(12px)',
      border: '1px solid rgba(255, 255, 255, 0.08)',
      borderRadius: '16px',
      overflow: 'hidden',
      position: 'relative'
    }}>
      <canvas
        ref={canvasRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        style={{ display: 'block', cursor: 'crosshair', width: '100%' }}
      />
    </div>
  );
}
