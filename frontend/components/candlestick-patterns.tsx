"use client";

// ──────────────────────────────────────────────────────────────
// Candlestick Pattern Metadata
// ──────────────────────────────────────────────────────────────

interface PatternMeta {
  signal: "bullish" | "bearish" | "neutral";
  strength: 1 | 2 | 3; // 1=weak, 2=medium, 3=strong
  candles: number; // how many candles form the pattern
  description: string;
  prediction: string;
  /** SVG candle specs: each candle is {type, bodyTop%, bodyBot%, wickTop%, wickBot%} */
  svgCandles: { type: "bull" | "bear" | "doji"; bt: number; bb: number; wt: number; wb: number }[];
}

const PATTERN_DB: Record<string, PatternMeta> = {
  // ── SINGLE ──
  "Doji": {
    signal: "neutral", strength: 1, candles: 1,
    description: "Body sangat kecil, menunjukkan keraguan pasar antara buyer dan seller.",
    prediction: "Potensi reversal jika muncul setelah tren yang jelas. Konfirmasi candle berikutnya diperlukan.",
    svgCandles: [{ type: "doji", bt: 48, bb: 52, wt: 15, wb: 85 }],
  },
  "Dragonfly Doji": {
    signal: "bullish", strength: 2, candles: 1,
    description: "Doji dengan lower shadow panjang. Seller mendominasi lalu buyer mengambil alih sepenuhnya.",
    prediction: "Sinyal reversal bullish kuat saat muncul di dasar downtrend. Harga cenderung naik.",
    svgCandles: [{ type: "doji", bt: 18, bb: 22, wt: 15, wb: 90 }],
  },
  "Gravestone Doji": {
    signal: "bearish", strength: 2, candles: 1,
    description: "Doji dengan upper shadow panjang. Buyer mendominasi lalu seller mengambil alih sepenuhnya.",
    prediction: "Sinyal reversal bearish saat muncul di puncak uptrend. Harga cenderung turun.",
    svgCandles: [{ type: "doji", bt: 78, bb: 82, wt: 10, wb: 85 }],
  },
  "Long-Legged Doji": {
    signal: "neutral", strength: 2, candles: 1,
    description: "Doji dengan shadow atas dan bawah sangat panjang. Volatilitas tinggi, keraguan ekstrem.",
    prediction: "Pasar sedang bingung. Reversal mungkin terjadi, tunggu konfirmasi arah selanjutnya.",
    svgCandles: [{ type: "doji", bt: 45, bb: 55, wt: 8, wb: 92 }],
  },
  "Hammer": {
    signal: "bullish", strength: 2, candles: 1,
    description: "Body kecil di atas, lower shadow panjang minimal 2x body. Muncul di downtrend.",
    prediction: "Sinyal reversal bullish. Seller berusaha menekan tapi buyer berhasil memantulkan harga naik.",
    svgCandles: [{ type: "bull", bt: 20, bb: 35, wt: 15, wb: 90 }],
  },
  "Hanging Man": {
    signal: "bearish", strength: 2, candles: 1,
    description: "Bentuk sama seperti Hammer tapi muncul di puncak uptrend. Tanda kelemahan buyer.",
    prediction: "Sinyal peringatan bearish. Momentum beli melemah, potensi penurunan harga.",
    svgCandles: [{ type: "bear", bt: 20, bb: 35, wt: 15, wb: 90 }],
  },
  "Inverted Hammer": {
    signal: "bullish", strength: 1, candles: 1,
    description: "Body kecil di bawah, upper shadow panjang. Muncul di downtrend sebagai tanda buyer mulai masuk.",
    prediction: "Sinyal reversal bullish lemah. Perlu konfirmasi candle bullish berikutnya.",
    svgCandles: [{ type: "bull", bt: 65, bb: 80, wt: 10, wb: 85 }],
  },
  "Shooting Star": {
    signal: "bearish", strength: 2, candles: 1,
    description: "Upper shadow panjang, body kecil di bawah. Buyer gagal mempertahankan harga tinggi.",
    prediction: "Sinyal reversal bearish. Harga kemungkinan turun setelah gagal menembus resistance.",
    svgCandles: [{ type: "bear", bt: 65, bb: 80, wt: 10, wb: 85 }],
  },
  "Marubozu": {
    signal: "bullish", strength: 3, candles: 1,
    description: "Candle tanpa shadow (atau sangat kecil). Dominasi total satu pihak sepanjang sesi.",
    prediction: "Momentum sangat kuat. Jika bullish, harga cenderung lanjut naik. Jika bearish, lanjut turun.",
    svgCandles: [{ type: "bull", bt: 18, bb: 82, wt: 18, wb: 82 }],
  },
  "Belt Hold Bullish": {
    signal: "bullish", strength: 2, candles: 1,
    description: "Candle bullish besar yang open di titik terendah hari itu. Buyer langsung mendominasi.",
    prediction: "Sinyal pembalikan bullish, terutama kuat jika muncul setelah beberapa candle bearish.",
    svgCandles: [{ type: "bull", bt: 20, bb: 85, wt: 15, wb: 85 }],
  },
  "Belt Hold Bearish": {
    signal: "bearish", strength: 2, candles: 1,
    description: "Candle bearish besar yang open di titik tertinggi hari itu. Seller langsung mendominasi.",
    prediction: "Sinyal pembalikan bearish, terutama kuat jika muncul setelah beberapa candle bullish.",
    svgCandles: [{ type: "bear", bt: 15, bb: 80, wt: 15, wb: 85 }],
  },
  "Spinning Top": {
    signal: "neutral", strength: 1, candles: 1,
    description: "Body kecil dengan shadow atas dan bawah hampir sama panjang. Pasar ragu-ragu.",
    prediction: "Keraguan pasar. Jika muncul setelah tren panjang, bisa menjadi sinyal awal reversal.",
    svgCandles: [{ type: "bull", bt: 38, bb: 62, wt: 12, wb: 88 }],
  },
  // ── DOUBLE ──
  "Bullish Engulfing": {
    signal: "bullish", strength: 3, candles: 2,
    description: "Candle bullish besar sepenuhnya 'menelan' body candle bearish sebelumnya.",
    prediction: "Sinyal reversal bullish sangat kuat. Buyer mengambil alih dengan agresif. Harga cenderung rally.",
    svgCandles: [
      { type: "bear", bt: 30, bb: 55, wt: 25, wb: 60 },
      { type: "bull", bt: 20, bb: 65, wt: 15, wb: 70 },
    ],
  },
  "Bearish Engulfing": {
    signal: "bearish", strength: 3, candles: 2,
    description: "Candle bearish besar sepenuhnya 'menelan' body candle bullish sebelumnya.",
    prediction: "Sinyal reversal bearish sangat kuat. Seller mengambil alih dengan agresif. Harga cenderung jatuh.",
    svgCandles: [
      { type: "bull", bt: 40, bb: 65, wt: 35, wb: 70 },
      { type: "bear", bt: 25, bb: 75, wt: 20, wb: 80 },
    ],
  },
  "Bullish Harami": {
    signal: "bullish", strength: 2, candles: 2,
    description: "Candle bullish kecil terbentuk di dalam range body candle bearish besar sebelumnya.",
    prediction: "Sinyal potensi reversal bullish. Tekanan jual melemah, buyer mulai masuk perlahan.",
    svgCandles: [
      { type: "bear", bt: 20, bb: 70, wt: 15, wb: 75 },
      { type: "bull", bt: 35, bb: 55, wt: 30, wb: 60 },
    ],
  },
  "Bearish Harami": {
    signal: "bearish", strength: 2, candles: 2,
    description: "Candle bearish kecil terbentuk di dalam range body candle bullish besar sebelumnya.",
    prediction: "Sinyal potensi reversal bearish. Tekanan beli melemah, seller mulai masuk perlahan.",
    svgCandles: [
      { type: "bull", bt: 25, bb: 75, wt: 20, wb: 80 },
      { type: "bear", bt: 40, bb: 60, wt: 35, wb: 65 },
    ],
  },
  "Harami Cross": {
    signal: "neutral", strength: 2, candles: 2,
    description: "Doji terbentuk di dalam range body candle besar sebelumnya. Harami versi lebih kuat.",
    prediction: "Sinyal reversal lebih kuat dari Harami biasa. Keraguan total setelah candle besar menunjukkan potensi pembalikan.",
    svgCandles: [
      { type: "bear", bt: 20, bb: 70, wt: 15, wb: 75 },
      { type: "doji", bt: 44, bb: 56, wt: 30, wb: 65 },
    ],
  },
  "Piercing": {
    signal: "bullish", strength: 2, candles: 2,
    description: "Candle bullish open di bawah low sebelumnya lalu close menembus >50% body bearish.",
    prediction: "Sinyal reversal bullish. Buyer berhasil membalikkan tekanan jual signifikan dalam satu sesi.",
    svgCandles: [
      { type: "bear", bt: 20, bb: 60, wt: 15, wb: 65 },
      { type: "bull", bt: 30, bb: 75, wt: 25, wb: 80 },
    ],
  },
  "Dark Cloud Cover": {
    signal: "bearish", strength: 2, candles: 2,
    description: "Candle bearish open di atas high sebelumnya lalu close menembus >50% body bullish.",
    prediction: "Sinyal reversal bearish. Seller berhasil menekan harga turun signifikan setelah gap up.",
    svgCandles: [
      { type: "bull", bt: 35, bb: 75, wt: 30, wb: 80 },
      { type: "bear", bt: 20, bb: 55, wt: 15, wb: 60 },
    ],
  },
  "Tweezer Top": {
    signal: "bearish", strength: 2, candles: 2,
    description: "Dua candle berturutan dengan high yang hampir sama. Double rejection di resistance.",
    prediction: "Sinyal reversal bearish. Harga gagal menembus level tertinggi dua kali berturut-turut.",
    svgCandles: [
      { type: "bull", bt: 15, bb: 55, wt: 12, wb: 60 },
      { type: "bear", bt: 15, bb: 55, wt: 12, wb: 70 },
    ],
  },
  "Tweezer Bottom": {
    signal: "bullish", strength: 2, candles: 2,
    description: "Dua candle berturutan dengan low yang hampir sama. Double bounce di support.",
    prediction: "Sinyal reversal bullish. Harga berhasil bertahan di level terendah dua kali berturut-turut.",
    svgCandles: [
      { type: "bear", bt: 40, bb: 85, wt: 35, wb: 88 },
      { type: "bull", bt: 40, bb: 85, wt: 30, wb: 88 },
    ],
  },
  "On-Neck": {
    signal: "bearish", strength: 1, candles: 2,
    description: "Candle bullish kecil close tepat di low candle bearish sebelumnya. Continuation pattern.",
    prediction: "Sinyal bearish continuation. Rebound yang terjadi sangat lemah, tren turun kemungkinan berlanjut.",
    svgCandles: [
      { type: "bear", bt: 20, bb: 65, wt: 15, wb: 70 },
      { type: "bull", bt: 55, bb: 70, wt: 50, wb: 80 },
    ],
  },
  "In-Neck": {
    signal: "bearish", strength: 1, candles: 2,
    description: "Mirip On-Neck tapi close sedikit di atas low sebelumnya. Bearish continuation lemah.",
    prediction: "Tren turun kemungkinan berlanjut. Rebound gagal menembus level signifikan.",
    svgCandles: [
      { type: "bear", bt: 20, bb: 65, wt: 15, wb: 70 },
      { type: "bull", bt: 50, bb: 68, wt: 45, wb: 78 },
    ],
  },
  "Kicker Bullish": {
    signal: "bullish", strength: 3, candles: 2,
    description: "Gap up besar setelah candle bearish. Candle bullish open di atas high sebelumnya.",
    prediction: "Sinyal reversal bullish PALING kuat. Perubahan sentimen drastis, harga biasanya rally signifikan.",
    svgCandles: [
      { type: "bear", bt: 25, bb: 60, wt: 20, wb: 65 },
      { type: "bull", bt: 5, bb: 40, wt: 2, wb: 45 },
    ],
  },
  "Kicker Bearish": {
    signal: "bearish", strength: 3, candles: 2,
    description: "Gap down besar setelah candle bullish. Candle bearish open di bawah low sebelumnya.",
    prediction: "Sinyal reversal bearish PALING kuat. Perubahan sentimen drastis, harga biasanya jatuh signifikan.",
    svgCandles: [
      { type: "bull", bt: 35, bb: 70, wt: 30, wb: 75 },
      { type: "bear", bt: 55, bb: 90, wt: 50, wb: 95 },
    ],
  },
  // ── TRIPLE ──
  "Morning Star": {
    signal: "bullish", strength: 3, candles: 3,
    description: "Pola 3 candle: bearish besar → candle kecil (star) → bullish besar. Classic reversal.",
    prediction: "Sinyal reversal bullish sangat kuat. Penjualan mencapai klimaks lalu buyer mendominasi penuh.",
    svgCandles: [
      { type: "bear", bt: 15, bb: 55, wt: 10, wb: 60 },
      { type: "doji", bt: 60, bb: 70, wt: 55, wb: 80 },
      { type: "bull", bt: 15, bb: 55, wt: 10, wb: 60 },
    ],
  },
  "Evening Star": {
    signal: "bearish", strength: 3, candles: 3,
    description: "Pola 3 candle: bullish besar → candle kecil (star) → bearish besar. Classic reversal.",
    prediction: "Sinyal reversal bearish sangat kuat. Pembelian mencapai klimaks lalu seller mendominasi penuh.",
    svgCandles: [
      { type: "bull", bt: 35, bb: 75, wt: 30, wb: 80 },
      { type: "doji", bt: 20, bb: 30, wt: 12, wb: 40 },
      { type: "bear", bt: 35, bb: 75, wt: 30, wb: 80 },
    ],
  },
  "Abandoned Baby Bullish": {
    signal: "bullish", strength: 3, candles: 3,
    description: "Morning Star dengan gap penuh: shadow star tidak overlap sama sekali dengan candle 1 & 3.",
    prediction: "Sinyal reversal bullish sangat langka dan sangat kuat. Hampir selalu diikuti rally signifikan.",
    svgCandles: [
      { type: "bear", bt: 12, bb: 48, wt: 8, wb: 52 },
      { type: "doji", bt: 60, bb: 65, wt: 56, wb: 72 },
      { type: "bull", bt: 15, bb: 50, wt: 10, wb: 55 },
    ],
  },
  "Abandoned Baby Bearish": {
    signal: "bearish", strength: 3, candles: 3,
    description: "Evening Star dengan gap penuh: shadow star tidak overlap sama sekali dengan candle 1 & 3.",
    prediction: "Sinyal reversal bearish sangat langka dan sangat kuat. Hampir selalu diikuti penurunan tajam.",
    svgCandles: [
      { type: "bull", bt: 40, bb: 78, wt: 35, wb: 82 },
      { type: "doji", bt: 22, bb: 28, wt: 18, wb: 35 },
      { type: "bear", bt: 40, bb: 78, wt: 35, wb: 82 },
    ],
  },
  "Three White Soldiers": {
    signal: "bullish", strength: 3, candles: 3,
    description: "Tiga candle bullish berturutan dengan close yang progressively lebih tinggi. Body besar.",
    prediction: "Sinyal bullish continuation sangat kuat. Momentum beli masif, harga kemungkinan terus naik.",
    svgCandles: [
      { type: "bull", bt: 52, bb: 78, wt: 48, wb: 82 },
      { type: "bull", bt: 32, bb: 58, wt: 28, wb: 62 },
      { type: "bull", bt: 12, bb: 38, wt: 8, wb: 42 },
    ],
  },
  "Three Black Crows": {
    signal: "bearish", strength: 3, candles: 3,
    description: "Tiga candle bearish berturutan dengan close yang progressively lebih rendah. Body besar.",
    prediction: "Sinyal bearish continuation sangat kuat. Tekanan jual masif, harga kemungkinan terus turun.",
    svgCandles: [
      { type: "bear", bt: 15, bb: 40, wt: 10, wb: 45 },
      { type: "bear", bt: 35, bb: 60, wt: 30, wb: 65 },
      { type: "bear", bt: 55, bb: 80, wt: 50, wb: 85 },
    ],
  },
  "Three Inside Up": {
    signal: "bullish", strength: 2, candles: 3,
    description: "Bearish → Bullish Harami → konfirmasi bullish yang close di atas candle pertama.",
    prediction: "Sinyal reversal bullish yang terkonfirmasi. Lebih reliable dari Harami biasa.",
    svgCandles: [
      { type: "bear", bt: 18, bb: 68, wt: 12, wb: 72 },
      { type: "bull", bt: 32, bb: 55, wt: 28, wb: 58 },
      { type: "bull", bt: 10, bb: 42, wt: 6, wb: 46 },
    ],
  },
  "Three Inside Down": {
    signal: "bearish", strength: 2, candles: 3,
    description: "Bullish → Bearish Harami → konfirmasi bearish yang close di bawah candle pertama.",
    prediction: "Sinyal reversal bearish yang terkonfirmasi. Lebih reliable dari Harami biasa.",
    svgCandles: [
      { type: "bull", bt: 28, bb: 78, wt: 22, wb: 82 },
      { type: "bear", bt: 42, bb: 62, wt: 38, wb: 68 },
      { type: "bear", bt: 55, bb: 88, wt: 50, wb: 92 },
    ],
  },
  "Three Outside Up": {
    signal: "bullish", strength: 3, candles: 3,
    description: "Bullish Engulfing + konfirmasi bullish. Pola paling kuat untuk reversal naik.",
    prediction: "Sinyal reversal bullish sangat kuat dan terkonfirmasi. High probability follow-through naik.",
    svgCandles: [
      { type: "bear", bt: 35, bb: 55, wt: 30, wb: 60 },
      { type: "bull", bt: 25, bb: 65, wt: 20, wb: 70 },
      { type: "bull", bt: 10, bb: 40, wt: 6, wb: 44 },
    ],
  },
  "Three Outside Down": {
    signal: "bearish", strength: 3, candles: 3,
    description: "Bearish Engulfing + konfirmasi bearish. Pola paling kuat untuk reversal turun.",
    prediction: "Sinyal reversal bearish sangat kuat dan terkonfirmasi. High probability follow-through turun.",
    svgCandles: [
      { type: "bull", bt: 42, bb: 62, wt: 38, wb: 66 },
      { type: "bear", bt: 30, bb: 72, wt: 25, wb: 76 },
      { type: "bear", bt: 55, bb: 85, wt: 50, wb: 90 },
    ],
  },
  "Rising Three Methods": {
    signal: "bullish", strength: 2, candles: 3,
    description: "Candle bullish besar → beberapa candle kecil → candle bullish besar lagi menembus high awal.",
    prediction: "Sinyal bullish continuation. Koreksi kecil selesai, tren naik berlanjut dengan kekuatan penuh.",
    svgCandles: [
      { type: "bull", bt: 30, bb: 70, wt: 25, wb: 75 },
      { type: "bear", bt: 38, bb: 55, wt: 34, wb: 58 },
      { type: "bull", bt: 15, bb: 55, wt: 10, wb: 60 },
    ],
  },
  "Falling Three Methods": {
    signal: "bearish", strength: 2, candles: 3,
    description: "Candle bearish besar → beberapa candle kecil → candle bearish besar lagi menembus low awal.",
    prediction: "Sinyal bearish continuation. Rebound kecil selesai, tren turun berlanjut dengan kekuatan penuh.",
    svgCandles: [
      { type: "bear", bt: 20, bb: 60, wt: 15, wb: 65 },
      { type: "bull", bt: 35, bb: 52, wt: 32, wb: 55 },
      { type: "bear", bt: 35, bb: 75, wt: 30, wb: 80 },
    ],
  },
};

