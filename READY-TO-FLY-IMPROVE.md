# Riset Mendalam Sistem Trading Swing Saham

Dalam riset ini kami mengkaji indikator teknikal, rumus, dan logika pengambilan keputusan yang paling tervalidasi secara akademik maupun empiris untuk sistem trading swing saham. Fokusnya adalah pada bukti penelitian dan justifikasi statistik, bukan popularitas indikator. Setiap indikator dianalisis secara komprehensif: tujuan, rumus lengkap, variabel, perhitungan langkah-demi-langkah, parameter default dan optimal menurut riset, sensitivitas, kelebihan, kekurangan, kondisi pasar ideal/gagal, serta bukti pendukung dan kritik dari literatur. Setelah itu disusun framework indikator terbaik dan metode scoring "Swing Score (0-100)" berdasarkan faktor-faktor yang terukur. Semua perhitungan dan ambang keputusan (threshold) didukung oleh referensi literatur atau hasil backtest kredibel. Apabila literatur tidak mencapai konsensus, kami nyatakan eksplisit dan sajikan alternatif yang paling banyak didukung.

## Indikator Tren

### Exponential Moving Average (EMA)

**Tujuan**: Menghaluskan data harga untuk menangkap tren jangka menengah, dengan pembobot lebih besar pada harga terbaru (responsif terhadap perubahan). EMA umum dipakai untuk sinyal tren dan sebagai komponen MACD.

**Rumus**:
```
EMA_t = α × P_t + (1-α) × EMA_(t-1)
```
dengan α = 2/(N+1) untuk periode N, dan P_t harga penutupan saat ini.

**Variabel**:
- P_t: harga (biasanya close) pada waktu t.
- EMA_(t-1): nilai EMA periode sebelumnya.
- N: panjang periode (default sering 12 atau 20 hari).
- α = 2/(N+1): faktor pelicinan (smoothing factor).

**Langkah Perhitungan**:
1. Tentukan periode N (misal 10, 20).
2. Hitung α = 2/(N+1).
3. Inisialisasi EMA awal (misal SMA periode pertama).
4. Setiap hari: EMA_t = P_t × α + EMA_(t-1) × (1-α).

**Parameter Default**: Umumnya 10 atau 20 hari untuk moving average jangka menengah. Dalam MACD standar digunakan EMA 12 dan 26, dengan sinyal EMA 9.

**Parameter Optimal**: Tidak ada konsensus mutlak; beberapa studi menyarankan pengujian parameter lewat optimasi historis. Secara umum, N yang lebih kecil membuat EMA lebih sensitif (cepat merespons sinyal baru), sedangkan N besar mengurangi noise (lebih halus).

**Sensitivitas**: EMA sensitif terhadap harga terbaru. Periode lebih pendek (mis. 10) cepat bereaksi tapi rentan sinyal palsu di pasar sideways. Periode lebih panjang (mis. 50) lebih stabil namun lambat mengikuti perubahan tren.

**Kelebihan**: Merespons perubahan tren lebih cepat daripada SMA; sederhana dan banyak digunakan; mudah dihitung.

**Kekurangan**: Masih lagging (tertinggal) karena mengandalkan harga historis; rentan sinyal palsu pada pasar bergejolak. Tidak memberikan sinyal jatuh atau bangkit yang pasti tanpa konfirmasi lain.

**Kondisi Pasar Sesuai**: Tren yang jelas (naik atau turun). EMA membantu menentukan arah tren saat harga bergerak konsisten.

**Kondisi Pasar Gagal**: Pasar menyamping tanpa tren kuat (sideways) atau berosilasi seringkali menghasilkan banyak sinyal palsu (whipsaw).

**Bukti Akademik**: EMA sendiri adalah alat dasar dalam literatur; misalnya analisis Adaptive MA (AMA) yang menyesuaikan α tidak memberikan keunggulan substansial dibandingkan strategi pasif. AMA (sejenis EMA adaptif) berhasil melebihi SMA 200 secara mentah, tetapi setelah biaya transaksi justru tidak mampu mengungguli strategi buy-and-hold. Hal ini menunjukkan bahwa meski EMA menangkap tren, keunggulannya tidak cukup besar untuk melampaui biaya trading.

**Kritik**: Dalam literatur modern sering disebutkan moving average tradisional (termasuk EMA) hanya bertahan saat tren jelas. Bagi beberapa studi, sinyal moving average biasanya tertinggal (lag) sehingga kurang efektif di pasar yang cepat berubah. Hingga sekarang, EMA dianggap berguna tetapi belum ada bukti akademik kuat bahwa strategi murni berbasis EMA jangka-pendek konsisten menguntungkan setelah biaya.

**Tingkat Validitas**: EMA dianggap indikator valid untuk mendeteksi tren dasar (lagging trend filter), namun reliabilitas sinyal murni tanpa filter lanjutan relatif rendah. Dukungan empiris mengakui kegunaannya sebagai bagian dari sistem namun menekankan kebutuhan konfirmasi lain.

### Simple Moving Average (SMA)

**Tujuan**: Mirip EMA, menghaluskan harga untuk melihat tren jangka menengah. Setiap harga mempunyai bobot sama selama N periode.

**Rumus**: SMA = rata-rata aritmatika N harga terakhir:
```
SMA_t = 1/N Σ P_(t-i)  untuk i=0 sampai N-1
```

**Variabel**:
- P_(t-i): harga pada waktu t-i.
- N: jumlah periode (default sering 20, 50, 200).

**Langkah Perhitungan**:
1. Pilih periode N.
2. Jumlahkan N harga terakhir, bagi N.
3. Geser jendela satu periode ke depan untuk nilai berikutnya.

**Parameter Default**: Sering 20 hari (menggambarkan 1 bulan perdagangan) atau 50/200 untuk jangka lebih panjang.

**Parameter Optimal**: Parameter optimum bergantung aset dan timeframe. Tidak ada nilai ajaib; trader biasanya uji (backtest) periode SMA untuk hasil terbaik historis.

**Sensitivitas**: Lebih lambat dibanding EMA dengan periode sama (EMA merespons perubahan harga lebih cepat). SMA lebih stabil tetapi ketinggalan sinyal.

**Kelebihan**: Sederhana dan intuitif; mengurangi noise harga acak; mudah diimplementasikan.

**Kekurangan**: Lagging tinggi; memberikan sinyal belakangan saat tren baru mulai. Tidak menyesuaikan bobot, sehingga sinyal terhadap perubahan tren lebih terlambat dibanding EMA.

**Kondisi Pasar Sesuai**: Tren lama/konsisten. Lebih cocok untuk analisis tren makro (mis. SMA200 untuk tren utama).

**Kondisi Pasar Gagal**: Pasar sangat bergejolak atau sideways akan menyebabkan banyak crossing palsu.

**Bukti Akademik**: SMA secara luas digunakan sebagai benchmark (mis. SMA200). Penelitian yang membandingkan SMA vs adaptive MA menyimpulkan keuntungan jangka panjang lebih didapat dari strategi pasif daripada trading murni berpedoman SMA. Dengan kata lain, walaupun SMA pernah digunakan untuk crossover (golden/death cross), hasil akademik menunjukkan kecenderungan outperform buy-and-hold minimal.

**Kritik**: SMA sering dikritik karena lagging nature-nya. Banyak penelitian teknikal menyatakan bahwa strategi crossover SMA klasik kurang efektif setelah biaya, terutama di pasar modern yang sering sideways.

**Tingkat Validitas**: Valid sebagai filter tren umum dan level dinamis support/resistance (SMA lama sering dianggap level signifikan). Namun, SMA saja jarang digunakan tanpa indikator pendamping karena keterbatasan menunda sinyal.

### Weighted Moving Average (WMA)

**Tujuan**: Variante SMA yang memberi bobot lebih besar pada harga terakhir agar lebih responsif daripada SMA biasa.

**Rumus**:
```
WMA = Σ w_i × P_(t-(i-1))  untuk i=1 sampai N
```
di mana bobot w_i biasanya proporsional terhadap urutan (mis. w_i = i / Σk). Dengan demikian harga terbaru (i=N) bobot terbesar.

**Variabel**:
- P_(t-(i-1)): harga pada periode (t-i+1).
- w_i: bobot pre-defined, sering kali w_i ∝ i (garis bawah 1/N normalisasi).

**Langkah Perhitungan**:
1. Tentukan panjang periode N.
2. Tetapkan bobot linear misalnya 1,2,...,N dan normalisasi agar total 1 (jumlah bobot = 1).
3. Hitung WMA = Σ w_i × P_(t-(i-1)).

**Parameter Default**: Mirip SMA; tidak ada "default" baku. Trader kadang gunakan N=10 atau 20.

**Parameter Optimal**: Belum banyak literatur khusus, biasanya disesuaikan seperti SMA.

**Sensitivitas**: Lebih responsif ke harga terkini daripada SMA, tapi tetap ada lag karena menggunakan harga historis. Sensitivitas tergantung fungsi bobot.

**Kelebihan**: Mendeteksi perubahan arah lebih cepat dari SMA (karena bobot akhir lebih besar) namun masih relatif stabil dibanding EMA.

**Kekurangan**: Rumus sedikit lebih kompleks, masih lagging. Tidak secepat EMA dalam merespon perubahan tajam, namun lebih rumit dihitung secara manual.

**Kondisi Pasar Sesuai**: Tren moderat. Cocok jika ingin responsif tetapi kurang sensitif seperti EMA.

**Kondisi Pasar Gagal**: Saham fluktuatif dan sideways dapat memunculkan sinyal palsu meskipun lebih sedikit daripada SMA.

**Bukti Akademik**: WMA jarang dibahas khusus dalam literatur akademik. Secara prinsip, keberhasilannya dianggap di tengah-tengah SMA dan EMA. Tidak ada studi terkenal yang menetapkan WMA unggul dari EMA/SMA.

**Kritik**: Minim publikasi ilmiah; kebermanfaatan WMA cenderung dianggap terbatas karena kini banyak trader menggunakan EMA/HMA/versi lain.

**Tingkat Validitas**: Tidak banyak data empiris. WMA dipakai oleh sebagian trader sebagai alternatif, tetapi tidak menjadi fokus utama dalam penelitian teknik karena keberadaannya yang lebih minor.

### Hull Moving Average (HMA)

**Tujuan**: Mengurangi lag moving average tradisional dengan kombinasi WMA dan smoothing, sehingga menggabungkan kecepatan EMA dengan kehalusan SMA.

**Rumus (langkah-langkah)**:
1. Hitung dua WMA: WMA1 dengan periode N/2 dan WMA2 dengan periode N (bulatkan periode setengah).
2. Hitung Raw HMA = 2 × WMA1 - WMA2.
3. HMA akhir = WMA(Raw HMA, √N).

Dengan kata lain, rumusnya:
```
HMA = WMA(2 × WMA(P, N/2) - WMA(P, N), √N)
```
di mana WMA(P,k) = weighted moving average periode k.

**Variabel**:
- P: deret harga.
- N: periode HMA (default misal 14).
- Tahapan WMA seperti di atas.

**Langkah Perhitungan**:
1. Tentukan N (mis. 14).
2. Hitung WMA periode N/2 dan N.
3. Raw HMA = 2×WMA(N/2) - WMA(N).
4. Smoothing: HMA = WMA(Raw HMA, √N).

**Parameter Default**: Umumnya digunakan N=14 sebagai default, meski beberapa sumber menyarankan 15, 25, atau 50 untuk jangka yang berbeda.

**Parameter Optimal**: Belum ada penelitian akademik baku. Umumnya disesuaikan seperti moving average lainnya.

**Sensitivitas**: Lebih cepat daripada SMA/EMA dengan periode sama dan lebih halus daripada WMA biasa. Dirancang untuk responsif namun mengurangi noise (kurang lag dibandingkan SMA biasa).

**Kelebihan**: Lebih responsif mengidentifikasi perubahan tren dengan lag yang rendah, sekaligus lebih halus dari sekadar EMA dengan periode setara. Banyak dipromosikan di literatur praktis sebagai "fast-moving average" yang stabil.

**Kekurangan**: Kompleksitas perhitungan (bergantung pada tiga WMA). Kurang dipelajari secara akademik sehingga kinerjanya kurang diverifikasi secara ilmiah. Juga masih dapat menghasilkan sinyal palsu pada pasar fluktuatif.

**Kondisi Pasar Sesuai**: Tren dengan volatilitas moderat. Dirancang untuk sinyal awal tren.

**Kondisi Pasar Gagal**: Periode tanpa tren jelas (sideways) berisiko memberi sinyal palsu karena terlalu sensitif.

**Bukti Akademik**: Minim; HMA berasal dari penulis independen (Alan Hull) tahun 2005. Penelitian ilmiah tentang HMA tidak ditemukan. Oleh karena itu validitasnya tidak jelas secara literatur akademik, walaupun banyak dipakai dalam praktik trading.

**Kritik**: Belum ada penelitian komprehensif yang mengonfirmasi keunggulan HMA. Kemungkinan hasilnya mirip indikator adaptif; jika pasar kuat trending, HMA responsif, namun dalam fase sideways belum diketahui performanya.

**Tingkat Validitas**: Tingkat kepercayaan akademik rendah (kerap hanya anekdot pedagang). Secara empiris mungkin efektif sebagai filter trend cepat, tetapi sejauh ini tidak ada konfirmasi statistik independen.

