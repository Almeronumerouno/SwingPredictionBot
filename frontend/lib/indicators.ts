import type { Candle } from "@/types/api";

export interface RSIPoint {
  time: string;
  value: number;
}

export function calculateRSI(data: Candle[], period = 14): RSIPoint[] {
  if (!data || data.length <= period) return [];

  const results: RSIPoint[] = [];
  let gains = 0;
  let losses = 0;

  // First period average
  for (let i = 1; i <= period; i++) {
    const diff = data[i].close - data[i - 1].close;
    if (diff >= 0) gains += diff;
    else losses -= diff;
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;

  const firstRS = avgLoss === 0 ? 100 : avgGain / avgLoss;
  const firstRSI = 100 - 100 / (1 + firstRS);
  results.push({ time: data[period].time, value: parseFloat(firstRSI.toFixed(2)) });

  // Subsequent values using Wilder's Smoothing (RMA)
  for (let i = period + 1; i < data.length; i++) {
    const diff = data[i].close - data[i - 1].close;
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;

    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    const rsi = 100 - 100 / (1 + rs);
    results.push({ time: data[i].time, value: parseFloat(rsi.toFixed(2)) });
  }

  return results;
}

export interface MACDResult {
  macdLine: { time: string; value: number }[];
  signalLine: { time: string; value: number }[];
  histogram: { time: string; value: number; color: string }[];
}

export function calculateMACD(
  data: Candle[],
  fastPeriod = 12,
  slowPeriod = 26,
  signalPeriod = 9
): MACDResult {
  if (!data || data.length <= slowPeriod + signalPeriod) {
    return { macdLine: [], signalLine: [], histogram: [] };
  }

  // EMA helper
  const calcEMA = (prices: number[], period: number): number[] => {
    const k = 2 / (period + 1);
    const ema: number[] = new Array(prices.length);
    let initialSum = 0;
    for (let i = 0; i < period; i++) {
      initialSum += prices[i];
    }
    ema[period - 1] = initialSum / period;
    for (let i = period; i < prices.length; i++) {
      ema[i] = prices[i] * k + ema[i - 1] * (1 - k);
    }
    return ema;
  };

  const closes = data.map((d) => d.close);
  const fastEMA = calcEMA(closes, fastPeriod);
  const slowEMA = calcEMA(closes, slowPeriod);

  // MACD line = fastEMA - slowEMA
  const macdValues: { time: string; value: number }[] = [];
  for (let i = slowPeriod - 1; i < data.length; i++) {
    if (fastEMA[i] !== undefined && slowEMA[i] !== undefined) {
      macdValues.push({
        time: data[i].time,
        value: fastEMA[i] - slowEMA[i],
      });
    }
  }

  if (macdValues.length <= signalPeriod) {
    return { macdLine: [], signalLine: [], histogram: [] };
  }

  // Signal line = EMA of MACD values
  const macdRaw = macdValues.map((m) => m.value);
  const signalRaw = calcEMA(macdRaw, signalPeriod);

  const macdLine: { time: string; value: number }[] = [];
  const signalLine: { time: string; value: number }[] = [];
  const histogram: { time: string; value: number; color: string }[] = [];

  for (let i = signalPeriod - 1; i < macdValues.length; i++) {
    const time = macdValues[i].time;
    const macdVal = macdValues[i].value;
    const sigVal = signalRaw[i];
    const histVal = macdVal - sigVal;

    macdLine.push({ time, value: parseFloat(macdVal.toFixed(2)) });
    signalLine.push({ time, value: parseFloat(sigVal.toFixed(2)) });
    histogram.push({
      time,
      value: parseFloat(histVal.toFixed(2)),
      color: histVal >= 0 ? "#10B981" : "#EF4444",
    });
  }

  return { macdLine, signalLine, histogram };
}
