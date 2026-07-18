# Swing Bot IDX — Frontend Dashboard

Next.js 16 dashboard untuk Swing Bot IDX API.

## Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard — Top Gainers table, signal badges, scrape button, date picker |
| `/analisis` | Form cari kode saham |
| `/saham/[kode]` | Detail analisis: ScoreCard, component bars, price chart, trade plan, capital control |

## Tech Stack

- **Framework**: Next.js 16.2.10 (App Router)
- **UI**: React 19.2.4 + Tailwind CSS 4.3.3
- **Chart**: lightweight-charts 5.2.0
- **Font**: Inter (Google Fonts)
- **Icons**: Lucide React

## Environment

| Variable | Default | Usage |
|----------|---------|-------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend URL untuk client components |

## Development

```bash
npm install
npm run dev    # → http://localhost:3000
```

Server component (`lib/api/*.ts`) pake `process.env.API_BASE_URL`, client component pake `NEXT_PUBLIC_API_BASE_URL`. Lihat `lib/api/api.ts` untuk detail fallback logic.