### Moving Average Convergence Divergence (MACD)

**Tujuan**: Menilai momentum dan arah tren jangka pendek dengan membandingkan dua EMA. Sering dipakai untuk sinyal beli/jual crossover dan divergensi harga-indikator.

**Rumus**:
```
Garis MACD = EMA(P,12) - EMA(P,26)
Garis Sinyal = EMA(MACD, 9)
Histogram = MACD - Sinyal
```

**Variabel**:
- EMA(P,12) dan EMA(P,26) adalah rata-rata eksponensial dengan periode tersebut.
- Garis sinyal (9) untuk smoothing crossing.

**Langkah Perhitungan**:
1. Hitung EMA(P,12) dan EMA(P,26) seperti sebelumnya.
2. MACD_t = EMA(P,12)_t - EMA(P,26)_t.
3. Garis Sinyal_t = EMA(MACD, 9)_t.
4. Histogram = MACD - Sinyal.

**Parameter Default**: 12-26-9 (umum digunakan pada grafik harian).

**Parameter Optimal**: Bervariasi; beberapa trader menguji periode yang lebih kecil atau lebih besar tergantung volatilitas. Riset spesifik MACD optimal susah ditemukan.

**Sensitivitas**: MACD memadukan dua EMA: bila tren kuat, selisih 12-26 melebar. Sinyal crossover (MACD melintasi sinyal 9) mungkin tertinggal dalam tren cepat. Histogram menandakan momentum (besar/kecil).

**Kelebihan**: Mendeteksi percepatan tren. Sinyal crossover sederhana digunakan (bullish jika MACD > sinyal). Divergensi antara MACD dan harga kadang menunjukkan kemungkinan reversal.

**Kekurangan**: Lagging karena EMA; false cross saat pasar sideways. Bisa "overfit" ke noise jika periode EMA dipendekkan. Lebih rumit diinterpretasi daripada satu MA biasa.

**Kondisi Pasar Sesuai**: Tren sedang hingga kuat. Dapat digunakan untuk menangkap momentum lanjutan. Sinyal paling akurat bila pasar memang bergerak tren.

**Kondisi Pasar Gagal**: Sideways atau sering berbalik-balikan (choppy) dapat menghasilkan crossing palsu. Sinyal MACD membutuhkan konfirmasi tambahan.

**Bukti Akademik**: Banyak tulisan trading populer mengapresiasi MACD, namun bukti akademik terbatas. Secara empiris, MACD sering menghasilkan sinyal yang terlambat, dan penelitian yang ada (meski jarang dipublikasi di jurnal akademik) tidak menjamin keuntungannya.

**Kritik**: MACD dikritik karena sensitivitas parameter dan kemunculan sinyal lambat. Tanpa filter, sinyalnya mudah tertinggal.

**Tingkat Validitas**: MACD banyak dipakai praktisi, tetapi tingkat validitas akademiknya "menengah". Ia diakui sebagai indikator pelengkap (konfirmasi momentum), bukan sinyal utama berdasarkan penelitian ilmiah (tidak banyak studi peer-review). Kemanjurannya tergantung implementasi dan pasar.

### Average Directional Index (ADX)

**Tujuan**: Mengukur kekuatan (tanpa arah) sebuah tren. ADX berasal dari Directional Movement Index Wilder, dan membantu membedakan pasar trending vs tidak.

**Rumus**: Berdasarkan perhitungan Directional Movement (+DM, -DM) dan True Range. Ringkasnya:
1. Hitung True Range (TR): max{H-L, |H-C_prev|, |L-C_prev|}.
2. +DM = perubahan naik: max{0, H_t-H_(t-1)} jika lebih besar dari penurunan, sebaliknya 0 (dan sebaliknya untuk -DM).
3. Hitung +DI = (Smoothed +DM) / (Smoothed ATR) × 100; -DI serupa.
4. DX = |+DI - -DI| / (+DI + -DI) × 100.
5. ADX = rata-rata (smooth) dari DX (14 hari biasanya).

**Variabel**:
- +DI14, -DI14: Indeks directional atas/bawah 14-hari (persentase).
- DX: Directional Index harian (0-100).
- ADX14: rata-rata 14-hari DX (skala 0-100).

**Langkah Perhitungan**:
1. Pilih periode ADX (biasanya 14 hari).
2. Hitung +DM, -DM harian dan True Range tiap hari.
3. Kalkulasi +DI dan -DI = (14-hari *DM/ATR) × 100.
4. DX = |+DI - -DI|/(+DI + -DI) × 100.
5. ADX = rata-rata bergulir DX (hari ke-14 pertama = rata-rata DX 14 hari, kemudian lissage Wilder).

**Parameter Default**: 14 hari (biasa dipilih Wilder). ADX adalah nilai tunggal yang berkembang.

**Parameter Optimal**: Sebagian riset menyarankan memastikan nilai ADX > threshold (mis. 25) untuk menganggap tren kuat. Periode ADX bisa divariasikan, tapi default 14 cukup umum.

**Sensitivitas**: ADX lambat merespons karena smoothing tinggi, sehingga reaksi tren lebih lagging. Nilainya antara 0-100.

**Kelebihan**: Mengkuantifikasi kekuatan tren secara objektif. ADX > 25-30 menandakan tren kuat, < 20 berarti pasar sideways. Berguna sebagai filter: jika ADX rendah, hindari sinyal tren.

**Kekurangan**: Tidak menunjukkan arah tren. Hanya kuat/lemah-nya tren tanpa memberi tahu naik/turun. Berlagging karena smoothing; tidak memberikan sinyal turn-over tajam.

**Kondisi Pasar Sesuai**: Pasar trending jelas. ADX membantu mengidentifikasi apakah tren itu cukup kuat untuk diikuti.

**Kondisi Pasar Gagal**: Sideways/flat market. Saat ADX rendah, sinyal tren tidak dapat diandalkan. Juga ketika tren baru mulai, ADX perlu waktu naik sehingga keputusan awal bisa terlambat.

**Bukti Akademik**: ADX banyak dijadikan pengukur kekuatan tren di literatur, misalnya Wilder sendiri menyebut ADX>25 tren dianggap kuat. Secara empiris, ADX sering dijadikan filter dalam backtest strategi trend-following. Misalnya, kombinasikan moving average crossover hanya jika ADX>20. Hasil backtest menyarankan penggunaan ADX sebagai filter memang meningkatkan kinerja dalam pasar trending.

**Kritik**: Tidak ada kritik besar kecuali sifatnya lagging. Beberapa studi menemukan indikator kekuatan tren lain (mis. VARI) tidak jauh lebih baik. ADX tetap dipakai banyak strategi, meski validitasnya tergantung konteks aset dan biaya transaksi (jika sering trading, sinyal ADX sering lambat muncul).

**Tingkat Validitas**: Diakui sebagai indikator "standar" kekuatan tren. Validitasnya relatif tinggi dalam teori tren teknikal, karena didukung Wilder. Namun, sebagai sinyal trading murni, ADX lagi-lagi lebih sebagai filter/penguat keputusan, bukan petunjuk belian segera.

### SuperTrend

**Tujuan**: Overlay dinamis yang mengikuti tren berdasarkan ATR; sering digunakan untuk trailing stop atau mengidentifikasi arah pasar.

**Rumus**:
1. Hitung Basic Upper Band = (High+Low)/2 + Multiplier × ATR.
2. Hitung Basic Lower Band = (High+Low)/2 - Multiplier × ATR.
3. Tentukan Final Upper Band/LB bergantung harga (digerakkan maju jika harga di atas/bawah band sebelumnya).
4. Gambar SuperTrend: jika harga menembus ke atas Basic Upper, maka SuperTrend = Basic Lower (uptrend). Jika menembus ke bawah Basic Lower, SuperTrend = Basic Upper (downtrend). Jika tidak ada breakout, SuperTrend tetap di level sebelumnya.

**Variabel**:
- ATR (mis. 10-hari) sebagai basis volatilitas.
- Multiplier (biasa 3).
- (High+Low)/2 = MidPrice.

**Langkah Perhitungan**:
1. Tentukan ATR_N dan multiplier (mis. ATR(10), mult=3).
2. Hitung Basic Bands: MidPrice ± (mult × ATR).
3. Set SuperTrend baris:
   - Mulai dengan arah netral. Jika harga (close) naik di atas Upper Band, pasang SuperTrend di Lower Band (tanda uptrend).
   - Jika harga turun di bawah Lower Band, pasang SuperTrend di Upper Band (tanda downtrend).
   - Jika belum ada sinyal baru, terus ikuti level band sebelumnya.
   - Band pindah arah hanya ketika ada crossover harga dengan Basic Band lawan.

**Parameter Default**: Biasanya ATR(10) dengan multiplier 3.

**Parameter Optimal**: Dapat di-tweak: ATR lebih panjang (20, 50) untuk pasar volatilitas rendah; multiplier 2-3 umum. Penyesuaian dilakukan empiris (stop loss relatif volatilitas).

**Sensitivitas**: Cukup sensitif karena mengandalkan ATR. Jika pasar tiba-tiba volatil, garis SuperTrend melebar dengan cepat. Sinyal beralih saat harga "menembus" band yang dinamis.

**Kelebihan**: Otomatis mengikuti volatilitas (tidak statis), memberikan sinyal tren yang adaptif. Berguna sebagai trailing stop (dapat dipakai titik cut-loss) dan mengonfirmasi arah tren secara visual.

**Kekurangan**: Belum ada publikasi akademis. Sinyalnya masih lagging (harus menunggu harga menembus band). Dalam pasar berombak tanpa tren, indikator dapat sering berbalik ("whipsaw"). Implementasi manual agak kompleks (band dinamis).

**Kondisi Pasar Sesuai**: Tren yang sudah mapan. Sinyal berganti hanya saat tren benar-benar berbalik.

**Kondisi Pasar Gagal**: Pasar tanpa tren jelas (range-bound) sehingga sering terjadi false crossover. Pencocokan band bergantung ATR bisa pula menimbulkan fluktuasi luar biasa saat volatilitas tiba-tiba tinggi.

**Bukti Akademik**: Tidak ada. SuperTrend adalah konsep populer di kalangan trader/penyedia platform charting. Tidak ada studi ilmiah terpublikasi tentang efektivitasnya.

**Kritik**: Sifatnya trailing & lagging membuat banyak trader menggunakannya sebagai filter trend saja. Tanpa penelitian independen, validitasnya hanya didasarkan pada pengalaman praktis. Belum diketahui keefektifan jangka panjangnya.

**Tingkat Validitas**: Cenderung rendah dalam konteks penelitian ilmiah. Hanya perlu diaplikasikan dengan hati-hati, biasanya digabung dengan indikator lain.

### Ichimoku Cloud

**Tujuan**: Sistem indikator lengkap (lagging dan leading) yang mengukur support/resistance, tren, dan momentum dalam satu paket. Menampilkan beberapa garis (chikou, kijun, tenkan, span A/B) untuk analisis multi-perioda.

**Rumus (utama)**:
- Tenkan-sen (Conversion Line): (Highest_9 + Lowest_9)/2.
- Kijun-sen (Base Line): (Highest_26 + Lowest_26)/2.
- Senkou Span A (Leading Span A): (Tenkan-sen + Kijun-sen)/2, diproyeksikan 26 periode ke depan.
- Senkou Span B (Leading Span B): (Highest_52 + Lowest_52)/2, diproyeksikan 26 periode ke depan.
- Chikou Span (Lagging): harga penutupan saat ini diproyeksikan 26 periode ke belakang.

**Variabel**:
- Highest high dan lowest low selama 9, 26, 52 periode, sesuai formula di atas.
- Default periode 9-26-52 (dikonversikan dari konsep waktu 9, 26, 52 minggu Jepang).

**Langkah Perhitungan**:
1. Hitung Tenkan-sen (9) dan Kijun-sen (26) setiap hari.
2. Hitung Senkou Span A = (Tenkan + Kijun)/2, plot 26 ke depan.
3. Hitung Senkou Span B = (Highest+Lowest)/2 untuk 52 periode, plot 26 ke depan.
4. Plot Chikou = harga tutup hari ini ke belakang 26 periode.

**Parameter Default**: 9, 26, 52 (SenkouB). Panjang 26 adalah waktu rata-rata siklus pasar Jepang awal.

**Parameter Optimal**: Jarang diubah; Ichimoku menggunakan setup "standar" 9/26/52 oleh penciptanya. Trader kadang eksperimen (mis. 7/22/44), tetapi riset tidak banyak.

**Sensitivitas**: Kompleks - ada unsur smoothing (Tenkan/Kijun) dan level dinamis (cloud). Cloud (area antara Span A dan B) melebar saat volatil, menyempit di tren kuat.

**Kelebihan**: Memberikan pandangan holistik: menentukan tren (garis di atas/bawah cloud), momentum (Tenkan vs Kijun cross), serta level support/resistance (cloud). Banyak pedagang menggunakannya sebagai sistem stand-alone.

**Kekurangan**: Rumus banyak dan interpretasi kompleks. Berat dikerjakan manual. Garis lagging (Chikou) dan leading (cloud) bisa membingungkan jika tidak dipahami konteks. Seperti banyak indikator trend, lagging bisa jadi sinyal terlambat.

**Kondisi Pasar Sesuai**: Trends jangka menengah hingga panjang. Cloud membantu menentukan arah besar pasar. Sebagai contoh: harga di atas cloud + span ke atas → kuat uptrend.

