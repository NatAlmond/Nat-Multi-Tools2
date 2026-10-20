# Nat-Multi Tools

**All-In-One Toolkit** — Downloader · Comic · Novel · GIF · AI · Safelink

**By: Nat**

---

## Fitur

| Tab | Isi |
|-----|-----|
| **Downloader** | TikTok, Instagram, Facebook, Twitter/X, YouTube (yt-dlp) |
| **Comic** | MangaDex, Komiku, **KeiKomik** (gratis) · Voratoon, Wurmz, KomikIndo (premium) |
| **Novel** | WB Novel (scrape) |
| **GIF** | Gifukai (tanpa API key) |
| **AI Chat** | Groq Llama + Gemini |
| **AI Image** | Gemini Image |
| **Lihat Kenyataan** | Analisis klaim (Groq) |
| **Safelink** | Bypass link pendek |
| **Secret** | Aktivasi Premium / Admin |

### Role

| | Free | Premium | Admin |
|--|------|---------|-------|
| Source comic premium | Terkunci | Buka | Buka |
| AI Chat / hari | 30 | 200 | ∞ |
| AI Image / hari | 5 | 40 | ∞ |
| Download / hari | 8 | 50 | ∞ |

**Kode Premium / Admin:** **JANGAN** ditulis di README atau repo publik.
Simpan hanya di **Environment Variables Vercel** (`ADMIN_CODE`, `PREMIUM_CODES`).
Bagikan kode ke user secara pribadi saja.

Pesan kunci: `Source Premium, Harap Gunakan Premium Untuk Membuka.`

---

## File di root repo

```
main.py
index.html
requirements.txt
vercel.json
README.md
banner1.gif · banner2.gif · banner3.gif   (opsional)
```

Nama file **harus persis** (bukan `main-5.py` / `index-8.html`).

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

## Deploy ke Vercel

### 1. Ambil API Key

**Groq (AI Chat)**
https://console.groq.com → API Keys → Create → salin `gsk_...`

**Gemini (AI Image)**
https://aistudio.google.com/apikey → Create API Key → salin

### 2. Upload GitHub

1. Buka repository
2. **Add file → Upload files**
3. Upload semua file di atas
4. **Commit changes**

### 3. Vercel + Environment Variables

1. https://vercel.com → Login with GitHub
2. **Add New → Project** → pilih repo
3. Framework: **Other**
4. **Settings → Environment Variables** (centang **Production** + **Preview**):

| Key | Value (contoh) | Wajib? |
|-----|----------------|--------|
| `GROQ_API_KEY` | `gsk_....` | Ya (AI Chat) |
| `GEMINI_API_KEY` | key Gemini | Ya (AI Image) |
| `ADMIN_CODE` | (kode admin milikmu — rahasia) | Opsional |
| `PREMIUM_CODES` | (kode premium milikmu, dipisah koma) | Opsional |

**Artinya “dipisah / pisahkan dengan koma”:**
Kalau kode premium **lebih dari satu**, tulis semuanya di **satu** Value, dipisah tanda koma `,`.

Contoh benar:
```
KODE1,KODE2,KODE3
```

Contoh salah (jangan enter / baris baru untuk tiap kode di Value yang sama tanpa koma):
```
KODE1
KODE2
```

5. **Save** → **Deploy** / **Redeploy**
6. Setelah ubah env, **wajib Redeploy** agar aktif

### 4. Cek

- Buka `https://DOMAIN.vercel.app/health` → harus ada status ok
- Tab **Secret** → uji kode Premium/Admin
- Tab **Comic** → coba MangaDex / KeiKomik

---

## Comic sources (teknis)

| Source | Akses | Keterangan |
|--------|--------|------------|
| MangaDex | Gratis | API resmi, paling stabil + filter ID/EN |
| Komiku | Gratis | API/HTML |
| KeiKomik | Gratis | Scrape homepage (search situs lemah) |
| Voratoon | Premium | API |
| Wurmz | Premium | Scrape |
| KomikIndo | Premium | Scrape |

Source HTML bisa rusak jika situs ganti struktur — itu normal di Vercel.

---

## Endpoint utama

| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/` | Frontend |
| GET | `/health` | Status |
| POST | `/download` | yt-dlp |
| GET | `/comic/search` | `source`, `q` |
| GET | `/comic/detail` | `source`, `id`, `lang` |
| GET | `/comic/chapter` | `source`, `id` |
| GET | `/novel/search` | `q` |
| GET | `/gif/search` | `q` |
| POST | `/ai/chat` | Groq / Gemini |
| POST | `/ai/image` | Gemini |
| GET | `/safelink/bypass` | `url` |
| POST | `/premium/verify` | kode Premium/Admin |

---

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| Halaman kosong | `index.html` di root + nama benar + redeploy |
| AI 503 | Env belum diisi / belum redeploy |
| Comic kosong | Coba MangaDex dulu; source Indo bisa CF |
| Premium tidak aktif | Kode di Secret harus sama dengan `PREMIUM_CODES` / default server |
| Loading lama | Cold start Vercel Hobby — normal request pertama |

---

**By: Nat**
