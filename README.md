# Nat-Multi Tools

**All-In-One Toolkit** — Downloader · Comic · Anime · Novel · Movie · GIF · AI · Safelink

**By: Nat**

---

## Fitur

| Tab | Isi |
|-----|-----|
| **Downloader** | TikTok, Instagram, Facebook, Twitter/X, YouTube (yt-dlp) |
| **Comic** | MangaDex, Komiku, Voratoon, **Wurmz (Premium)**, Shinigami / Manhwa Desu (Premium) |
| **Anime** | Jikan (metadata) + best-effort scrape |
| **Novel** | WB Novel (scrape) |
| **Drama / Movie** | Mirror LK21 (best-effort) |
| **GIF** | Gifukai (tanpa API key) |
| **AI Chat** | Groq Llama + Gemini |
| **AI Image** | Gemini Image + Pollinations fallback |
| **Safelink** | Bypass link pendek (multi-method) |
| **Secret** | Aktivasi Premium / Admin |

### Role

| | Free | Premium | Admin |
|--|------|---------|-------|
| Comic Wurmz / Voratoon / Shinigami / Manhwa Desu | Terkunci | Buka | Buka |
| AI Chat / hari | 30 | 200 | ∞ |
| AI Image / hari | 5 | 40 | ∞ |
| Download / hari | 8 | 50 | ∞ |

**Kode Premium / Admin:** tidak dipublikasikan di README.
Simpan hanya di `main.py` (server) dan bagikan kode ke user secara pribadi.
Jangan commit daftar kode ke repo publik jika tidak ingin terbaca siapa saja.

Pesan kunci source Premium:
`Source Premium, Harap Gunakan Premium Untuk Membuka.`

---

## File yang wajib ada di root repo

```
main.py
index.html
requirements.txt
vercel.json
README.md
banner1.gif · banner2.gif · banner3.gif   (opsional)
```

**Nama file harus persis** (bukan `main-5.py` / `index-8.html`).

---

## requirements.txt

```
fastapi
uvicorn
yt-dlp
httpx
python-multipart
pydantic
beautifulsoup4
```

---

## Deploy ke Vercel (langkah demi langkah)

### 1. API Key

**Groq (AI Chat)**
1. https://console.groq.com → API Keys → Create
2. Salin key (`gsk_...`)

**Gemini (AI Chat + Image)**
1. https://aistudio.google.com/apikey → Create API Key
2. Salin key

### 2. GitHub

1. Buat/buka repository
2. **Add file → Upload files**
3. Upload semua file di atas
4. **Commit changes**

### 3. Vercel

1. https://vercel.com → Login with GitHub
2. **Add New → Project** → pilih repo
3. Framework: **Other**
4. **Environment Variables** (centang **Production** + **Preview**):

| Key | Value |
|-----|--------|
| `GROQ_API_KEY` | `gsk_...` |
| `GEMINI_API_KEY` | key Gemini kamu |

> **Key** = nama variabel (`GROQ_API_KEY`).
> **Value** = isi secret key yang kamu tempel.

5. **Deploy**
6. Tunggu selesai → buka URL project

### 4. Redeploy setelah ubah file

Commit di GitHub biasanya auto-deploy.
Atau: Vercel → Deployments → **Redeploy**.

---

## Verifikasi

1. `https://DOMAIN.vercel.app/health`
   Harus mirip: `{"status":"ok","bs4":true,"ytdlp":true,...}`
2. Comic → **MangaDex** / **Komiku** → Cari → harus ada hasil
3. Comic → **Wurmz ★ Premium** (belum Premium) → pesan kunci
4. Secret → kode Premium → aktif
5. Comic → **Wurmz** → Cari / Muat → buka chapter
6. AI Chat → kirim "halo" (butuh API key)

---

## Banner carousel (opsional)

1. Siapkan 3 GIF, idealnya **1200×300**, max ~2 MB
2. Nama **persis**: `banner1.gif`, `banner2.gif`, `banner3.gif`
3. Upload ke **root** repo
4. Redeploy

Tanpa file banner, area banner bisa kosong / fallback teks.

---

## Comic sources (teknis)

| Source | Metode | Keterangan |
|--------|--------|------------|
| MangaDex | API resmi | Paling stabil |
| Komiku | `api.komiku.org` + `komiku.org` | Stabil relatif |
| Voratoon | Scrape `v10.voratoon.com` | Bukan `voratoon.id` (landing DNS) |
| **Wurmz** | Scrape `wurmz.net` | **Premium** |
| Shinigami / Manhwa Desu | Scrape best-effort | Sering CF / domain ganti |

Source HTML bisa rusak jika situs ganti struktur — itu normal.

---

## Catatan penting

- **Vercel serverless**: timeout & IP cloud bisa membuat scrape/anime stream gagal.
- **Anime full stream** di cloud sering diblok; Jikan = metadata, bukan player.
- **Spotify** tidak didukung (DRM).
- YouTube kadang diblok di server cloud.
- Jangan commit API key ke GitHub; pakai Environment Variables Vercel saja.
- Role Premium/Admin disimpan di `localStorage` browser (bukan akun server).

---

## Endpoint utama

| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/` | Frontend |
| GET | `/health` | Status |
| POST | `/download` | yt-dlp |
| GET | `/comic/search` | `source`, `q` |
| GET | `/comic/detail` | `source`, `id` |
| GET | `/comic/chapter` | `source`, `id` |
| GET | `/anime/search` | `source`, `q` |
| GET | `/novel/search` | `q` |
| GET | `/movie/search` | `q`, `type` |
| GET | `/gif/search` | `q` |
| POST | `/ai/chat` | Groq / Gemini |
| POST | `/ai/image` | Gemini / Pollinations |
| GET | `/safelink/bypass` | `url` |
| POST | `/premium/verify` | kode Premium/Admin |

---

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Halaman kosong | Pastikan `index.html` di root + nama benar + redeploy |
| `bs4: false` | `beautifulsoup4` di requirements + redeploy |
| AI 503 | Environment Variables belum diisi / belum redeploy |
| Comic kosong | Coba MangaDex dulu; source Indo bisa down/CF |
| Wurmz terkunci | Aktifkan Premium di tab Secret |
| Loading lama | Cold start Vercel Hobby — normal di request pertama |

---

**By: Nat**