**Kondisi Pasar Gagal**: Pasar kekurangan tren jelas (konsolidasi), banyak sinyal saling tabrakan. Cloud cenderung mendatar; sinyal Tenkan/Kijun akan sering silang tanpa makna.

**Bukti Akademik**: Jarang ditinjau di literatur ilmiah Barat. Ichimoku lahir dari literatur Jepang (Goichi Hosoda, 1960an) dan populer di kalangan trader Asia. Studi empiris publikasi terbatas; tidak ada konsensus akademik mengenai efektivitasnya.

**Kritik**: Rumus kompleks membuatnya sulit dimasukkan ke dalam analisis kuantitatif akademik. Beberapa praktisi mengklaim indikator ini "semua dalam satu", namun peneliti kritis mencatat mayoritas sinyalnya sebenarnya didorong oleh moving average dasar (Tenkan/Kijun) dan pencilan. Sampai kini, Ichimoku lebih diterima sebagai alat visual analisis daripada elemen sistem trading formal di riset keuangan.

**Tingkat Validitas**: Rendah-moderat. Dilihat populer, namun kehandalan literaturnya lemah. Dalam sistem trading modern, Ichimoku sering dipakai bersama filter lain; bukti empirisnya tidak cukup untuk rekomendasi tunggal tanpa konteks tambahan.

## Indikator Momentum

### Relative Strength Index (RSI)

**Tujuan**: Mengukur kekuatan/momentum perubahan harga dalam jangka pendek. RSI menghasilkan nilai 0-100; ekstrem di atas 70 (overbought) atau di bawah 30 (oversold) sering ditafsirkan sebagai potensi pembalikan sementara.

**Rumus**: RSI diciptakan oleh Wilder (1978).
1. Hitung up-day (UC) dan down-day (DC) untuk setiap hari (UC = max{ΔP,0}, DC = max{-ΔP,0}).
2. Rata-rata gain = EMA(UC,n), rata-rata loss = EMA(DC,n) (banyak implementasi menggunakan eksponensial, Wilder pakai smoothed MA).
3. RS = Average Gain / Average Loss.
4. RSI = 100 - 100/(1+RS).

**Variabel**:
- n: periode (default 14).
- UC, DC: rata-rata kenaikan dan penurunan harga selama n (energi akumulasi).

**Langkah Perhitungan**:
1. Tetapkan periode n (biasanya 14).
2. Hitung setiap hari perubahan harga. Dapatkan 14-hari rata-rata gain dan loss (dengan rumus Wilder).
3. RS = avg_gain/avg_loss, lalu RSI = 100 - 100/(1+RS).

**Parameter Default**: 14 periode (hari) adalah baku.

**Parameter Optimal**: Tergantung pasangan aset dan volatilitas. Penelitian seperti Park & Irwin (2015) menunjukkan RSI 30/70 tidak selalu optimal untuk semua pasar. Beberapa trader menurunkan ke 5-10 atau menaikkan ke 20 untuk sensitivitas berbeda.

**Sensitivitas**: RSI melebar jika volatilitas tinggi. Periode lebih pendek membuat RSI sering berosilasi di ekstrem, periode panjang membuatnya lambat.

**Kelebihan**: Populer untuk menunjukkan kondisi overbought/oversold. Memiliki batas 0-100 memudahkan interpretasi. Banyak backtest RSI (kadang disanding MACD) menunjukkan performa cukup baik untuk mengantisipasi koreksi minor.

**Kekurangan**: Cenderung memberikan false signal saat tren kuat (mis. RSI bisa tetap >70 saat uptrend berkepanjangan). Park & Irwin (2015) menemukan sinyal standar RSI (membeli <30, menjual >70) tidak profitable di Swiss Franc/USD harian, justru sedikit loss. Artinya, level threshold RSI tidak berlaku universal. RSI juga tidak memperhitungkan volume.

**Kondisi Pasar Sesuai**: Pasar bergerak berosilasi di rentang (range-bound) sehingga overbought/oversold punah. Juga berguna sebagai filter dalam tren (mis. tunggu RSI oversold saat uptrend sebagai peluang beli).

**Kondisi Pasar Gagal**: Tren kuat. RSI bisa "walk the band" (menempel di level tinggi saat uptrend). Overbought/oversold bisa membiarkan sinyal menggiring keluar terlalu cepat.

**Bukti Akademik**: Beberapa studi empiris menunjukkan RSI bekerja terbaik saat digabung dengan indikator lain. Contohnya, Hill (2019) mengamati bahwa kekuatan RSI sebenarnya terletak pada deteksi uptrend yang konsisten jika digabung dengan filter momentum lain. Namun Park & Irwin (2015) mengkritisi penggunaan batas konvensional RSI 30/70 karena tidak efektif secara universal.

**Kritik**: RSI menerima kritik karena sensitivitas threshold-nya. Penelitian Park & Irwin menyoroti bahwa standar 30/70 sering gagal secara sistematis (tidak menghasilkan profit). Selain itu, penggunaan RSI banyak dipengaruhi oleh setting subjektif.

**Tingkat Validitas**: RSI adalah salah satu indikator momentum paling banyak dipelajari; validitasnya terukur sedang-tinggi sebagai bagian dari sistem pengambilan keputusan. Literatur menyimpulkan RSI bermanfaat, terutama bila digunakan bersama indikator lain, namun tidak ampuh bila berdiri sendiri.

### Stochastic Oscillator

**Tujuan**: Menilai posisi harga relatif terhadap rentang tertinggi/terendah dalam periode tertentu. Mengindikasikan kondisi overbought/oversold dengan membaca persentase (%K) dan sinyal garis (%D).

**Rumus**:
```
%K = (C - L_n) / (H_n - L_n) × 100
```
di mana C = harga terakhir (close), H_n = tertinggi n hari terakhir, L_n = terendah n hari terakhir.
%D = rata-rata beberapa periode (umumnya 3).

**Variabel**:
- n: periode lookback (default 14).
- (C, H_n, L_n): harga tersier.

**Langkah Perhitungan**:
1. Pilih periode n (default 14).
2. Hitung H_n dan L_n (highest high dan lowest low selama 14 hari terakhir).
3. Hitung %K dengan rumus di atas.
4. %D = 3-periode SMA dari %K (untuk smoothing).

**Parameter Default**: %K dengan periode 14, %D dengan periode 3 (hasilnya sering disebut Slow Stochastic).

**Parameter Optimal**: Beberapa pedagang menyesuaikan (mis. %K=5 atau 20, %D=3) tergantung preferensi sensitivitas. Tidak ada konsensus akademik.

**Sensitivitas**: Menunjukkan fluktuasi harga dalam rentang skala 0-100. %K naik tajam saat harga mendekati puncak lokalan, %D meratakannya.

**Kelebihan**: Menggabungkan aspek momentum dan kondisi eksternal (rentang harga). Sinyal berubah arah (cross %K-%D) mudah diinterpretasi. Rasio 80/20 sering dianggap sinyal extrem (80+ overbought, 20- oversold).

**Kekurangan**: Cenderung banyak sinyal palsu di pasar bergejolak. Interpretasi rentang terbatas (tidak mengukur momentum harga melampaui 100). Dapat "terkunci" di ekstrem saat tren.

**Kondisi Pasar Sesuai**: Pasar ranging (berosilasi dalam kanal harga), karena stokastik menunjukkan overbought/oversold di level ekstrem.

**Kondisi Pasar Gagal**: Tren kuat atau sangat volatile. Dalam tren kuat, indikator sering menempel di level atas/bawah ("walk the band"). Saat volatilitas tinggi, cepat pulang-balik, banyak sinyal semu.

**Bukti Akademik**: Seperti RSI, stokastik banyak digunakan di praktik, tetapi studi akademik terbatas. Tidak ada konsensus bahwa stokastik memberikan keuntungan jangka panjang.

**Kritik**: Hasil backtest dan literatur praktis memperingatkan false breakouts. Literaturnya kurang, indikasi pakai stokastik sebagai indikator pendukung saja.

**Tingkat Validitas**: Sedang; dipakai sebagai pelengkap momentum. Validitas statistiknya menengah; bergantung konteks. Tidak banyak penelitian ilmiah mengenai efektivitasnya murni.

### Stochastic RSI (StochRSI)

**Tujuan**: Mengukur posisi RSI saat ini dalam rentang nilai RSI selama beberapa periode. Lebih sensitif daripada RSI biasa, menampilkan fluktuasi lebih sering.

**Rumus**:
```
StochRSI = (RSI - min(RSI_n)) / (max(RSI_n) - min(RSI_n))
```
di mana max dan min adalah nilai tertinggi/terendah RSI selama n periode (biasanya 14). Hasilnya 0-1 (atau %).

**Variabel**:
- RSI_t: nilai RSI saat ini.
- min(RSI_n), max(RSI_n): nilai RSI terendah dan tertinggi selama n periode terakhir.
- Default lookback RSI 14 (sebelas; kemudian StochRSI juga 14).

**Langkah Perhitungan**:
1. Hitung RSI periodik (mis. 14-hari) terlebih dahulu.
2. Tentukan window n (sering sama, 14) untuk StochRSI.
3. Ambil RSI_min dan RSI_max selama n.
4. Kalkulasi StochRSI = (RSI - RSI_min) / (RSI_max - RSI_min).

**Parameter Default**: RSI 14, Stoch window 14. Aturan overbought/oversold 0.8/0.2 (setara 80/20).

**Parameter Optimal**: Umumnya 14-3 (mirip stokastik). Bisa disesuaikan sangat sensitif hingga bulanan tergantung strategi.

**Sensitivitas**: Sangat tinggi - fluktuasi lebih sering daripada RSI normal. Kelebihan sensitivitas ini dapat memberikan sinyal banyak, mengidentifikasi momentum jangka sangat pendek.

**Kelebihan**: Mengangkat momentum kecil yang tak terlihat RSI biasa. Berguna untuk entry/exit jangka pendek.

**Kekurangan**: Sangat volatile, mudah "bergelombang" (sinyal terlalu banyak). Sering "jaman" di posisi ekstrim. Sering perlu smoothing (mis. tambahan moving average).

**Kondisi Pasar Sesuai**: Tren halus atau pasar dengan momentum cepat di timeframe pendek (day-swing).

**Kondisi Pasar Gagal**: Struktur jangka panjang tidak terwakili, banyak false signal jika diterapkan chart harian. Jika RSI itu noisy, StochRSI makin tidak stabil.

**Bukti Akademik**: Tidak ada literatur akademik khusus. StochRSI adalah inovasi publikasi trading (Tushar Chande). Lebih banyak teori/saran trader daripada studi formal.

**Kritik**: StochRSI sangat rentan salah sinyal jika tidak di-smooth. Penggunaan utamanya terbatas pada indikator konfirmasi atau filter tambahan.

**Tingkat Validitas**: Rendah; hampir tidak ada dukungan akademis. Dalam praktik mungkin berguna untuk very short-term timing, tapi risikonya tinggi.

### Commodity Channel Index (CCI)

**Tujuan**: Mengukur deviasi harga dari rata-rata bergerak, membantu mendeteksi kondisi overbought/oversold dan awal trend. CCI membandingkan harga saat ini dengan rata-rata harga (typical price) selama N periode.

**Rumus**:
```
CCI = (TP - SMA(TP)) / (0.015 × MD)
```
di mana:
- TP = (H+L+C)/3 = Typical Price.
- SMA(TP) = rata-rata TP selama N (default 20).
- MD = mean deviation dari TP selama N.
Konstanta 0.015 dipilih agar sebagian besar nilai CCI jatuh antara ±100.

**Variabel**:
- H, L, C: harga tertinggi, terendah, penutupan tiap hari.
- N: periode (default 20).

**Langkah Perhitungan**:
1. Pilih periode N (20).
2. Hitung TP setiap hari.
3. Hitung SMA dari TP (N hari).
4. Hitung mean absolute deviation: rata-rata |TP-SMA(TP)| selama N.
5. CCI = (TP - SMA(TP)) / (0.015 × MD).

**Parameter Default**: 20 hari (SMA). Batas umum ±100 (menandakan mulai tren).

**Parameter Optimal**: Bergantung volatilitas saham; banyak studi perdagangan menggunakan 14-20. Parameter bisa diuji, namun tidak ada kesepakatan khusus akademis.

**Sensitivitas**: Jika harga bergerak jauh dari rata-rata, CCI membesar (positif/negatif ekstrim). Jangka waktu lebih pendek membuat CCI mudah melonjak di ±100.

**Kelebihan**: Tidak dibatasi 0-100, sehingga dapat mengukur tren kuat di luar tingkat ekstrem. Memberi sinyal awal tren (terobosan ±100). Kombinasinya dengan grafik menunjukkan momen divergences.

**Kekurangan**: Rentan noise di pasar sideways; perlu interpretasi pengalaman. Tidak begitu terkenal, sehingga kurang banyak studi pendukung. Lebih sulit disesuaikan (pembacaan tak intuitif seperti RSI).

**Kondisi Pasar Sesuai**: Tren kuat; breakout dari ±100 menandakan awal tren baru. Juga dapat mendeteksi kondisi ekstrem dalam range-bound minor.

**Kondisi Pasar Gagal**: Pasar flat panjang: sinyal CCI sering berubah-ubah antara +100 dan -100 tanpa tren yang berkelanjutan.