// ──────────────────────────────────────────────────────────────
// SVG Candle Renderer
// ──────────────────────────────────────────────────────────────

function CandleSVG({ candles }: { candles: PatternMeta["svgCandles"] }) {
  const count = candles.length;
  const candleWidth = 14;
  const gap = 6;
  const totalWidth = count * candleWidth + (count - 1) * gap;
  const height = 56;

  return (
    <svg width={totalWidth} height={height} viewBox={`0 0 ${totalWidth} ${height}`} className="flex-shrink-0">
      {candles.map((c, i) => {
        const x = i * (candleWidth + gap);
        const midX = x + candleWidth / 2;
        const wickTop = (c.wt / 100) * height;
        const wickBot = (c.wb / 100) * height;
        const bodyTop = (c.bt / 100) * height;
        const bodyBot = (c.bb / 100) * height;
        const bodyH = Math.max(bodyBot - bodyTop, 1);

        const fill = c.type === "bull" ? "#059669" : c.type === "bear" ? "#DC2626" : "#94a3b8";
        const wickColor = c.type === "bull" ? "#059669" : c.type === "bear" ? "#DC2626" : "#64748b";

        return (
          <g key={i}>
            {/* wick */}
            <line x1={midX} y1={wickTop} x2={midX} y2={wickBot} stroke={wickColor} strokeWidth={1.5} strokeLinecap="round" />
            {/* body */}
            {c.type === "doji" ? (
              <line x1={x + 1} y1={(bodyTop + bodyBot) / 2} x2={x + candleWidth - 1} y2={(bodyTop + bodyBot) / 2} stroke={wickColor} strokeWidth={2} strokeLinecap="round" />
            ) : (
              <rect x={x} y={bodyTop} width={candleWidth} height={bodyH} rx={1.5} fill={fill} />
            )}
          </g>
        );
      })}
    </svg>
  );
}