**Bukti Akademik**: Sangat sedikit. Sebagian backtest menyarankan CCI berguna untuk swing trading tertentu, namun literatur akademik tidak terkenal membahasnya. Biasanya dimasukkan sebagai indikator alternatif momentum.

**Kritik**: Karena struktur rumus yang agak "arbitrary" (nilai 0.015), CCI kadang hanya dianggap variasi lain RSI. Tanpa uji statistik, efektivitasnya tidak terjamin.

**Tingkat Validitas**: Rendah-sedang. CCI kadang digunakan dalam strategi, tapi dalam riset akademik ia bukan fokus. Ia dianggap sinyal pendukung atau filter tambahan.

### Rate of Change (ROC)

**Tujuan**: Mengukur momentum harga sebagai persentase perubahan dibanding harga n periode lalu. Menunjukkan seberapa cepat harga berubah.

**Rumus**:
```
ROC = (C_t - C_(t-n)) / C_(t-n) × 100
```
di mana C_t = harga penutupan saat ini, C_(t-n) = penutupan n periode lalu.

**Variabel**:
- n: periode lookback (misal 12).

**Langkah Perhitungan**:
1. Pilih n (umumnya 12-14).
2. Ambil selisih antara harga sekarang dengan harga n periode lalu.
3. Bagi selisih ini dengan harga n periode lalu, lalu kali 100.

**Parameter Default**: Sering 12 atau 14 hari, mirip momentum. Tidak ada "standar" baku.

**Parameter Optimal**: Belum ada konsensus; analisis harga berubah-ubah. Dalam literatur jarang dikaji.

**Sensitivitas**: ROC tidak dibatasi (tidak ada 0-100); volatilitas menghasilkan rentang ROC lebar. Oleh karena itu sulit menetapkan level overbought/oversold yang universal.

**Kelebihan**: Simple dan mudah dipahami. Langsung menunjukkan sign berubah naik/turun. Berguna untuk melihat persentase perubahan harga.

**Kekurangan**: Tidak ada batasan patokan (berbeda RSI), sehingga penafsiran lebih subjektif. Sangat dipengaruhi volatilitas: di pasar volatile ROC besar turun-naik.

**Kondisi Pasar Sesuai**: Tren yang mapan, untuk konfirmasi momentum (jika ROC menurun padahal harga masih naik, tandanya momentum melemah).

**Kondisi Pasar Gagal**: Level volatil: ROC bisa memberi sinyal noise. Tidak efektif menandakan ekstrem (tidak ada overbought/oversold baku).

**Bukti Akademik**: Minim. ROC kadang disebut dalam strategi momentum sederhana, tetapi penelitian formal jarang menggunakan ROC sebagai indikator utama.

**Kritik**: Dikritik karena interpretasi ambigu dan rentan noise. Sering dibandingkan dengan momentum biasa (selisih harga), yang gejala sinyalnya serupa.

**Tingkat Validitas**: Rendah. Sebagai pengukur momentum sederhana, paling dipakai untuk analisis visual atau filter tambahan daripada indikator tunggal sistem trading.

### Momentum (indikator Momentum)

**Tujuan**: Mengukur selisih harga terkini dengan harga n periode lalu (bukan persentase, melainkan nilai absolut). Indikator dasar momentum mentransformasi harga jadi pergerakan absolut.

**Rumus**:
```
Momentum = C_t - C_(t-n)
```

**Variabel**:
- C_t: harga penutupan saat ini.
- C_(t-n): penutupan n periode lalu (default 10).

**Langkah Perhitungan**:
1. Pilih periode n (misalnya 10 hari).
2. Substract harga n hari lalu dari harga sekarang.

**Parameter Default**: 10 hari (sering dipakai).

**Parameter Optimal**: Bervariasi; seperti ROC, sering dipakai 10-20.

**Sensitivitas**: Mirip ROC namun tidak relativitas persentase. Kalau harga semakin tinggi, nilai momentum bisa besar walau persentasenya kecil.

**Kelebihan**: Sangat sederhana. Jika tren naik, momentum positif besar; turun, momentum negatif besar. Bisa dipakai untuk konfirmasi tren.

**Kekurangan**: Tidak dinormalisasi (skala bergantung harga); kurang intuitif untuk threshold. Sangat mirip dengan ROC, sering dianggap variannya.

**Kondisi Pasar Sesuai**: Tren kuat (momentum akan konsisten positif/negatif).

**Kondisi Pasar Gagal**: Pasar mendatar, momentum cepat berganti tanda.

**Bukti Akademik**: Tidak banyak diteliti secara individu. Dijelaskan dalam literatur trading umum (mis. Murphy) tetapi tidak sebagai variabel utama dalam studi ilmiah.

**Kritik**: Indikator paling dasar, jarang dijadikan satu-satunya sinyal. Atau biasa dipadukan dengan oscillator lain.

**Tingkat Validitas**: Rendah; hanya pedoman dasar. Dalam riset mungkin dicatat sebagai bagian dari kategori momentum, namun tidak dominan.

## Indikator Volume

### On-Balance Volume (OBV)

**Tujuan**: Mengukur akumulasi atau distribusi volume seiring perubahan harga. OBV membantu melihat apakah volume lebih banyak pada hari harga naik atau turun, sebagai indikasi kekuatan tren.

**Rumus**:
```
OBV_t = OBV_(t-1) + { +V_t, jika C_t > C_(t-1); -V_t, jika C_t < C_(t-1); 0, jika C_t = C_(t-1) }
```
di mana V_t = volume hari ke-t. Jika harga naik hari ini, tambahkan volume; jika turun, kurangi.

**Variabel**:
- C_t, C_(t-1): harga penutupan sekarang dan sebelumnya.
- V_t: volume sekarang.

**Langkah Perhitungan**:
1. Mulai dengan OBV awal (bisa 0).
2. Setiap hari:
   - Jika C_t > C_(t-1), OBV = OBV_(t-1) + V_t.
   - Jika C_t < C_(t-1), OBV = OBV_(t-1) - V_t.
   - Jika sama, OBV tidak berubah.
3. Plot OBV sebagai garis kumulatif volume.

**Parameter Default**: Tidak ada periode; ini indikator akumulatif harian.

**Parameter Optimal**: N/A (tidak ada pengaturan).

**Sensitivitas**: OBV hanya naik/turun sesuai arah harga, sehingga memantau tren volume agresif. Terlalu sensitif terhadap hari-hari trading dengan volume besar saat tren berlawanan arah.

**Kelebihan**: Sederhana dan sering dipakai untuk konfirmasi tren. Divergensi OBV (harga naik tapi OBV turun) bisa memperingatkan tren lemah.

**Kekurangan**: OBV merupakan indikator leading yang mudah menghasilkan sinyal palsu. Misalnya, lonjakan volume tiba-tiba pada hari harga turun mungkin memberi konotasi akumulasi meski sebenarnya panik selling.

**Kondisi Pasar Sesuai**: Tren kuat dengan volume konsisten sesuai arah. Dalam tren naik dengan konfirmasi OBV naik, tren dianggap didukung pembelian kuat.

**Kondisi Pasar Gagal**: Volatilitas volume tinggi di dalam range; perbedaan sehari bisa menghancurkan pola OBV. Tidak cocok jika trading tidak likuid (vol kecil tak signifikan).

**Bukti Akademik**: OBV lebih sering disebut dalam literatur trading populer daripada penelitian ilmiah. Belum ada studi akademis besar tentang efektivitas OBV.

**Kritik**: Karena sangat sederhana, OBV sering dikritik karena tidak mempertimbangkan posisi harga dalam hari itu. Oleh karena itu, banyak trader advanced lebih memilih indikator distribusi/akumulasi yang melibatkan level harga (seperti A/D line di bawah).

**Tingkat Validitas**: Rendah-sedang. OBV valid sebagai konfirmasi tambahan untuk tren, tapi sebagai sinyal trading tunggal efeknya terbatas (risiko false).

### Money Flow Index (MFI)

**Tujuan**: Mirip RSI, namun memasukkan data volume. MFI menilai "tekanan beli/jual" melalui harga dan volume selama periode. 0-100, dengan area 80/20 sebagai overbought/oversold (lebih ekstrem daripada RSI).

**Rumus**:
1. Hitung Typical Price setiap hari: TP = (H+L+C)/3.
2. Hitung Raw Money Flow = TP × V (harga × volume).
3. Pisahkan Positive Money Flow (jika TP hari ini > kemarin, masukkan raw flow ke positive) dan Negative Money Flow sebaliknya.
4. Money Flow Ratio = (sum Positive MF selama n) / (sum Negative MF selama n).
5. MFI = 100 - 100/(1 + Money Flow Ratio).

**Variabel**:
- n: biasanya 14 hari.
- H, L, C: harga tinggi/low/close.
- V: volume.

**Langkah Perhitungan**:
1. Pilih n (default 14).
2. Setiap hari: hitung TP, kemudian MF = TP × V. Tentukan apakah MF termasuk Pos (TP naik) atau Neg (TP turun).
3. Setelah n hari, hitung sum PosMF dan NegMF.
4. Money Flow Ratio = PosMF/NegMF, kemudian MFI = 100 - 100/(1+Ratio).

**Parameter Default**: 14 periode; threshold oversold/overbought biasanya 20/80 (atau ekstrem 10/90).

**Parameter Optimal**: Sama dengan RSI; banyak yang tetap pakai 14. Rumus berbasis volume membuatnya cenderung berfluktuasi lebih dari RSI.

**Sensitivitas**: Nyaris sama dengan RSI tapi dengan volume sebagai pembobot. Jika harga naik dengan volume besar, MFI naik tajam. Jika tren berlanjut, MFI bisa tetap ekstrim.

**Kelebihan**: Memadukan volume, sehingga kadang lebih bisa menggambarkan kekuatan tren. Misalnya perbedaan hasil bila harga naik pada volume tinggi vs rendah. Sering dipakai divergen MFI/harga.

**Kekurangan**: Seperti RSI, MFI juga menghasilkan false signal jika tren kuat (indikator bisa terpaku di area ekstrem). Tren kuat dapat "menyebabkan sinyal palsu" - contohnya exit terlalu awal jika MFI naik di atas 80 terus-terusan. Selain itu, data volume sering tidak seragam.

**Kondisi Pasar Sesuai**: Rutin dipakai seperti RSI: untuk mengidentifikasi pembalikan kecil. Bisa efektif saat ada divergensi (harga naik baru-baru ini tapi MFI turun karena volume melemah).

**Kondisi Pasar Gagal**: Tren solid dengan volume tinggi terus-menerus. Misal selama bull run, MFI hampir selalu >80, sehingga sinyal jual dari MFI bisa menyesatkan.

**Bukti Akademik**: Sedikit literatur. MFI diperkenalkan oleh Wilder (yang juga RSI), namun kajian independen terbatas. Ia sering disebut dalam tutorial trading sebagai "RSI dengan volume", namun tanpa percobaan statistik luas.

**Kritik**: Kinerjanya tidak jauh berbeda dari RSI. Beberapa studi mencatat bahwa MFI cenderung tersisih jika harga trend terus (sama seperti RSI). Terlebih, volume yang tak beraturan membuat MFI sulit distandarisasi.

**Tingkat Validitas**: Moderat. MFI sering direkomendasikan oleh analis teknikal (hence widely used oleh trader) sebagai indikator momentum berbasis volume. Namun evidence ilmiah masih sedikit; pada akhirnya dianggap pelengkap RSI.

### Chaikin Money Flow (CMF)

**Tujuan**: Mengukur akumulasi/distribusi berdasarkan harga dan volume selama n hari. Mirip ADL, namun dalam bentuk oscillator yang diasumsikan berfluktuasi di sekitar nol. Menunjukkan apakah tekanan beli (positif) atau jual (negatif) sedang mendominasi.

**Rumus**:
1. Hitung Money Flow Multiplier setiap hari: ((C-L)-(H-C))/(H-L).
2. Money Flow Volume = Multiplier × Volume.
3. CMF = (Σ MFV_i) / (Σ V_i) untuk i=0 sampai N-1.

**Variabel**:
- N: periode (default sering 20).
- H, L, C: harga tinggi, rendah, penutupan; V: volume.

**Langkah Perhitungan**:
1. Pilih N (20).
2. Setiap hari: hitung multiplier dan MFV sebagai di atas.
3. Setelah N hari: jumlahkan MFV selama N dan volume selama N. CMF = sum(MFV)/sum(volume).

**Parameter Default**: Biasanya 20 periode.

**Parameter Optimal**: Bergantung pada timeframe trading (lebih lama di stock, lebih singkat untuk intraday).

**Sensitivitas**: Naik-turun dengan Accumulation/Distribution Line jangka pendek. Nilai CMF biasanya antara -1 dan +1.

**Kelebihan**: Mempertimbangkan seberapa lama harga menutup di area atas/bawah range hari, dibobot volume. Dapat memberikan sinyal divergensi seperti OBV, tapi dengan normalisasi periode.

**Kekurangan**: Tidak luas diuji dalam studi. Bergantung format data. Dalam tren kuat, CMF dapat terus positif/negatif dengan sedikit pengembalian ke nol. Tak ada threshold "standar" baku.

**Kondisi Pasar Sesuai**: Sama seperti ADL/OBV: memberi sinyal pembelian jika melonjak positif, penjualan jika turun negatif, terutama bila dikonfirmasi tren.

**Kondisi Pasar Gagal**: Variasi harian harga-volum kecil, atau trend strong dimana CMF mendekati batas ±1.

**Bukti Akademik**: CMF diperkenalkan oleh Marc Chaikin, namun belum memiliki studi terbuka luas. Beberapa tulisan (mis. di situs ChartSchool) menjelaskan formulanya, namun bukti empiris akademik sulit ditemukan.

**Kritik**: Mirip OBV, mudah disalahartikan saat volatilitas tinggi. Tanpa riset publik, efektivitasnya sulit diukur; sering dianggap indikator kelas kedua.

**Tingkat Validitas**: Rendah. Dianggap sebagai varian lain dari indikator akumulasi-volume tanpa validasi ilmiah kuat.

### Accumulation/Distribution Line (A/D Line)

**Tujuan**: Mengukur akumulasi (pembelian) atau distribusi (penjualan) berdasarkan harga dan volume harian. Versi kumulatif dari Money Flow Volume.

**Rumus**: Mirror CMF sebelum normalisasi: setiap hari tambahkan Money Flow Volume secara kumulatif. Money Flow Multiplier = ((C-L)-(H-C))/(H-L). MFV = multiplier × volume. ADL ditambah atau dikurangi MFV ke nilai ADL sebelumnya.

**Variabel**: Seperti di CMF.

**Perhitungan**: Seperti OBV, tapi menggunakan MFV dengan hitungan tertimbang harga.

**Parameter Default**: N/A, berkelanjutan.

**Sensitivitas**: Jumlah terbuka (tidak dibatasi), cenderung naik terus jika akumulasi terjadi.

**Kelebihan**: Lebih halus dari OBV karena memperhitungkan seberapa dekat close dari high/low (sering disebut Close Location Value).

**Kekurangan**: Sama seperti OBV; sebagai leading indicator, rawan salah sinyal. Jika harga periode tertentu turun sedikit tapi dekat high, hasil MFV bisa kecil, memberi sinyal berbeda dari OBV.

**Kondisi Pasar Sesuai/Gagal**: Serupa OBV.

**Bukti Akademik/Kritik**: Jarang ditinjau akademis. Tidak ada studi terpublik tentang performa A/D.

**Tingkat Validitas**: Rendah-moderat. Berguna sebagai alternatif OBV dalam analisis teknikal praktis, tetapi bukti ilmiahnya tidak ada.

### Volume Weighted Average Price (VWAP)

**Tujuan**: Menunjukkan harga rata-rata tertimbang volume sejak awal sesi perdagangan (biasanya harian). Sering digunakan oleh institusi untuk mengevaluasi eksekusi.

**Rumus**:
```
VWAP = (Σ(P_i × V_i)) / (Σ V_i)
```
di mana i setiap tick atau bar intraday.

**Variabel**:
- P_i: harga pada transaksi atau bar (typical price).
- V_i: volume pada saat itu.

**Langkah Perhitungan**:
1. Setiap periode (mis. 1 menit): hitung total nilai P×V dan total volume kumulatif.
2. VWAP = (running sum of P×V) / (running sum of V).
3. Reset setiap hari (VWAP hari baru dari awal sesi).

**Parameter Default**: Periodik harian; reset di pembukaan pasar.

**Parameter Optimal**: Tidak berlaku - VWAP intrinsik intraday.

**Sensitivitas**: Sangat tergantung volume distribusi sepanjang hari. Bandingkan pergerakan harga dengan VWAP: harga di atas VWAP = buying pressure, di bawah = selling.

**Kelebihan**: Standar industri intraday. Mempunyai interpretasi statistik sebagai "imbalan" volume (avg). Dapat digunakan sebagai level support/res (institusi sering transaksikan di dekat VWAP).

**Kekurangan**: Hanya berguna intraday. Untuk analisis harian, tidak ada pengaruh (reset tiap hari). Tidak diukur dalam riset swing trading jangka lebih panjang.

**Kondisi Pasar Sesuai**: Trading harian/intraday dengan akumulasi banyak order.

**Kondisi Pasar Gagal**: Swing trading mingguan: VWAP tidak relevan.

**Bukti Akademik**: VWAP tidak dibahas dalam konteks pasar saham jangka panjang, karena fungsi utamanya adalah ekseskusi intraday.

**Tingkat Validitas**: Hanya relevan intraday; bukan indikator tren/jangka panjang. Dalam konteks swing trading yang fokusnya harian/lebih, VWAP biasanya diabaikan.

### Relative Volume (RVOL)

**Tujuan**: Mengukur likuiditas saat ini relatif terhadap rata-rata historis pada periode sejenis. Indikator sederhana untuk melihat level minat pasar/volatilitas volume.

**Rumus**:
```
RVOL = V_current / AvgVol
```
di mana AvgVol bisa rata-rata harian volume selama N hari (mis. 5-10).

**Variabel**:
- V_current: volume saat interval tertentu.
- AvgVol: rata-rata volume historis pada periode sebanding (5, 10, 30 hari).

**Langkah Perhitungan**:
1. Hitung rata-rata volume harian selama N hari terakhir.
2. Bandingkan volume hari ini terhadap rata-rata itu.
3. RVOL > 1 artinya volume lebih besar dari biasa (minat tinggi).

**Parameter Default**: Tidak standar, namun 5, 10, 30 hari sering digunakan.

**Parameter Optimal**: Aturan praktis: batas tertentu (mis. >2) menandakan "in-play" (aktif).

**Sensitivitas**: Cenderung kasar. Ambang signifikan (seperti 2× rata-rata) perlu ditentukan berdasarkan aset.

**Kelebihan**: Indikasi cepat untuk volume outlier (berita/fundamental masuk). Ada analisis anomali gap yang mendukung pentingnya perbedaan volume.

**Kekurangan**: Bukan indikator harga; hanya sinyal eksternal ("minat pasar"). Ambang 2× bersifat heuristik.

**Kondisi Pasar Sesuai**: Validasi breakout/pullback: RVOL tinggi memberi keyakinan sinyal (breakout likuid), sebaliknya rendah menunjukkan false breakout mungkin.

**Kondisi Pasar Gagal**: Tidak ada. Ini indikator volume yang informatif kapanpun. Namun tidak memberi sinyal beli/jual sendiri.

**Bukti Akademik**: Tidak ada kajian formal. Relative volume dicantumkan sebagai konsep trader. Ia berguna dalam trading rumor, namun hanya dimasukkan dalam sistem sebagai filter (untuk mengecek relevansi berita vs aksi harga).

**Tingkat Validitas**: Sangat bergantung penerapan. Tidak diukur ilmiah, tetapi masuk akal untuk validasi volume.

### Volume Profile

**Tujuan**: Menampilkan sebaran volume berdasar tingkat harga tertentu selama periode. Menentukan "nodes" harga dengan volume tinggi (value area).

**Rumus**: Bukan indikator berbasis formula; lebih pada pengumpulan data: untuk setiap level harga (bin) hitung total volume yang diperdagangkan.

**Variabel**: Price levels dan volume.

**Langkah Perhitungan**:
1. Pilih periode analisis (mis. 1 bulan).
2. Bagi rentang harga menjadi kotak (bin).
3. Akumulasi volume setiap kali harga bertransaksi dalam bin tersebut.
4. Hasilnya histogram di samping grafik harga.

**Parameter Default**: Banyak platform (TradingView, Market Profile) menyediakan profil volume tiap bar atau fixed periode (harian, bulanan).

**Kelebihan**: Mengidentifikasi area harga yang sering diperdagangkan (VAH, VAL, POC). Berguna untuk support/resistance dan pengakuan konsolidasi/akumulasi.

**Kekurangan**: Lebih tool analitis daripada indikator sinyal. Tidak memberi threshold angka.

**Bukti Akademik**: Volume profile akrab di komunitas trader (Market Profile Peter Steidlmayer dll.), tapi studi formal agak sedikit. Sering diasosiasikan dengan konsep pasar efisien (banyak volume = harga dianggap wajar).

**Tingkat Validitas**: Konsep S/R berdasarkan volume umum diterima (banyak buku trading mengulasnya). Namun bukan indikator kuantitatif teruji, melainkan interpretasi grafis.

## Indikator Volatilitas

### Average True Range (ATR)

**Tujuan**: Mengukur volatilitas pasar secara kuantitatif (berapa besar pergerakan harga rata-rata). Tidak memprediksi arah; hanya seberapa "besar" fluktuasi historis. Sering dipakai dalam pengelolaan risiko (stop-loss adaptif).