// ──────────────────────────────────────────────────────────────
// Strength Indicator
// ──────────────────────────────────────────────────────────────

function StrengthDots({ strength }: { strength: 1 | 2 | 3 }) {
  const labels = ["Lemah", "Sedang", "Kuat"];
  const colors = ["bg-amber-400", "bg-orange-500", "bg-red-500"];
  return (
    <div className="flex items-center gap-1.5">
      {[1, 2, 3].map((s) => (
        <div
          key={s}
          className={`w-2 h-2 rounded-full ${s <= strength ? colors[strength - 1] : "bg-slate-200"}`}
        />
      ))}
      <span className="text-[10px] font-semibold text-[var(--color-text-muted)] ml-0.5">{labels[strength - 1]}</span>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// Main Component
// ──────────────────────────────────────────────────────────────

export default function CandlestickPatterns({
  patterns,
  lastPrice,
  atr,
  realCandles,
}: {
  patterns: string[];
  lastPrice: number;
  atr: number | null;
  realCandles?: { open: number; high: number; low: number; close: number }[];
}) {
  const fmtIDR = (v: number) => Math.round(v).toLocaleString("id-ID");

  return (
    <div>
      <h4 className="text-xs font-bold text-[var(--color-text-muted)] uppercase tracking-wider mb-4">
        Pola Candlestick Terdeteksi
      </h4>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {patterns.map((patternName, i) => {
          const meta = PATTERN_DB[patternName];

          // Fallback for unknown patterns
          if (!meta) {
            return (
              <div key={i} className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)]">
                <span className="text-sm font-bold text-[var(--color-text-primary)]">{patternName}</span>
              </div>
            );
          }

          // Use real OHLC data to draw the candles if available
          let renderCandles = meta.svgCandles;
          if (realCandles && realCandles.length > 0) {
            // Get the last N candles based on pattern length
            const n = meta.candles;
            const relevantCandles = realCandles.slice(-n);
            
            if (relevantCandles.length === n) {
              const maxHigh = Math.max(...relevantCandles.map(c => c.high));
              const minLow = Math.min(...relevantCandles.map(c => c.low));
              const range = maxHigh - minLow || 1; // avoid div-by-zero

              renderCandles = relevantCandles.map(c => {
                const type = c.close > c.open ? "bull" : c.close < c.open ? "bear" : "doji";
                // mapping to 0-100% (0 is top, 100 is bottom)
                const wt = ((maxHigh - c.high) / range) * 100;
                const wb = ((maxHigh - c.low) / range) * 100;
                const topBody = Math.max(c.open, c.close);
                const botBody = Math.min(c.open, c.close);
                const bt = ((maxHigh - topBody) / range) * 100;
                const bb = ((maxHigh - botBody) / range) * 100;
                
                return { type, bt, bb, wt, wb };
              });
            }
          }

          const signalCls =
            meta.signal === "bullish"
              ? { bg: "bg-[var(--color-up-bg)]", border: "border-[var(--color-up)]/20", text: "text-[var(--color-up)]", badge: "bg-[var(--color-up-bg)] text-[var(--color-up)] border-[var(--color-up)]/20", label: "Bullish", dir: "up" as const }
              : meta.signal === "bearish"
                ? { bg: "bg-[var(--color-down-bg)]", border: "border-[var(--color-down)]/20", text: "text-[var(--color-down)]", badge: "bg-[var(--color-down-bg)] text-[var(--color-down)] border-[var(--color-down)]/20", label: "Bearish", dir: "down" as const }
                : { bg: "bg-[var(--color-warning-bg)]", border: "border-[var(--color-warning)]/20", text: "text-[var(--color-warning)]", badge: "bg-[var(--color-warning-bg)] text-[var(--color-warning)] border-[var(--color-warning)]/20", label: "Netral", dir: "neutral" as const };

          // Price projection based on ATR
          const atrVal = atr && atr > 0 ? atr : null;
          let projectionText = null;
          if (atrVal && lastPrice > 0) {
            if (meta.signal === "bullish") {
              const target = lastPrice + atrVal * meta.strength;
              projectionText = `Target naik: ~Rp ${fmtIDR(target)} (+${((atrVal * meta.strength / lastPrice) * 100).toFixed(1)}%)`;
            } else if (meta.signal === "bearish") {
              const target = lastPrice - atrVal * meta.strength;
              projectionText = `Risiko turun: ~Rp ${fmtIDR(target)} (-${((atrVal * meta.strength / lastPrice) * 100).toFixed(1)}%)`;
            }
          }

          return (
            <div key={i} className={`rounded-xl border ${signalCls.border} ${signalCls.bg} p-4 transition-all hover:shadow-md`}>
              {/* Header row */}
              <div className="flex items-start gap-3 mb-3">
                {/* SVG Illustration */}
                <div className="flex-shrink-0 p-2 rounded-lg bg-white/70 border border-white/50 shadow-sm">
                  <CandleSVG candles={renderCandles} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <h5 className="text-sm font-bold text-[var(--color-text-primary)]">{patternName}</h5>
                    <span className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-bold rounded border tabular-nums tracking-wide ${signalCls.badge}`}>
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        {signalCls.dir === "up" ? (
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 15l7-7 7 7" />
                        ) : signalCls.dir === "down" ? (
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                        ) : (
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                        )}
                      </svg>
                      {signalCls.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mb-1.5">
                    <StrengthDots strength={meta.strength} />
                    <span className="text-[10px] text-[var(--color-text-muted)]">{meta.candles} candle</span>
                  </div>
                </div>
              </div>

              {/* Description */}
              <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed mb-2">{meta.description}</p>

              {/* Prediction */}
              <div className="p-2.5 rounded-lg bg-white/50 border border-white/40 mb-2">
                <div className="flex items-start gap-1.5">
                  <svg className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-[var(--color-text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  <p className="text-[11px] font-medium text-[var(--color-text-primary)] leading-relaxed">{meta.prediction}</p>
                </div>
              </div>

              {/* Price Projection */}
              {projectionText && (
                <div className={`flex items-center gap-1.5 text-[11px] font-bold ${signalCls.text}`}>
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d={meta.signal === "bullish" ? "M5 15l7-7 7 7" : "M19 9l-7 7-7-7"} />
                  </svg>
                  {projectionText}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