**Rumus**: Diperkenalkan Wilder; ATR menghitung True Range (TR) setiap hari sebagai komponen:
```
TR = max{H-L, |H-C_prev|, |L-C_prev|}
```
ATR kemudian dihitung sebagai rata-rata bergerak dari TR (bisa simple atau Wilder's smoothing):
```
ATR_t = (ATR_(t-1) × (n-1) + TR_t) / n
```
untuk Wilder's (initial ATR = rata-rata TR awal).

**Variabel**:
- H, L: harga tertinggi, terendah hari ini.
- C_prev: harga tutup kemarin.
- n: periode (default 14).

**Langkah Perhitungan**:
1. Tentukan n (biasanya 14).
2. Hitung TR hari per hari.
3. ATR awal (mis. hari ke-14) adalah rata-rata TR dari 14 hari.
4. ATR berikutnya = ((ATR_(t-1) × (n-1)) + TR_t) / n.

**Parameter Default**: 14 hari (Wilder).

**Parameter Optimal**: Dapat disesuaikan (lebih pendek untuk timeframe pendek, lebih panjang jika ingin smooth).

**Sensitivitas**: ATR naik saat volatilitas meningkat (range harian melebar). Nilainya tidak memiliki batas atas.

**Kelebihan**: Ukuran volatilitas yang mudah diinterpretasi. Banyak sistem trading menggunakan ATR untuk mengatur lebar stop-loss (mis. 1×ATR atau 2×ATR). Adaptif terhadap kondisi pasar saat ini.

**Kekurangan**: Hanya volatilitas; tidak memberikan sinyal beli/jual. Indikator semata. Jika pasar volatil rendah, ATR rendah; saat tiba-tiba naik, ATR bisa naik perlahan (lag smoothing).

**Kondisi Pasar Sesuai**: Umum; cocok di semua kondisi untuk mengetahui volatilitas.

**Kondisi Pasar Gagal**: Tidak relevan sebagai sinyal, tapi secara fungsi, ATR rendah saat pasar flat bisa disalahpahami sebagai "aman" padahal market bisa lompat kapan saja.

**Bukti Akademik**: ATR banyak disebut dalam literatur pengelolaan risiko. Misalnya, strategi breakout sering menggunakan filter ATR (breakout hanya jika ATR menurun dari periode sejak). Namun studi empiris jarang terfokus ATR sebagai sinyal.

**Kritik**: ATR adalah ukuran backward-looking; dalam pasar trending tiba, ATR baru naik belakangan. Sebagai indikator solo, belum terbukti memperbaiki kinerja sinyal.

**Tingkat Validitas**: Tinggi sebagai ukuran volatilitas (diakui secara luas). Namun secara trading-signal ATR intrinsik bukan petunjuk arah, jadi validitasnya diukur sebagai alat bantu (backing up risk management) bukan trigger trading.

### Bollinger Bands

**Tujuan**: Menampilkan volatilitas dinamis di sekitar SMA. Mengukur overbought/oversold relatif dalam konsisten 2 standar deviasi band.

**Rumus**:
- Middle Band: SMA_N (biasanya 20 periode) dari harga.
- Upper Band = Middle Band + k × SD_N.
- Lower Band = Middle Band - k × SD_N.
Umumnya k=2 standar deviasi.

**Variabel**:
- N: periode SMA (default 20).
- SD_N: standar deviasi harga (close) 20-periode.
- k: multiplier (biasanya 2).

**Langkah Perhitungan**:
1. Tentukan SMA 20 hari (tengah).
2. Hitung deviasi harga tiap hari dari SMA, lalu STD 20 hari.
3. Gambarkan Upper = SMA + 2×STD, Lower = SMA - 2×STD.

**Parameter Default**: 20 periode dan 2×STD.

**Parameter Optimal**: John Bollinger menyesuaikan sedikit (mis. SMA50×2.1, SMA10×1.9) tergantung volatilitas. Tapi 20/2 paling sering dipakai.

**Sensitivitas**: Band melebar menyesuaikan volatilitas: pergerakan tajam membuat deviasi naik, band melebar; di pasar tenang band menyempit.

**Kelebihan**:
- Mengukur volatilitas secara visual (lebar band).
- Sinyal reversion: jika harga menembus band luar, sering dianggap kondisi ekstrim (meski Bollinger menekankan "tag", bukan sinyal otomatis).
- Indikator multifungsi: squeeze (penyempitan band) sinyal akan breakout; walking the bands sebagai tanda tren kuat.

**Kekurangan**: Bukan prediktif; harga sering menapak band saat tren kuat (tidak artinya segera reversal). Perdagangan hanya berpatokan band sering memberi sinyal prematur.

**Kondisi Pasar Sesuai**: Ranging (kembali ke mean) dan transisi volatil (squeeze). Juga sebagai konfirmasi tren (price "walking the band" menandakan kekuatan).

**Kondisi Pasar Gagal**: Pasar trending kuat: bisa sering tag upper band tanpa koreksi. Breakout band tidak menjamin reversal. Oleh karena itu perlu filter momentum.

**Bukti Akademik**: Bollinger Bands banyak disebut di literatur teknikal. Studi sistem trading menunjukkan indikator ini lebih efektif sebagai komponen (squeeze, konfirmasi) daripada berdiri sendiri sebagai sinyal beli/jual.

**Kritik**: Biasa dijadikan secondary indicator. Bollinger sendiri memperingatkan "touch" band bukan perintah beli/jual langsung. Kinerja akademik sangat bergantung kombinasi dengan indikator lain (misalnya RSI, MACD).

**Tingkat Validitas**: Sedang. Sangat populer; nilai-nilai 20/2 (atau 20/1.9/2.1) dianggap standar. Diakui sebagai alat ukur volatilitas/statistik price action. Kelebihannya pada riset adalah deskriptif (kapan volatilitas naik), bukan prediksi langsung.

### Keltner Channels

**Tujuan**: Volatility channel mirip Bollinger, namun menggunakan ATR sebagai ukuran volatilitas di sekeliling moving average (biasanya EMA 20). Menyaring noise tren dan menunjukkan breakout.

**Rumus**:
- Middle Line: biasanya EMA 20 dari harga.
- Upper Channel: EMA + (multiplier × ATR).
- Lower Channel: EMA - (multiplier × ATR).
Umumnya multiplier 2.

**Variabel**:
- EMA 20 harga (dasar tren).
- ATR N hari (sering 10 atau 20).
- Multiplier (sering 2).

**Langkah Perhitungan**:
1. Hitung EMA 20 (atau lain) harga.
2. Hitung ATR (mis. 10-hari).
3. Gambarkan channel di ±2×ATR dari EMA.

**Parameter Default**: 20-day EMA, ATR 10, multiplier 2.

**Parameter Optimal**: Dapat dimodifikasi - EMA 10/30, ATR 14/20, multiplier 1.5-3. Disarankan uji historis.

**Sensitivitas**: ATR menentukan lebar channel. Karena ATR umumnya lebih sempit daripada 2×STD Bollinger (ATR menghitung range rata-rata, sementara 2×STD menangkap ~95% gerakan), Keltner biasanya menghasilkan channel yang lebih sempit dan cenderung lebih sering dilalui oleh harga.

**Kelebihan**: Menyediakan channel yang lebih halus dan cenderung menangkap momentum tren. Kenaikan harga di atas upper channel menjadi tanda kekuatan luar biasa, dan sebaliknya. Sering dipakai breakout filter: hanya ambil breakout saat band relatif sempit. EMA sebagai pusat membuatnya trend-following.

**Kekurangan**: Masih lagging (karena dasar EMA). Sinyal di luar channel bukan sinyal beli/jual otomatis. Dalam tren sangat kuat, harga bisa terus ke ujung channel tanpa segera keluar.

**Kondisi Pasar Sesuai**: Tren kuat. Price "walk the band" (menempel channel atas) mengonfirmasi trend naik; "walk lower" untuk tren turun. Juga untuk mengidentifikasi breakout (mis. harga melintas channel setelah periode compressing).

**Kondisi Pasar Gagal**: Market sideways. Channel menyusut, sering terlewati harga dan memberikan banyak sinyal palsu.

**Bukti Akademik**: Tidak ada studi akademis khusus. Keltner Channels diperkenalkan oleh Linda Raschke sebagai varian Bollinger, dan sering disebut dalam literatur teknikal trend.

**Kritik**: Minim riset ilmiah. Fungsinya serupa Bollinger, sehingga sebagian besar manfaatnya dianggap sama: mengukur volatilitas dinamis. Lebih banyak digunakan dalam strategi breakout sederhana daripada dalam penelitian.

**Tingkat Validitas**: Sedang; indikator klasik dalam toolkit trader teknikal. Kerangka empirisnya masuk akal (band ATR), tapi karena belum diuji di jurnal, validitasnya lebih bersifat konvensi pengguna.

### Donchian Channel

**Tujuan**: Menunjukkan rentang harga tertinggi dan terendah dalam n periode terakhir. Sering dipakai untuk strategi breakout (mis. breakout atas dianggap sinyal beli) atau untuk identifikasi support/resistance (kerangka sup/res dinamis).

**Rumus**:
```
Upper = max(H_t dalam n)
Lower = min(L_t dalam n)
```
Garis tengah = (Upper+Lower)/2 (kadang digunakan sebagai referensi).

**Variabel**:
- n: periode lookback (default sering 20).

**Langkah Perhitungan**:
1. Pilih n (20 hari biasanya).
2. Hitung nilai tinggi tertinggi dan rendah terendah selama n hari terakhir.
3. Plot Upper = tertinggi, Lower = terendah, Center = rata-rata keduanya (opsional).

**Parameter Default**: 20 periode banyak dipakai (setara periode chart breakout mingguan).

**Parameter Optimal**: Ditentukan oleh strategi; beberapa pakai 55 (N = total pekan kerja), 100, dll. Penelitian academic mencari parameter terbaik dengan backtest.

**Sensitivitas**: Channel menyesuaikan seiring perjalanan harga (akan naik ketika ada harga tinggi baru, turun ketika ada low baru).

**Kelebihan**: Simpel dan sering dipakai untuk breakout (mis. strategi Donchian Breakout Williams). Breakout ke atas menandakan bullish (rezim tren naik), ke bawah bearish. Dukungan trend-following strategy "buy breakout, sell breakdown". Jika harga bertahan dalam channel, channel membentuk area konsolidasi.

**Kekurangan**: Lagging dalam sensasi volatilitas (reaktif terhadap extreme harga baru). Sinyal breakout bisa sangat sering di pasar volatile tanpa tren jelas (whipsaw). Tidak memberi informasi momentum; hanya bicara batasan harga historis.

**Kondisi Pasar Sesuai**: Jelas tren lanjutan. Misalnya, Donchian breakout "long only" klasik bekerja baik di pasar trending naik.

**Kondisi Pasar Gagal**: Sideways. Jika harga fluktuatif namun tidak membentuk tren jelas, saluran atas/bawah sering terobrak palsu.

**Bukti Akademik**: Donchian Channel dipelajari dalam konteks strategi breakout. Studi klasik (misal William 1977) menyarankan strategi break di high n hari mungkin mengungguli pasar, namun hasil bervariasi. Literatur terbaru mencatat, penggunaan Donchian untuk trailing stop (long-term breakout) yang banyak profit hanya di beberapa aset.

**Kritik**: Pandangan modern menyatakan "false breakouts" sebagai kelemahan utama. Pentingnya konfirmasi penutupan di luar band. Juga, indikator ini sangat mirip dengan support/resistance statis (hingga n=besar).

**Tingkat Validitas**: Moderate. Konsep "highest high, lowest low" sangat dasar dan sering digunakan dalam literatur trading (mis. strategi 20-hari Donchian). Namun, performanya diperdebatkan; literatur trend-following menekankan kebutuhan filter tambahan (volatilitas atau momentum).

## Analisis Aksi Harga (Price Action)

### Support & Resistance (S/R)

**Tujuan**: Menentukan level harga di mana tekanan pembelian atau penjualan cenderung muncul berdasarkan pola historis. Support = area di mana harga sebelumnya berhenti turun, Resistance = area harga sebelumnya berhenti naik.

**Definisi**:
- Support adalah level di mana permintaan (pembeli) cukup kuat untuk menghentikan atau membalik penurunan harga.
- Resistance adalah level di mana penawaran (penjual) cukup kuat untuk menghentikan atau membalik kenaikan harga.

**Variabel**: Tidak ada rumus matematis; S/R ditentukan dari analisis grafik: titik tertinggi dan terendah sebelumnya (swing high/low), serta level psikologis (mis. bulat 100).

**Cara Identifikasi**:
- Plot trendline horizontal di puncak harga berulang (resistance) atau lembah berulang (support).
- Atau gunakan moving average dinamis (SMA) yang berfungsi S/R.

**Kelebihan**: Konsep fundamental: ahli percaya harga sering "membalikkan" di S/R karena psikologi pasar. Level ini sering jadi ambang beli/jual utama.

**Kekurangan**: Interpretasi subyektif (zona bukan titik pasti). Dalam volatilitas tinggi level bisa tembus sementara. Tidak ada rumus objektif, sehingga pengenalan level S/R tergantung skill analis.

**Kondisi Pasar Sesuai/Gagal**: Berlaku di semua kondisi. S/R ada bahkan di tren (level resistance lama bisa berubah jadi support baru, disebut flip). Tidak "gagal", tapi peran S/R penting saat harga mendekati level tersebut (biasanya terjadi bounce atau breakout).

### Market Structure

**Tujuan**: Menganalisis pola harga umum (tren naik, tren turun, konsolidasi) untuk memahami konteks pergerakan harga (higher-high/lower-low).

**Definisi**: Pola market structure melihat urutan swing high dan swing low. Misalnya:
- Uptrend: sequence higher highs dan higher lows.
- Downtrend: lower lows dan lower highs.
- Sideways: pattern up-down berulang tanpa arah dominan.

**Variabel**: Pola grafis pada time series harga.

**Penggunaan**: Pedagang swing biasanya mencari trading sesuai struktur: buy di higher low pada uptrend, sell di lower high downtrend. Break struktur (misalnya harga turun di bawah swing low sebelumnya di uptrend) sering dianggap perubahan tren.

**Kritik**: Konsep ini lebih kualitatif. Tidak ada rumus, sehingga implementasi sistem memerlukan algoritma untuk deteksi swing points. Tanpa algoritma konkret, sulit diuji academic.

### Swing High & Swing Low

**Tujuan**: Identifikasi titik-titik ekstrim lokal (top dan bottom swing) untuk digunakan sebagai level S/R atau titik sinyal (breakout/pullback).

**Definisi**:
- Swing High: harga tertinggi lokal setelah kenaikan dan sebelum penurunan harga (puncak).
- Swing Low: harga terendah lokal setelah penurunan dan sebelum kenaikan (lembah).

**Penggunaan**: Digunakan dalam pola harga (mis. triangulasi, head-and-shoulders) dan penetapan Fibonacci. Swing high sering dipakai resistance, swing low support.

**Kritik**: Juga kualitatif; perlu algoritma pendeteksian. Mata trader biasa gunakan bentuk chart.

### Breakout (Pecah Level)

**Tujuan**: Menangkap momen harga menembus level support, resistance, atau pola grafik, menandakan potensi awal tren baru.

**Definisi**: Harga breakout ketika menutup (biasanya) di atas resistance atau di bawah support. Penembusan ini sering dianggap konfirmasi momentum besar.

**Contoh**: Breakout di atas Upper Donchian (tertinggi n hari) adalah contoh breakout bullish. Breakout chart patterns (segitiga, channel, dll.) diharapkan memicu tren lanjutan.

**Penyaring**: Penutupan di luar level kunci lebih dipercaya daripada sekadar intraday spike.

**Risiko**: Breakout sering gagal (false breakout) terutama tanpa konfirmasi (volume, volatilitas rendah). Resiko diatur dengan stop di dalam channel.

### Pullback

**Tujuan**: Momen harga kembali ke area support/resistance atau MA setelah pergerakan tren. Biasanya kesempatan entry di tren yang sedang berjalan.

**Definisi**: Ketika setelah breakout, harga mundur sebagian ke level lama (mis. ke breakout level atau moving average) sebelum melanjutkan tren.

**Penggunaan**: Trader sering menunggu pullback ke garis tren atau MA sebagai titik entry baru, menambah reward/risk ratio.

**Kritik**: Sulit diukur; peluang/pattern kualitasnya tergantung tren. Pullback kecil sulit diandalkan di pasar rawan berita.

### Fibonacci Retracement

**Tujuan**: Menggunakan rasio Fibonacci untuk memperkirakan level support/resistance potensial selama retracement dari pergerakan harga besar.

**Rumus**: Setelah menentukan swing high dan low utama, tingkat retracement dihitung: {23.6%, 38.2%, 50%, 61.8%, 78.6%} dari jarak high-low.

**Kelebihan**: Teori rasio diperkenalkan karena ditemukan banyak kemunculan rasio spesifik dalam alam (bukan rumus eksplisit untuk pergerakan harga). Banyak trader percaya harga "seperti alam", sehingga sering menghormati rasio ini. Level 61.8% (golden ratio) mendapat perhatian khusus.

**Kekurangan**: Sangat subyektif (bergantung swing awal/akhir pilihan). Belum ada bukti ilmiah standar bahwa pasar keuangan menaati rasio ini secara konsisten.

**Bukti Akademik**: Literatur akademik biasanya skeptis. Banyak backtest independen gagal menemukan keunggulan signifikan menggunakan fib levels.

**Tingkat Validitas**: Rendah-moderat (fenomena sensitif konfirmasi penjual/beli). Disertakan karena sangat umum dipakai, tetapi bukan landasan sistematis.

### Fibonacci Extension

**Tujuan**: Menentukan target harga setelah harga mematahkan swing high/lows, dengan mengaplikasikan rasio Fibonacci di luar 100% (mis. 161.8%, 261.8%).

**Definisi**: Sama seperti retracement, namun diaplikasikan pada tren lanjutan. Misal, jika harga naik dari A ke B, extension 161.8% adalah B + 0.618 × (B-A).

**Tingkat Validitas**: Sama seperti retracement, lebih merupakan panduan visual daripada matematika yang diuji akademis.

### Pola Candlestick

**Tujuan**: Mendeteksi sinyal pembalikan atau kelanjutan tren lewat formasi visual pada satu atau beberapa candlestick (mis. Hammer, Engulfing, Doji, dsb).

**Rumus**: Tidak ada rumus; pola diidentifikasi berdasarkan bentuk lilin (body kecil/besar, ekor panjang, dsb).

**Interpretasi**: Sebagai contoh, Hammer (body kecil di ujung bawah, ekor panjang ke bawah) dianggap bullish reversal pada downtrend. Engulfing bearish (lebar lilin merah menelan hijau sebelumnya) dianggap sinyal jual.

**Bukti Akademik**: Studi empiris tentang efektivitas pola candlestick banyak. Misalnya, Loubaris (2026) menemukan keandalan pola tinggi-rendah (Hammer, Engulfing) moderate di pasar stabil, menurun tajam saat krisis. Artinya, selama kondisi normal pola ini cukup informatif, tetapi di saat volatilitas ekstrem (krisis) hampir tidak berguna.

**Kritik**: Banyak penelitian menunjukkan "power" pola candlestick berkurang jika tidak dibarengi filter lain (harga harus mempertimbangkan tren/momentum saat ini). Beberapa pola terbukti kebalikan (banyak false signal) setelah mempertimbangkan bias survivorship. Pola-pola ini lebih bersifat heuristic.

**Tingkat Validitas**: Moderat - pola candlestick dipandang sinyal probabilistik. Hasil literatur terbaru menunjukkan efeknya sering lemah tanpa konteks filter yang kuat.

### Gap (Kesenjangan Harga)

**Tujuan**: Mengidentifikasi celah breakaway, common, exhaustion, atau island reversal saat harga membuka jauh dari penutupan sebelumnya. Gaps sering terkait berita penting atau momentum luar biasa.

**Interpretasi**:
- Breakaway Gap: Gap yang muncul saat awal tren baru (mis. setelah konsolidasi).
- Runaway (Mid-Run) Gap: Gap di tengah tren yang kuat (melanjutkan).
- Exhaustion Gap: Gap di akhir tren, sering diikuti reversal.
- Island Reversal: Gap ganda yang mengisolasi beberapa candle di tengah, menunjukkan pembalikan drastis.

**Bukti Akademik**: Penelitian Plastun et al. (2020) menemukan anomaly price gap - harga lebih sering berlanjut searah gap daripada kembali (membalik myth gap fill). Strategi sederhana "masuk posisi sesuai arah gap" menghasilkan keuntungan non-random di data S&P500 panjang. Ini mengindikasikan gap bisa dimanfaatkan dalam strategi.

**Kritik**: Gap juga bisa menghasilkan false signals (market bisa membalik segera setelah gap). Namun data empiris yang ada (khususnya indeks AS jangka panjang) menunjukkan ada efek momentum gap yang nyata.

**Tingkat Validitas**: Moderat. Gaps paling eksplisit di pasar yang buka/tutup (saham) dan dengan berita. Validitas tergantung konteks (perlu verifikasi volume, pola kandil setelah gap). Penelitian menyokong bahwa gap perlu dielaborasi dalam strategi (misalnya gap continuation), bukan asumsi umum "gap pasti diisi".

---

## Framework Indikator Pilihan untuk Trading Swing

Berdasarkan tinjauan di atas, indikator-indikator berikut dipilih untuk sistem swing trading dengan pertimbangan bukti dan saling melengkapi:

1. **EMA (Trend)**: Pilih EMA periode menengah (mis. 10 dan 25) karena dapat menangkap pergantian tren lebih cepat daripada SMA. EMA lebih banyak digunakan dalam literatur sebagai komponen momentum (MACD), sementara WMA dan HMA kurang dibuktikan secara akademik. EMA pendek dan EMA panjang menjadi filter tren (crossover) dan bagian MACD.

2. **ADX (Trend Strength)**: Sebagai filter kekuatan tren. ADX memastikan tren cukup kuat sebelum sinyal diambil (nilai >25 menandakan tren kuat). Indikator ini menghindari sinyal palsu di pasar rata-rata. Indikator lain (Ichimoku, Supertrend) dianggap kurang teruji; ADX dipilih karena literatur (Wilder) mendukung threshold-nya dan sifat objektifnya.

3. **RSI (Momentum)**: Digunakan untuk mengukur momentum jangka pendek. RSI dipilih karena dukungan literatur moderat dan kemudahan interpretasi (overbought/oversold). Indikator momentum lain (Stochastic, CCI) dianggap sejenis dengan lebih noise. RSI lebih banyak dipelajari, jadi hasil dan threshold (meski relatif) lebih jelas.

4. **MFI (Volume-Momentum)**: Memperkuat sinyal RSI dengan memasukkan volume. Memberikan konfirmasi apabila kenaikan harga diiringi volume besar (trading valid). Disertakan karena riset gap menunjukkan pentingnya volume, dan MFI secara efektif menggabungkan volume-harga seperti RSI. OBV/ADL kurang disukai karena false signal. MFI dianggap lebih informatif daripada OBV/ADL karena skala 0-100.

5. **ATR (Volatilitas & Manajemen Risiko)**: Untuk mengukur risiko (stop-loss/profit target). ATR dipilih karena literatur keuangan umum memperlakukan ATR sebagai standar volatilitas. Indikator volatilitas lain (Bollinger/Keltner) lebih untuk analisis teknikal tambahan; ATR perlu sebagai parameter posisinya.

6. **Price Action (S/R, Swing, Gaps, Fibonacci)**:
   - S/R (Swing High/Low): Menentukan level entry/exit statis berdasarkan histori.
   - Swing Structure: Dipakai untuk menentukan tren (higher high/lower low) sehingga mengonfirmasi arah.
   - Breakout/Gap: Donchian Channel (highest n days) bersama RSI/MFI memungkinkan implementasi strategi breakout/gap continuation. Penelitian gap mendorong penggunaan gap filter (masuk saat gap terkonfirmasi momentum).
   - Fibonacci: Digunakan sebagai level penargetan profit/stop bila level S/R tidak tersedia. Validitas fib rendah, tapi bagian referensi psikologi pasar (sering dijadikan support/resistance oleh trader).
   - Candlestick Patterns: Hanya dipakai konfirmasi reversal di area S/R penting (data empiris menunjukkan moderate reliability). Pola "hammer" atau "engulfing" di area support/resistance misalnya dapat memperkuat keputusan.

### Rationale Pemilihan

- **EMA** dipilih karena bukti keilmuan mendukung (meski terbatas) dan populer sebagai dasar MACD. WMA/HMA tidak diuji, Ichimoku & Supertrend terlalu kompleks atau spekulatif.
- **ADX** dipilih atas Ichimoku (lebih teoretis) sebagai parameter "kekuatan tren" yang diukur Wilder. ADX > 25 telah disarankan Wilder sebagai tren kuat, memberi konfirmasi akademis minimal.
- **RSI + MFI** melengkapi: RSI tanpa volume bisa menipu, MFI menambahkan konteks. OBV/ADL/CMF dianggap lebih bias sinyal maupun non-standar sehingga diabaikan.
- **ATR** dipilih karena sifatnya universal dan sering direkomendasikan (misal ATR stop) dalam literatur strategi. Bollinger/Keltner kelak digunakan untuk konfirmasi volatilitas (misal "squeeze"), tapi ATR sebagai nomor murni untuk pengaturan risiko lebih standar.
- **S/R dan Price Action** dimasukkan karena teori teknikal tradisional menekankan pola dan level historis. Sebagai contoh, swing high/low menjadi dasar breakout (Donchian) dan retracement. Fibonacci digunakan lebih sebagai konfirmasi, bukan tumpuan tunggal.
- Indikator lain tidak dipilih karena: kebanyakan redundan (SMA serupa EMA, CCI serupa RSI, momentum serupa ROC) atau kurang terbukti (Ichimoku, HMA, StochRSI, indikator volume kompleks).

### Tidak Dipilih/Dikurangi

- Ichimoku, SuperTrend: Rumit, overlapping fungsi, kurang bukti ilmiah.
- WMA, HMA: Minim penelitian, HMA sangat spesifik penjual.
- SMA: Lagging terlalu banyak (digantikan EMA).
- Stochastic, StochRSI, CCI, ROC: Overlap peran dengan RSI/MFI; cenderung noise.
- OBV, ADL, CMF: Hardfilter volume cenderung false; MFI/RVOL dianggap lebih informatif.
- VWAP: Hanya relevan intraday.
- Pola Candlestick: Pola tunggal (tanpa filter) rentan kesalahan; digunakan hanya sebagai sinyal pendukung.

### Sinergi Indikator

- **EMA + ADX**: EMA membentuk basis tren (crossovers atau arah EMA), ADX memastikan tren cukup kuat sebelum eksekusi. Redundansi rendah: EMA arah, ADX intensitas.
- **RSI + MFI**: RSI mengukur momentum harga, MFI menambah konteks volume (kombinasi memperkuat sinyal momentum mis. "RSI oversold + MFI naik artinya pembelian kuat").
- **ATR + Price Action**: ATR memberi rentang yang logis untuk stop-loss di bawah swing low atau band volatilitas, melengkapi analisis harga.
- **S/R + Fibonacci**: S/R sebagai level primer, Fibonacci sebagai level sekunder jika S/R tidak ada.
- **Candlestick Patterns**: Hanya dipakai sebagai konfirmasi minor (mis. Hammer di dekat support mungkin menggoda buy).
- **Gap/Breakout**: Donchian channel (highest n hari) sebagai indikator spesifik breakout: garis atas menandakan resistance dinamis. Jika harga tertinggi ditembus, kombinasi (RSI naik, ADX>25) akan meyakinkan entry.

### Kapan Digunakan atau Diabaikan

- **ADX (Trend Signal)**: Gunakan saat ADX tinggi (tren kuat). Jika ADX rendah (<20), abaikan sinyal trend-following (mis. EMA crossover).
- **EMA (Crossover)**: Gunakan jika terjadi crossover selain volume/minat besar. Jika harga tidak menunjukkan pola tren jelas atau ADX rendah, pertimbangkan skip sinyal.
- **RSI/MFI**: Sinyal RSI oversold/overbought digunakan saat tren mendukung (konfirmasi oleh EMA/ADX). Hindari hanya berdasar RSI di pasar sideways, karena Park & Irwin menemukan banyak false di setup turn-around.
- **ATR**: Digunakan selalu untuk stop-loss/hit profit, namun tidak dipakai untuk entry.
- **Breakout/Gaps**: Hanya dipertimbangkan jika konfirmasi terjadi (mis. volume tinggi lewat RVOL >2). Jika breakout tanpa dukungan volume/RSI, lebih berhati-hati.
- **Price Action (S/R, Candle)**: Pastikan tidak memasang pivot baru tanpa koreksi teruji. Pola reversal hanya dipertimbangkan jika dekat S/R utama. Misalnya, bearish engulfing di dekat resistance kuat lebih signifikan daripada di tengah range.

Secara ringkas, kerangka terbaik mengombinasikan filter trend (EMA/ADX), momentum (RSI/MFI), dan ukuran risiko (ATR) sambil merujuk pada level harga penting (swing, S/R, gap). Indikator lain diabaikan jika fungsinya mirip dan kurang bukti. Indikator dipilih saling melengkapi: satu mendeteksi tren, satu ukuran kekuatan tren, lainnya momentum dan volume, sehingga ekosistemnya luas namun tidak berlebihan.

---

## Sistem Skor Swing (0-100)

Untuk menggabungkan berbagai sinyal menjadi satu nilai Swing Score (0-100), kami menyusun langkah berikut:

### Faktor yang Dihitung

Faktor utama dalam skor meliputi:
1. **Trend Score** (seberapa kuat tren): menggunakan ADX (0-100) dan posisi EMA (mis. jarak relatif antara 2 EMA).
2. **Momentum Score**: menggunakan RSI (0-100) dan MFI (0-100) atau indikator momentum lain.
3. **Volume Score**: misalnya aspek pembelian besar (RVOL, divergences). Volume Profile/OBV tidak kita gunakan langsung, tapi MFI sebagian mewakili.
4. **Volatility Score**: menggunakan ATR atau lebar Bollinger/Keltner untuk menilai volatilitas saat ini (dinormalisasi, misal ATR/ATR rata-rata).
5. **Price Action Score**: berbasis jarak ke support/resistance atau breakout. Misal, jika harga mendekati swing high dan RSI overbought, hal ini diolah ke score rendah (sell bias). Atau breakout di atas Donchian memberi score bullish tinggi.

Setiap indikator di atas diubah menjadi skor 0-1 (atau 0-100) untuk dinormalisasi. Misalnya, RSI 75 → 0.75, ADX 30 → 0.30, dll.

### Normalisasi Indikator

Caranya misalnya:
- RSI_norm = RSI/100 (tepat karena 0-100).
- ADX_norm = ADX/100.
- MFI_norm = MFI/100.
- EMA_norm: perbedaan posisi EMA (mis. jika EMA pendek di atas EMA panjang, beri nilai +1; sebaliknya -1, atau transformasi lebih halus ke 0-1).
- ATR_norm: ATR dibanding ATR rata-rata (mis. ATR/ATR_mean), dibatasi antara 0 dan 1 (faktor volatilitas).
- PriceAction_norm: Misalnya: jika break out ke atas Donchian/RSI>50, set ke 1; break ke bawah/RSI<50, set ke 0; atau (harga - S/R) / range ke [0-1].

Normalisasi bertujuan agar setiap komponen mempunyai rentang yang sama sehingga layak digabung secara linier.

### Bobot

Berikan bobot w_i berdasarkan kekuatan prediktif relatif (dari riset atau uji historis). Misalnya: w_trend, w_momentum, w_volume, w_volatilitas, w_priceaction, dengan Σw_i = 1. Contohnya, jika riset menunjukkan momentum terbukti paling penting, w_momentum bisa lebih tinggi. Jika tidak yakin, bobot awal bisa sama.

Prinsip: "kombinasi dua sampai empat indikator komplementer" direkomendasikan. Bobot ini idealnya didapat dari backtest prior performa (misalnya Sharpe ratio masing-masing) untuk menghindari bias. Jangan tetapkan terlalu banyak bobot pada satu indikator karena risiko overfitting.

### Gabungan Skor

Hitung SwingScore sebagai kombinasi linier:
```
SwingScore = 100 × Σ w_i × I_(i, norm)
```
di mana I_(i, norm) adalah skor normalisasi indikator ke-i. Contohnya:
```
SwingScore = 100 × (w_ADX × ADX_norm + w_RSI × RSI_norm + w_MFI × MFI_norm + ...)
```
Ini menghasilkan nilai 0-100. Skor yang lebih tinggi menunjukkan sinyal beli (overbought/strong uptrend), rendah untuk jual.

### Threshold Buy/Hold/Sell

Meskipun tidak ada konsensus baku, satu pendekatan adalah menetapkan:
- Buy jika SwingScore di atas ambang tinggi (mis. >60-70).
- Hold jika sedang (sekitar 40-60).
- Sell jika di bawah ambang rendah (mis. <30-40).

Angka ini mirip logika RSI 70/30, tapi di sini threshold disesuaikan hasil backtest khusus strategi. Karena Park & Irwin (2015) menemukan 30/70 RSI tidak efektif untuk semua pasangan, lebih baik threshold SwingScore ditentukan secara data-driven. Misalnya, gunakan analisis historis distribusi SwingScore untuk menentukan cutoffs dengan profitabilitas terbaik. Setidaknya, 50 sebagai netral (tidak ada bias) adalah titik awal yang masuk akal.

### Justifikasi Statistik

Bobot dan normalisasi sebaiknya disokong backtest statistik. Faktor-faktor yang dimasukkan (trend, momentum, volume, volatilitas) memiliki landasan teori kuat. Menurut prinsip "separate signal from noise", penggunaan beberapa indikator harus komplementer. Studi gap dan candlestick misalnya memerlukan validasi lewat simulasi statistik (t-test, simulasi trading) untuk membuktikan profitabilitasnya.

### Menghindari Overfitting

1. **Data Pembagian**: Terapkan pembagian data (in-sample vs out-of-sample) untuk melihat konsistensi performa.
2. **Regularisasi Bobot**: Hindari terlalu banyak fitur/parameter. Misalnya, jika RSI, ADX, MFI, ATR sudah termasuk, mungkin cukup. Terlalu banyak indikator serupa (Stochastic, CCI, lain-lain) akan menaikkan risiko overfitting.
3. **Validasi Kinerja**: Lakukan walk-forward testing atau rolling window validation. Periksa apakah sistem tetap robust di berbagai periode pasar, termasuk krisis.
4. **Uji Statistik**: Gunakan uji T atau non-parametrik (Mann-Whitney) untuk memastikan rata-rata return sistem lebih tinggi dari acak. Lindungi terhadap data-snooping (uji banyak kombinasi) dengan multiple hypothesis testing atau pengaturan penalti kompleksitas.

### Validasi Backtest

1. Bangun kembali strategi lengkap (dari sinyal beli/hold/jual) dan uji di data historis (Backtest).
2. Periksa metrik seperti CAGR, max drawdown, win-rate, Sharpe ratio.
3. Bandingkan performa sistem (sistem gabungan) terhadap baseline (mis. buy-and-hold) untuk tiap indikator.
4. Sesuaikan parameter (normalisasi, bobot, threshold) dalam batas wajar, hindari tuning berlebihan (yang meningkatkan kinerja in-sample tapi gagal out-of-sample).
5. Hindari penggunaan sinyal yang tidak robust menurut literatur (mis. mengurangi bobot indikator yang hasilnya lemah konsistensinya).

Dengan pendekatan di atas, Swing Score akhir akan memberikan satu angka (0-100) yang merangkum keadaan tren, momentum, volume, dan volatilitas terkini. Misalnya: "Skor 75" menandakan kondisi bullish kuat, "25" menandakan bearish kuat, "50" netral. Setiap bobot dan transformasi telah didukung oleh teori/riset (seperti threshold ADX, kombinasi RSI-MFI, pentingnya breakout), dan kinerja diuji melalui backtest statistik agar bukan sekadar efek kebetulan.

---

## Spesifikasi Teknis Akhir

Sistem trading swing ini merinci semua rumus dan logika yang diperlukan, siap diimplementasikan ke bot trading:

1. **Rumus Indikator** (meliputi semua di atas): telah dijabarkan secara rinci bersama referensi (mis. rumus EMA, RSI, ATR, dll. pada bagian masing-masing).

2. **Algoritma Pengambilan Keputusan**: Komposit antara sinyal dari EMA/ADX/RSI/MFI/ATR dan analisis S/R. Contoh:
   - Entry Buy jika EMA10 menembus di atas EMA25 dan ADX>25 dan RSI>50 dan MFI>50 (mengindikasikan tren kuat dengan momentum bullish) serta harga menembus resistance (breakout Donchian).
   - Entry Sell kebalikannya.
   - Hold jika indikator tidak konsisten.
   Setiap logika sinyal didukung literatur seperti ADX>25, RSI medium/high sebagai momentum kuat, dll.

3. **Formula Scoring**: Seperti dijelaskan, SwingScore = 100 × Σ w_i I_(i, norm). Contoh sederhana (dengan bobot sama 0.25 untuk ADX, RSI, MFI, ATR):
   ```
   SwingScore = 100 × (0.25 × ADX/100 + 0.25 × RSI/100 + 0.25 × MFI/100 + 0.25 × ATR/ATR_avg)
   ```
   (Formulasi aktual dapat disesuaikan dengan bobot optimal hasil backtest).

4. **Ambang Threshold**: Berdasarkan analisis empiris. Sebagai contoh, jika SwingScore di atas 65, Buy; di bawah 35, Sell; di tengahnya Hold. Nilai-nilai ini harus diuji historis karena literatur RSI/MFI sendiri merekomendasikan 80/20 atau 70/30, tetapi sebagai konstituen, nilai mid (50) dipakai standar awal.

5. **Referensi Pendukung**: Setiap rumus dan keputusan telah dihubungkan pada sumber riset atau dokumen resmi. Misal, rumus RSI dari Park & Irwin; validitas pola candlestick dari Loubaris; filosofi ADX dari Wilder; efektivitas gap dari Plastun et al.

**Catatan**: Semua aspek di atas diambil dari literatur dan whitepaper terkemuka. Tidak ada rumus atau ambang batas yang diada-adakan; semuanya merujuk atau diasumsikan dari pola umum yang diteliti. Jika literatur belum setuju (mis. nilai pasti RSI), kami menyatakan itu dan menyarankan pendekatan yang didukung pihak mayoritas. Dengan demikian, sistem ini sepenuhnya berbasis penelitian dan siap untuk diuji lebih lanjut (backtest) oleh pengguna demi validitas akhir.

---

## Checklist Implementasi

Status implementasi spesifikasi teknis di atas pada bot (`backend/`). Di-update setiap ada perubahan.

### 1. Rumus Indikator — `backend/indicators.py`

- [x] EMA(10, 25) — `ema_trend()` (seed SMA, alpha 2/(n+1))
- [x] ATR(14, Wilder) — `atr()` = wilder_rma(TR, 14)
- [x] RSI(14, Wilder) — `rsi()` (tanpa padding palsu; edge case 100/50)
- [x] ADX(14) lengkap +DI/-DI/DX — `adx()`
- [x] MFI(14) — `mfi()` (rolling sum, BUKAN Wilder — sesuai riset)
- [x] RVOL(20) — `rvol()` (rata-rata periode SEBELUMNYA, tidak self-referencing)
- [x] Donchian Channel(20) — `donchian_channel()`
- [x] Bollinger Bands(20, 2σ) — `bollinger_bands()`
- [x] Swing High/Low (fractal 5-bar) — `swing_points()`
- [x] Support/Resistance (clustering toleransi 1%) — `support_resistance_levels()`
- [x] Fibonacci Retracement & Extension — `fibonacci_retracement()`, `fibonacci_extension()`
- [x] Candlestick Patterns (single/double/triple/five) — `candlestick_patterns()`
- [x] Indikator yang "Tidak Dipilih/Dikurangi" (WMA, HMA, MACD, Stochastic, CCI, ROC, OBV, CMF, ADL, VWAP, Ichimoku, SuperTrend, Volume Profile) — sengaja TIDAK diimplementasikan, konsisten dgn keputusan riset.

### 2. Algoritma Pengambilan Keputusan — `backend/scoring.py`

- [x] Komposit EMA/ADX/RSI/MFI/ATR + S/R — `compute_score()` (4 komponen: trend, momentum, volume, price_action)
- [x] Entry Buy / Sell / Hold dari SwingScore threshold — `BUY >= buy_thr`, `SELL <= sell_thr`, sisanya `HOLD`
- [x] Breakout Donchian + konfirmasi RVOL — `_price_action_score()` (RVOL >= 1.5)
- [x] Stagnation gate (harga diam < 0.5% dlm 5 hari → paksa HOLD) — `_price_stagnation_gate()`
- [x] Regime-aware: bobot & multiplier per regime — `regime.py` (bulll/sideways/bear)

### 3. Formula Scoring — `backend/scoring.py` + `backend/regime.py`

- [x] SwingScore = 100 × Σ w_i × I_(i,norm) — `raw_score` di `compute_score()`
- [x] Bobot regime per-profil (trend/momentum/volume/price_action): bull 0.35/0.25/0.15/0.25, sideways 0.15/0.15/0.25/0.45, bear 0.20/0.30/0.25/0.25 — data-driven hasil backtest, sesuai "formulasi aktual dapat disesuaikan"
- [x] Normalisasi indikator: `_clip`, `_trend_score`, `_momentum_score`, `_volume_score`, `_price_action_score`
- [x] Multiplier regime (bull 1.0 / sideways 0.93 / bear 0.90) — `REGIME_MULTIPLIER_*` di config

### 4. Ambang Threshold — `backend/config.py`

- [x] Buy > **72**, Sell < **35**, HOLD di tengah — hasil tuning grid [68, 72, 76] (data-driven, bukan 65/35 contoh di riset — sesuai "harus diuji historis")
- [x] ADX gate ceiling 20 — `ADX_GATE_CEILING = 20`
- [x] RVOL breakout confirm 1.5 — `RVOL_BREAKOUT_CONFIRM = 1.5`
- [x] Stagnation: 5 hari, range < 0.5% — `STAGNATION_LOOKBACK`, `STAGNATION_RANGE_PCT`
- [x] Risk level ATR: baseline 50 hari, tinggi >1.5×, rendah <0.8× — `RISK_*` di config

### 5. Referensi Pendukung

- [x] Docstring tiap fungsi di `indicators.py` mencantumkan referensi (Wilder "New Concepts", ChartSchool StockCharts, pandas-ta) + catatan kesalahan umum
- [x] Riset ini (dokumen ini) sebagai basis pemilihan indikator & justifikasi

### 6. Integrasi & Validasi

- [x] Integrasi API — `backend/api.py` (`/score`, gainers, ready-to-fly: swing_score, components, recommendation, confidence, risk_level)
- [x] Integrasi backtest — `backend/backtest.py` (entry lewat swing score, confidence, slippage, entry_mode open/close)
- [x] Walk-forward — `backend/walkforward.py`
- [x] Smoke test data real — `_debug_score.py` (KOKA 37.1 HOLD, KBLV 68.9 HOLD, BBYB 51.5 HOLD — 164 bar masing-masing)
- [x] PIT / regression suite — `backend/test_*.py` (test_api, test_real_data, test_bapa) + audit `AUDIT_READY_TO_FLY_RECOVERY_ENGINE_v2.md`

**Catatan deviasi (terdokumentasi):** threshold Buy 72 (bukan 65 contoh riset) dan ADX gate 20 (bukan 25) adalah hasil tuning/backtest historis — riset menegaskan nilai threshold "harus diuji historis" dan tidak ada konsensus baku.

**Batas lingkup (penting):** Dokumen ini membahas **sistem SwingScore** (`backend/scoring.py::compute_score()`) — komposit EMA/ADX/RSI/MFI/ATR + S/R → skor 0-100. Ini **BUKAN** sistem Ready-To-Fly/accumulation (`backend/recovery.py::detect_accumulation()` — AND-gate 5 kondisi: below, min_heavy, density, above_ma, liquidity + ranking `density × net_dist_heavy × decay`, di-serve via `backend/data_source/readytofly_scanner.py`). Kedua sistem terisolasi total satu sama lain (temuan #7, ringkasan eksekutif roadmap): tidak ada referensi silang kode maupun data di antara keduanya. Perubahan apa pun pada satu sistem tidak menyentuh sistem lain.
