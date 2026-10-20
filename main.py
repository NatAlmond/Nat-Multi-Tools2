"""
Nat-Multi Tools v4.6 — scrape fix + downloader PERFECT VERSION
All-in-One Toolkit: Downloader · Comic · Anime · Novel · Movie · GIF · AI
By: Nat🥜
"""
import os, re, uuid, time, hashlib, urllib.parse
from pathlib import Path
from typing import List
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import httpx

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

# ---------- Setup ----------
DOWNLOAD_DIR = Path("/tmp/downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Nat-Multi Tools", version="4.6.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def env(k: str, d: str = "") -> str:
    return os.environ.get(k, d).strip()

# ---------- Rate Limiting ----------
usage_db = defaultdict(lambda: {"chat": 0, "image": 0, "download": 0, "reset_at": 0})

def get_usage(client_ip: str, role: str):
    now = time.time()
    u = usage_db[client_ip]
    if now > u["reset_at"]:
        u["chat"] = u["image"] = u["download"] = 0
        u["reset_at"] = now + 86400
    limits = {
        "free": {"chat": 30, "image": 5, "download": 8},
        "premium": {"chat": 200, "image": 40, "download": 50},
        "admin": {"chat": 999999, "image": 999999, "download": 999999},
    }
    return u, limits[role]

def detect_role(request: Request) -> str:
    auth = (request.headers.get("Authorization") or "").strip()
    # Bearer optional
    if auth.lower().startswith("bearer "):
        auth = auth[7:].strip()
    low = auth.lower()
    if low == "admin":
        return "admin"
    if low == "premium":
        return "premium"
    return "free"

# ---------- Config ----------
ADMIN_CODE = env("ADMIN_CODE", "PEANUTSBUTTERCUP")
ADMIN_HASH = hashlib.sha256(ADMIN_CODE.encode()).hexdigest()
FIXED_PREMIUM_CODES = {"ZURAALMOND", "NATSIGMA", "OHYAYES", "SKIBIDIMOMENT", "ROHANCHESS"}
PREMIUM_SOURCES = {"voratoon", "komikindo"}
ADMIN_SOURCES = {"wurmz"}  # hanya Admin

# ---------- Models ----------
class DownloadRequest(BaseModel):
    url: str
    type: str = "video"
    quality: str = "best"

class ChatRequest(BaseModel):
    model: str = "groq"
    messages: List[dict]

class ImageRequest(BaseModel):
    model: str = "gemini"
    prompt: str

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
}

# ============================================================
# FRONTEND
# ============================================================
@app.get("/", response_class=HTMLResponse)
def home():
    for p in [Path(__file__).parent / "index.html", Path.cwd() / "index.html"]:
        try:
            if p.exists():
                return HTMLResponse(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return HTMLResponse("<h1>index.html tidak ditemukan</h1>", status_code=404)

@app.get("/health")
def health():
    return {"status": "ok", "version": "4.6.0", "ytdlp": HAS_YTDLP, "bs4": HAS_BS4}

@app.get("/banner.gif")
@app.get("/banner1.gif")
@app.get("/banner2.gif")
@app.get("/banner3.gif")
def serve_banner(request: Request):
    name = request.url.path.lstrip("/")
    for base in (Path(__file__).parent, Path(__file__).parent / "public"):
        p = base / name
        if p.exists():
            return FileResponse(p, media_type="image/gif")
    raise HTTPException(404, "banner not found")

# ============================================================
# DOWNLOADER
# ============================================================
@app.post("/download")
async def download(req: DownloadRequest, request: Request):
    if not HAS_YTDLP:
        raise HTTPException(500, "yt-dlp tidak terpasang")
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL tidak valid")
    if "spotify.com" in req.url.lower():
        raise HTTPException(400, "Spotify tidak didukung (DRM)")
    
    client_ip = request.client.host if request.client else "unknown"
    role = detect_role(request)
    usage, limits = get_usage(client_ip, role)
    if usage["download"] >= limits["download"]:
        raise HTTPException(429, f"Limit download harian ({limits['download']}x)")
    
    file_id = str(uuid.uuid4())[:8]
    outtmpl = str(DOWNLOAD_DIR / f"{file_id}.%(ext)s")
    
    if req.type == "audio":
        opts = {
            "format": "bestaudio/best", "outtmpl": outtmpl,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "128"}],
            "quiet": True, "no_warnings": True, "noplaylist": True,
            "socket_timeout": 30,
            "retries": 3,
        }
    else:
        fmt_map = {
            "best": "best[ext=mp4]/best",
            "720": "best[height<=720][ext=mp4]/best",
            "480": "best[height<=480][ext=mp4]/best",
            "360": "best[height<=360][ext=mp4]/best",
        }
        opts = {
            "format": fmt_map.get(req.quality, "best[ext=mp4]/best"),
            "outtmpl": outtmpl, "quiet": True, "no_warnings": True, "noplaylist": True,
            "socket_timeout": 30, "retries": 3,
        }
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(req.url, download=True)
            title = info.get("title", "download")
            downloaded = next(DOWNLOAD_DIR.glob(f"{file_id}.*"), None)
            if not downloaded:
                raise Exception("File tidak ditemukan")
            safe = "".join(c for c in title if c.isalnum() or c in " -_")[:60].strip() or "download"
            final = DOWNLOAD_DIR / f"{safe}{downloaded.suffix}"
            n = 1
            while final.exists():
                final = DOWNLOAD_DIR / f"{safe}_{n}{downloaded.suffix}"
                n += 1
            downloaded.rename(final)
            usage["download"] += 1
            return {
                "status": "success", "filename": final.name,
                "download_url": f"/file/{final.name}", "title": title,
                "usage_left": limits["download"] - usage["download"],
            }
    except Exception as e:
        msg = str(e).lower()
        if "sign in" in msg or "not a bot" in msg:
            raise HTTPException(500, "YouTube memblokir server cloud. Coba TikTok/IG/FB.")
        raise HTTPException(500, f"Download gagal: {str(e)[:200]}")

@app.get("/file/{filename}")
def get_file(filename: str):
    if ".." in filename or "/" in filename:
        raise HTTPException(400, "Invalid")
    path = DOWNLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File tidak ditemukan")
    return FileResponse(path, filename=filename)

# ============================================================
# COMIC — MangaDex (API) + Komiku (api.komiku.org + HTML)
# ============================================================
KOMIKU_API = "https://api.komiku.org"
KOMIKU_WEB = "https://komiku.org"
MD_API = "https://api.mangadex.org"
VORATOON_BASE = "https://v10.voratoon.com"
VORATOON_API = "https://api.voratoon.com"
WURMZ_BASE = "https://wurmz.net"
KOMIKINDO_BASE = "https://komikindo.ch"
KEIKOMIK_BASE = "https://keikomik.com"



def _clean_chapter_title(text: str) -> str:
    text = (text or "").strip()
    m = re.search(r"(?:Chapter|Ch\.?|Bab)[\s._-]*(\d+(?:\.\d+)?)", text, flags=re.I)
    if m:
        return f"Chapter {m.group(1)}"
    m = re.search(r"\b(\d+(?:\.\d+)?)\b", text)
    if m and len(text) < 40:
        return f"Chapter {m.group(1)}"
    text = re.sub(r"[\d.,]+[KkMmBb]\b", " ", text)
    text = re.sub(r"\b\d+\s*(jam|hari|bulan|minggu|menit|detik)\s*(lalu)?\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -·|:")
    return text[:80] or "Chapter"


def _komiku_title_from_card(card) -> str:
    h3 = card.find("h3")
    if h3:
        t = h3.get_text(strip=True)
        if t and len(t) > 2:
            return t
    img = card.find("img")
    if img and img.get("alt"):
        return img.get("alt")
    a = card.find("a", href=True)
    if a:
        t = a.get_text(strip=True)
        t = re.sub(r"^(Manga|Manhwa|Manhua|Aksi|Fantasi)+", "", t, flags=re.I).strip()
        if t:
            return t
    return "?"


def _is_komiku_page_image(src: str, img_tag=None) -> bool:
    """True untuk panel chapter Komiku; false untuk iklan/logo."""
    if not src or not str(src).startswith("http"):
        return False
    low = str(src).lower().split("?")[0]
    block = (
        "promosi", "promo-", "-promo", "iklan", "/ads/", "advert", "banner",
        "logo", "icon", "avatar", "emoji", "gravatar", "gstatic", "firebase",
        "spinner", "pixel", "button", "badge", "donate", "donasi",
        "facebook", "twitter", "whatsapp", "telegram", ".svg",
    )
    if any(b in low for b in block):
        return False
    fname = low.rsplit("/", 1)[-1]
    if any(x in fname for x in ("promosi", "promo", "iklan", "ads", "banner", "logo")):
        return False
    # panel: uploads path atau CDN komiku
    if any(x in low for x in ("/uploads/", "/uploads2/", "/upload5/", "img.komiku", "image2.komiku", "cdn.komiku", "komiku.org/upload")):
        if img_tag is not None:
            cls = " ".join(img_tag.get("class") or []).lower()
            if "klazy" in cls or "ww" in cls.split():
                return True
        if re.search(r"(part\d|\d{4,}|chapter)", fname):
            return True
        if fname.endswith((".jpg", ".jpeg", ".png", ".webp")):
            return True
    return False


def _slug_from_href(href: str) -> str:
    href = (href or "").strip().rstrip("/")
    if not href:
        return ""
    # /manga/foo/ -> foo ; /foo-chapter-1/ -> foo-chapter-1
    parts = href.split("/")
    return parts[-1] or (parts[-2] if len(parts) > 1 else "")


def _parse_komiku_cards(html: str, source: str = "komiku"):
    if not HAS_BS4:
        return []
    soup = BeautifulSoup(html, "html.parser")
    items = []
    cards = soup.find_all("div", class_="bge")
    if not cards:
        # home page articles
        for a in soup.select('a[href*="/manga/"]'):
            href = a.get("href") or ""
            if href.count("/") < 2:
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 2:
                continue
            img = a.find("img")
            slug = _slug_from_href(href)
            if not slug or slug in ("manga", "genre"):
                continue
            items.append({
                "title": title,
                "thumb": (img.get("data-src") or img.get("src") or "") if img else "",
                "id": slug,
                "source": source,
                "label": "KOMIK",
            })
        # dedupe
        seen, out = set(), []
        for it in items:
            if it["id"] in seen:
                continue
            seen.add(it["id"])
            out.append(it)
        return out[:30]

    for card in cards[:24]:
        link = card.find("a", href=True)
        if not link:
            continue
        href = link.get("href") or ""
        img = card.find("img")
        title = _komiku_title_from_card(card)
        slug = _slug_from_href(href)
        if "/manga/" in href:
            slug = _slug_from_href(href)
        label = "KOMIK"
        tip = card.find(class_="tpe1_inf")
        if tip and "manhwa" in tip.get_text(strip=True).lower():
            label = "MANHWA"
        items.append({
            "title": title,
            "thumb": (img.get("data-src") or img.get("src") or "") if img else "",
            "id": slug,
            "source": source,
            "label": label,
        })
    return items



@app.get("/comic/genres")
async def comic_genres(source: str = "all"):
    """Daftar genre untuk filter UI."""
    common = [
        "Action", "Adventure", "Comedy", "Drama", "Ecchi", "Fantasy", "Harem",
        "Horror", "Martial Arts", "Mystery", "Romance", "School", "Sci-Fi",
        "Seinen", "Shoujo", "Shounen", "Slice of Life", "Sports", "Supernatural",
        "Tragedy", "Isekai", "Reincarnation", "Murim", "Historical",
    ]
    if source == "wurmz":
        return {"genres": common + ["Yaoi", "Hentai", "18+", "Doujinshi", "Gender Bender", "Mecha", "Psychological"]}
    return {"genres": common}


@app.get("/comic/search")
async def comic_search(request: Request, source: str = "all", q: str = ""):
    items = []
    q = (q or "").strip()
    role = detect_role(request)
    if source in ADMIN_SOURCES and role != "admin":
        raise HTTPException(403, "Source Admin — khusus Admin.")
    if source in PREMIUM_SOURCES and role not in ("premium", "admin"):
        raise HTTPException(403, "Source Premium, Harap Gunakan Premium Untuk Membuka.")

    # 1) MangaDex
    if source == "mangadex":  # tidak prioritas di "all"
        try:
            async with httpx.AsyncClient(timeout=18.0) as client:
                params = {
                    "limit": 20,
                    "includes[]": ["cover_art"],
                    "contentRating[]": ["safe", "suggestive"],
                }
                if q:
                    params["title"] = q
                    params["order[relevance]"] = "desc"
                else:
                    params["order[followedCount]"] = "desc"
                r = await client.get(f"{MD_API}/manga", params=params)
                if r.status_code == 200:
                    for m in r.json().get("data") or []:
                        attrs = m.get("attributes") or {}
                        title = (attrs.get("title") or {}).get("en") or next(
                            iter((attrs.get("title") or {}).values()), "?"
                        )
                        cover = ""
                        for rel in m.get("relationships") or []:
                            if rel.get("type") == "cover_art":
                                fn = (rel.get("attributes") or {}).get("fileName") or ""
                                if fn:
                                    cover = f"https://uploads.mangadex.org/covers/{m['id']}/{fn}.256.jpg"
                        items.append({
                            "title": title, "thumb": cover, "id": m["id"],
                            "source": "mangadex", "label": "MANGADEX",
                        })
        except Exception:
            pass

    # 2) Komiku via api.komiku.org (HTMX fragment with div.bge)
    if source in ("all", "komiku") and HAS_BS4:
        try:
            async with httpx.AsyncClient(timeout=18.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
                if q:
                    url = f"{KOMIKU_API}/?post_type=manga&s={urllib.parse.quote(q)}"
                else:
                    # homepage HTML sering tanpa thumb stabil — pakai API list default
                    url = f"{KOMIKU_API}/?post_type=manga&s="
                r = await client.get(url)
                if r.status_code == 200:
                    parsed = _parse_komiku_cards(r.text, "komiku")
                    # merge without killing mangadex results
                    seen = {(x["title"] or "").lower()[:30] for x in items}
                    for it in parsed:
                        key = (it["title"] or "").lower()[:30]
                        if key not in seen:
                            seen.add(key)
                            items.append(it)
        except Exception:
            pass

        # 3) Voratoon — API resmi api.voratoon.com (pagination + search title)
    if source in ("all", "voratoon"):
        try:
            async with httpx.AsyncClient(timeout=22.0, headers={
                "User-Agent": BROWSER_HEADERS["User-Agent"],
                "Accept": "application/json",
                "Origin": VORATOON_BASE,
                "Referer": VORATOON_BASE + "/",
            }) as client:
                params = {"page": 1, "limit": 30}
                if q:
                    params["title"] = q
                r = await client.get(f"{VORATOON_API}/series", params=params)
                if r.status_code == 200:
                    payload = r.json() or {}
                    for row in (payload.get("data") or [])[:30]:
                        inner = row.get("data") if isinstance(row, dict) else None
                        if not isinstance(inner, dict):
                            continue
                        slug = inner.get("slug") or ""
                        title = inner.get("title") or slug
                        thumb = inner.get("coverImage") or ""
                        if not slug:
                            continue
                        items.append({
                            "title": title[:90],
                            "thumb": thumb,
                            "id": slug,
                            "source": "voratoon",
                            "label": "PROJECT",
                            "chapter": str(inner.get("totalChapters") or ""),
                        })
                # page 2 if no query (lebih banyak judul)
                if not q and r.status_code == 200:
                    r2 = await client.get(f"{VORATOON_API}/series", params={"page": 2, "limit": 30})
                    if r2.status_code == 200:
                        seen = {it["id"] for it in items if it.get("source") == "voratoon"}
                        for row in (r2.json() or {}).get("data") or []:
                            inner = row.get("data") if isinstance(row, dict) else None
                            if not isinstance(inner, dict):
                                continue
                            slug = inner.get("slug") or ""
                            if not slug or slug in seen:
                                continue
                            items.append({
                                "title": (inner.get("title") or slug)[:90],
                                "thumb": inner.get("coverImage") or "",
                                "id": slug,
                                "source": "voratoon",
                                "label": "PROJECT",
                            })
                            if len(seen) + 1 >= 48:
                                break
                            seen.add(slug)
        except Exception:
            pass

    # 3b) Wurmz (Premium) — multi-page ?page=N



    if source == "wurmz" and HAS_BS4:
        # Wurmz = Admin special: ambil sebanyak mungkin (semua-komik + semua genre)
        try:
            async with httpx.AsyncClient(timeout=55.0, follow_redirects=True, headers={**BROWSER_HEADERS, "Referer": WURMZ_BASE + "/"}) as client:
                genre = ""
                q_clean = q
                gm = re.match(r"(?i)^genre:([^\s]+)\s*(.*)$", q or "")
                if gm:
                    genre = gm.group(1).strip()
                    q_clean = (gm.group(2) or "").strip()

                seen_w = set()

                async def _ingest(soup):
                    nodes = soup.select("article") or []
                    if not nodes:
                        for a in soup.select("a[href*='/detail/']"):
                            if "/chapter/" not in (a.get("href") or ""):
                                nodes.append(a)
                    for node in nodes:
                        a = node if getattr(node, "name", "") == "a" else node.select_one("a[href*='/detail/']")
                        if not a:
                            continue
                        href = (a.get("href") or "").strip()
                        if "/detail/" not in href or "/chapter/" in href:
                            continue
                        path = href.split("/detail/")[-1].strip("/")
                        if not path or path in seen_w:
                            continue
                        img = node.select_one("img") if hasattr(node, "select_one") else None
                        if img is None and hasattr(a, "find"):
                            img = a.find("img")
                        thumb = ""
                        if img is not None:
                            thumb = (img.get("data-src") or img.get("src") or "").strip()
                        if thumb.startswith("/"):
                            thumb = WURMZ_BASE + thumb
                        elif thumb and not thumb.startswith("http"):
                            thumb = WURMZ_BASE + "/" + thumb.lstrip("/")
                        title = (a.get("title") or "").strip()
                        if not title:
                            text = node.get_text(" ", strip=True) if hasattr(node, "get_text") else a.get_text(" ", strip=True)
                            text = re.sub(r"^(Manhwa|Manga|Manhua)\s+", "", text or "", flags=re.I)
                            text = re.sub(r"\s*Ch\.?\s*[\d.]+.*$", "", text, flags=re.I)
                            text = re.sub(r"\s*\d+\s*(jam|menit|hari|minggu).*", "", text, flags=re.I).strip()
                            title = text or path.split("/")[-1].replace("-", " ")
                        if q_clean and q_clean.lower() not in title.lower() and q_clean.lower() not in path.lower():
                            continue
                        seen_w.add(path)
                        items.append({
                            "title": title[:90],
                            "thumb": thumb,
                            "id": path,
                            "source": "wurmz",
                            "label": "ADMIN",
                        })

                # 1) Filter genre spesifik dari UI
                if genre:
                    for page in range(1, 31):
                        url = f"{WURMZ_BASE}/semua-komik?q={urllib.parse.quote(q_clean)}&type=&status=&genres%5B%5D={urllib.parse.quote(genre)}&sort=new"
                        if page > 1:
                            url += f"&page={page}"
                        r = await client.get(url)
                        if r.status_code != 200:
                            break
                        before = len(seen_w)
                        await _ingest(BeautifulSoup(r.text, "html.parser"))
                        if len(seen_w) == before:
                            break
                        if len(seen_w) >= 800:
                            break
                # 2) Search teks
                elif q_clean:
                    for page in range(1, 12):
                        url = f"{WURMZ_BASE}/?s={urllib.parse.quote(q_clean)}"
                        if page > 1:
                            url = f"{WURMZ_BASE}/page/{page}/?s={urllib.parse.quote(q_clean)}"
                        r = await client.get(url)
                        if r.status_code != 200:
                            break
                        before = len(seen_w)
                        await _ingest(BeautifulSoup(r.text, "html.parser"))
                        if len(seen_w) == before:
                            break
                # 3) FULL DUMP admin: semua-komik page 1..50 + semua genre
                else:
                    for page in range(1, 51):
                        url = f"{WURMZ_BASE}/semua-komik" if page == 1 else f"{WURMZ_BASE}/semua-komik?page={page}"
                        r = await client.get(url)
                        if r.status_code != 200:
                            break
                        before = len(seen_w)
                        await _ingest(BeautifulSoup(r.text, "html.parser"))
                        if len(seen_w) == before and page > 2:
                            break
                        if len(seen_w) >= 1200:
                            break
                    # tambah per-genre (isi niche yang tidak di "semua")
                    for gname in ['Action', 'Adventure', 'Comedy', 'Drama', 'Ecchi', 'Fantasy', 'Harem', 'Horror', 'Martial Arts', 'Mystery', 'Romance', 'School', 'Sci-Fi', 'Seinen', 'Shoujo', 'Shounen', 'Slice of Life', 'Sports', 'Supernatural', 'Tragedy', 'Isekai', 'Reincarnation', 'Murim', 'Historical', 'Yaoi', 'Hentai', '18+', 'Doujinshi', 'Gender Bender', 'Mecha', 'Psychological', 'Thriller', 'Josei', 'Adult']:
                        if len(seen_w) >= 1500:
                            break
                        for page in range(1, 8):
                            gu = f"{WURMZ_BASE}/semua-komik?q=&type=&status=&genres%5B%5D={urllib.parse.quote(gname)}&sort=new"
                            if page > 1:
                                gu += f"&page={page}"
                            try:
                                r = await client.get(gu)
                                if r.status_code != 200:
                                    break
                                before = len(seen_w)
                                await _ingest(BeautifulSoup(r.text, "html.parser"))
                                if len(seen_w) == before:
                                    break
                            except Exception:
                                break
        except Exception:
            pass


    if source in ("all", "komikindo") and HAS_BS4:
        try:
            async with httpx.AsyncClient(timeout=22.0, follow_redirects=True, headers={**BROWSER_HEADERS, "Referer": KOMIKINDO_BASE + "/"}) as client:
                url = f"{KOMIKINDO_BASE}/?s={urllib.parse.quote(q)}" if q else f"{KOMIKINDO_BASE}/"
                r = await client.get(url)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    posts = soup.select(".animepost") or soup.select(".bsx") or []
                    for post in posts[:30]:
                        a = post.select_one("a[href*='/komik/']") or post.select_one("a[href*='/manga/']")
                        if not a:
                            continue
                        href = a.get("href") or ""
                        title = a.get("title") or a.get_text(strip=True) or "?"
                        # skip category links
                        if href.rstrip("/").endswith("/komik") or href.rstrip("/").endswith("/manga"):
                            continue
                        img = post.select_one("img")
                        thumb = ""
                        if img:
                            thumb = img.get("data-src") or img.get("src") or ""
                        slug = href.rstrip("/").split("/")[-1]
                        if not slug or len(slug) < 2:
                            continue
                        items.append({
                            "title": title[:90],
                            "thumb": thumb,
                            "id": slug,
                            "source": "komikindo",
                            "label": "PREMIUM",
                        })
        except Exception:
            pass



    # KeiKomik (gratis)
    if source in ("all", "keikomik") and HAS_BS4:
        try:
            async with httpx.AsyncClient(timeout=22.0, follow_redirects=True, headers={**BROWSER_HEADERS, "Referer": KEIKOMIK_BASE + "/"}) as client:
                r = await client.get(KEIKOMIK_BASE + "/")
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    seen_k = set()
                    for art in soup.select("article"):
                        a = art.select_one("a[href*='/komik/']")
                        if not a:
                            continue
                        href = (a.get("href") or "").strip()
                        if "chapter" in href.lower():
                            continue
                        if not re.search(r"/komik/[^/]+/?$", href):
                            continue
                        slug = href.rstrip("/").split("/")[-1]
                        if not slug or slug in seen_k:
                            continue
                        img = art.select_one("img")
                        title_k = ""
                        thumb = ""
                        if img:
                            alt = (img.get("alt") or "").strip()
                            if alt.lower().startswith("poster"):
                                title_k = re.sub(r"^poster\s*(trending)?\s*:?\s*", "", alt, flags=re.I).strip()
                            else:
                                title_k = alt
                            thumb = img.get("src") or img.get("data-src") or ""
                        if not title_k:
                            text = art.get_text(" ", strip=True)
                            text = re.sub(r"^#?\d+(\.\d+)?k?\s*", "", text)
                            text = re.sub(r"\s*Ch\.?\s*\d+.*$", "", text, flags=re.I)
                            text = re.sub(r"\s*(Manga|Manhwa|Manhua)\s*$", "", text, flags=re.I).strip()
                            title_k = text or slug.replace("-", " ").title()
                        if q and q.lower() not in title_k.lower() and q.lower() not in slug.lower():
                            continue
                        seen_k.add(slug)
                        items.append({
                            "title": title_k[:90],
                            "thumb": thumb,
                            "id": slug,
                            "source": "keikomik",
                            "label": "KOMIK",
                        })
        except Exception:
            pass

    # final dedupe
    seen2, unique = set(), []
    for it in items:
        key = ((it.get("title") or "").lower()[:40], it.get("source"), it.get("id"))
        if key in seen2:
            continue
        seen2.add(key)
        unique.append(it)
    limit = 200 if source == "wurmz" else 48
    return {"items": unique[:limit]}



@app.get("/comic/detail")
async def comic_detail(request: Request, source: str = "komiku", id: str = "", lang: str = "all"):
    if not id:
        raise HTTPException(400, "id kosong")
    role = detect_role(request)
    if source in ADMIN_SOURCES and role != "admin":
        raise HTTPException(403, "Source Admin — khusus Admin.")
    if source in PREMIUM_SOURCES and role not in ("premium", "admin"):
        raise HTTPException(403, "Source Premium, Harap Gunakan Premium Untuk Membuka.")
    chapters, title, synopsis, thumb, genres = [], id, "", "", []

    # ---- MangaDex ----
    if source == "mangadex":
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                r = await client.get(f"{MD_API}/manga/{id}", params={"includes[]": ["cover_art", "author"]})
                if r.status_code == 200:
                    m = (r.json() or {}).get("data") or {}
                    attrs = m.get("attributes") or {}
                    title = (attrs.get("title") or {}).get("en") or next(iter((attrs.get("title") or {}).values()), id)
                    desc = attrs.get("description") or {}
                    if isinstance(desc, dict):
                        synopsis = (desc.get("en") or desc.get("id") or next(iter(desc.values()), ""))[:1200]
                    for rel in m.get("relationships") or []:
                        if rel.get("type") == "cover_art":
                            fn = (rel.get("attributes") or {}).get("fileName") or ""
                            if fn:
                                thumb = f"https://uploads.mangadex.org/covers/{id}/{fn}.256.jpg"
                    for g in (attrs.get("tags") or [])[:8]:
                        n = ((g.get("attributes") or {}).get("name") or {}).get("en")
                        if n:
                            genres.append(n)
                offset = 0
                lang = (lang or "all").lower().strip()
                while offset < 500:
                    feed_params = [
                        ("limit", 100), ("offset", offset),
                        ("order[chapter]", "desc"), ("includeEmptyPages", "0"),
                        ("contentRating[]", "safe"), ("contentRating[]", "suggestive"), ("contentRating[]", "erotica"),
                    ]
                    if lang in ("id", "indonesia", "ind"):
                        feed_params.append(("translatedLanguage[]", "id"))
                    elif lang in ("en", "eng", "english"):
                        feed_params.append(("translatedLanguage[]", "en"))
                    else:
                        feed_params.append(("translatedLanguage[]", "id"))
                        feed_params.append(("translatedLanguage[]", "en"))
                    rf = await client.get(f"{MD_API}/manga/{id}/feed", params=feed_params)
                    batch = (rf.json() or {}).get("data") or []
                    if not batch:
                        break
                    for ch in batch:
                        a = ch.get("attributes") or {}
                        num = a.get("chapter") or "?"
                        lang_ch = (a.get("translatedLanguage") or "").upper()
                        extra = a.get("title") or ""
                        label = f"Chapter {num}"
                        if extra:
                            label += f" — {extra}"
                        if lang_ch:
                            label += f" [{lang_ch}]"
                        chapters.append({"title": label[:100], "id": ch["id"], "lang": a.get("translatedLanguage") or ""})
                    offset += 100
                    if len(batch) < 100:
                        break
                if not chapters and lang not in ("all", "", "any"):
                    offset = 0
                    while offset < 300:
                        rf = await client.get(f"{MD_API}/manga/{id}/feed", params=[
                            ("limit", 100), ("offset", offset), ("order[chapter]", "desc"), ("includeEmptyPages", "0"),
                            ("contentRating[]", "safe"), ("contentRating[]", "suggestive"), ("contentRating[]", "erotica"),
                        ])
                        batch = (rf.json() or {}).get("data") or []
                        if not batch:
                            break
                        for ch in batch:
                            a = ch.get("attributes") or {}
                            num = a.get("chapter") or "?"
                            lang_ch = (a.get("translatedLanguage") or "").upper()
                            label = f"Chapter {num}" + (f" [{lang_ch}]" if lang_ch else "")
                            chapters.append({"title": label[:100], "id": ch["id"], "lang": a.get("translatedLanguage") or ""})
                        offset += 100
                        if len(batch) < 100:
                            break
        except Exception as e:
            raise HTTPException(502, f"MangaDex detail: {e}")
        return {"title": title, "chapters": chapters[:2500], "synopsis": synopsis, "thumb": thumb, "genres": genres}

    # ---- KeiKomik ----
    if source == "keikomik" and HAS_BS4:
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers={**BROWSER_HEADERS, "Referer": KEIKOMIK_BASE + "/"}) as client:
                slug = id.strip("/")
                r = await client.get(f"{KEIKOMIK_BASE}/komik/{slug}/")
                if r.status_code != 200:
                    raise HTTPException(404, f"KeiKomik tidak ditemukan ({r.status_code})")
                soup = BeautifulSoup(r.text, "html.parser")
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(" ", strip=True)
                img = soup.select_one("img[alt*='Poster'], img[alt*='poster'], main img, img")
                if img:
                    thumb = img.get("src") or img.get("data-src") or ""
                for p_el in soup.select("p"):
                    t = p_el.get_text(" ", strip=True)
                    if len(t) > 60:
                        synopsis = t[:1200]
                        break
                seen = set()
                for a in soup.find_all("a", href=True):
                    href = (a.get("href") or "").strip()
                    if not re.search(rf"/komik/{re.escape(slug)}/chapter-[\d.]+", href):
                        continue
                    m = re.search(r"chapter-([\d.]+)", href, re.I)
                    num = m.group(1) if m else ""
                    path = href
                    if href.startswith("http"):
                        path = href.split(KEIKOMIK_BASE)[-1] if KEIKOMIK_BASE in href else href
                    ch_id = path.strip("/")
                    if not ch_id or ch_id in seen:
                        continue
                    seen.add(ch_id)
                    label = a.get_text(" ", strip=True) or f"Chapter {num}"
                    if "mulai baca" in label.lower() or "terbaru" in label.lower() or not label.strip():
                        label = f"Chapter {num}" if num else ch_id
                    chapters.append({"title": label[:80], "id": ch_id})
                def _ck(c):
                    m = re.search(r"chapter-([\d.]+)", c["id"], re.I)
                    try:
                        return float(m.group(1)) if m else 0.0
                    except Exception:
                        return 0.0
                chapters.sort(key=_ck, reverse=True)
                return {"title": title, "chapters": chapters[:2500], "synopsis": synopsis, "thumb": thumb, "genres": genres}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"KeiKomik detail: {e}")


    # ---- Komiku (daftar chapter lengkap dari #Daftar_Chapter) ----
    if source == "komiku" and HAS_BS4:
        try:
            async with httpx.AsyncClient(timeout=28.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
                slug = id.strip("/")
                r = await client.get(f"{KOMIKU_WEB}/manga/{slug}/")
                if r.status_code != 200:
                    raise HTTPException(404, f"Komiku tidak ditemukan ({r.status_code})")
                soup = BeautifulSoup(r.text, "html.parser")
                h1 = soup.find("h1")
                if h1:
                    title = h1.get_text(" ", strip=True).replace("Komik ", "", 1)
                img = soup.select_one(".ims img, .thumb img, img[itemprop='image'], .gambar img")
                if img:
                    thumb = img.get("data-src") or img.get("src") or ""
                desc = soup.select_one("#Sinopsis, .desc, [itemprop='description']")
                if desc:
                    synopsis = desc.get_text(" ", strip=True)[:1200]
                seen = set()
                box = soup.select_one("#Daftar_Chapter, #Chapter, .daftar-chapter")
                anchors = box.select("a[href]") if box else []
                if not anchors:
                    anchors = soup.find_all("a", href=True)
                for a in anchors:
                    href = (a.get("href") or "").strip()
                    text = a.get_text(" ", strip=True)
                    low = href.lower()
                    if not href:
                        continue
                    if "chapter" not in low and not re.search(r"ch-?\d", low):
                        continue
                    # skip non-series
                    if slug and slug not in low and not re.search(rf"{re.escape(slug)}[-_/]", low):
                        # still allow path like /slug-chapter-1/
                        if not re.search(r"chapter[-_/]?\d", low):
                            continue
                    ch_id = _slug_from_href(href)
                    if not ch_id or ch_id in seen or len(ch_id) < 3:
                        continue
                    seen.add(ch_id)
                    label = _clean_chapter_title(text) if text else ch_id
                    chapters.append({"title": label[:80], "id": ch_id})
                # sort newest first if numbers found
                def _k(c):
                    m = re.search(r"chapter[-_]?(\d+(?:\.\d+)?)", c["id"], re.I) or re.search(r"(\d+(?:\.\d+)?)", c["title"])
                    try:
                        return float(m.group(1)) if m else 0
                    except Exception:
                        return 0
                chapters.sort(key=_k, reverse=True)
                return {"title": title, "chapters": chapters[:2500], "synopsis": synopsis, "thumb": thumb, "genres": genres}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Komiku detail: {e}")

    # ---- HTML sources: komikindo, voratoon, wurmz ----

    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            if source == "komikindo":
                url = f"{KOMIKINDO_BASE}/komik/{id}/"
            elif source == "voratoon":
                try:
                    async with httpx.AsyncClient(timeout=22.0, headers={
                        "User-Agent": BROWSER_HEADERS["User-Agent"],
                        "Accept": "application/json",
                        "Origin": VORATOON_BASE,
                        "Referer": VORATOON_BASE + "/",
                    }) as apiclient:
                        rd = await apiclient.get(f"{VORATOON_API}/series/{id}")
                        if rd.status_code == 200:
                            row = (rd.json() or {}).get("data") or {}
                            inner = row.get("data") if isinstance(row, dict) else {}
                            if isinstance(inner, dict):
                                title = inner.get("title") or title
                                synopsis = inner.get("synopsis") or ""
                                thumb = inner.get("coverImage") or ""
                        rc = await apiclient.get(f"{VORATOON_API}/series/{id}/chapters")
                        if rc.status_code == 200:
                            rows = (rc.json() or {}).get("data") or []
                            for ch in rows:
                                cdata = ch.get("data") if isinstance(ch.get("data"), dict) else {}
                                num = cdata.get("index") or cdata.get("number") or cdata.get("chapter") or ch.get("id")
                                ctitle = (cdata.get("title") or "") if isinstance(cdata, dict) else ""
                                ch_id = f"{id}/chapter/{num}"
                                chapters.append({
                                    "title": _clean_chapter_title(f"Chapter {num} {ctitle}"),
                                    "id": ch_id,
                                })
                    if chapters:
                        return {"title": title, "chapters": chapters[:2500], "synopsis": synopsis, "thumb": thumb, "genres": genres}
                except Exception:
                    chapters = []
                url = f"{VORATOON_BASE}/series/{id}"
            elif source == "wurmz":
                url = f"{WURMZ_BASE}/detail/{id}"
            else:
                url = f"{KOMIKU_WEB}/manga/{id}/"

            r = await client.get(url)
            if r.status_code != 200:
                raise HTTPException(404, f"Komik tidak ditemukan ({r.status_code})")
            if not HAS_BS4:
                raise HTTPException(500, "BeautifulSoup tidak tersedia")
            soup = BeautifulSoup(r.text, "html.parser")
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(" ", strip=True).replace("Komik ", "", 1)
            img = soup.select_one(".ims img, .thumb img, .info-image img, img[itemprop='image']")
            if img:
                thumb = img.get("data-src") or img.get("src") or ""
            desc = soup.select_one("#Sinopsis, .desc, .entry-content, .summary__content, [itemprop='description']")
            if desc:
                synopsis = desc.get_text(" ", strip=True)[:1200]
            seen_ch = set()
            series_key = (id or "").split("/")[-1].lower()
            for a in soup.find_all("a", href=True):
                href = (a.get("href") or "").strip()
                text = a.get_text(" ", strip=True)
                if not href:
                    continue
                low = href.lower()
                is_ch = (
                    "/chapter/" in low
                    or bool(re.search(r"chapter[-_/]?\d", low))
                    or bool(re.search(r"-chapter-\d", low))
                    or bool(re.search(r"(?:chapter|ch\.?|bab)\s*\d", (text or "").lower()))
                )
                if not is_ch:
                    continue
                if source == "voratoon" and "/chapter/" in low:
                    if series_key and series_key not in low:
                        continue
                    parts = href.split("/series/")[-1].strip("/")
                    if "/chapter/" not in parts:
                        continue
                    ch_id = parts
                elif source == "wurmz" and "/detail/" in low and "/chapter/" in low:
                    if series_key and series_key not in low:
                        continue
                    ch_id = href.split("/detail/")[-1].strip("/")
                elif source == "komiku":
                    ch_id = _slug_from_href(href)
                    if "chapter" not in ch_id.lower() and not re.search(r"ch-?\d", ch_id.lower()):
                        continue
                else:
                    ch_id = _slug_from_href(href)
                title_ch = _clean_chapter_title(text) if text else (ch_id[:40] if ch_id else "Chapter")
                if not ch_id or ch_id == id or ch_id in seen_ch or len(ch_id) < 3:
                    continue
                seen_ch.add(ch_id)
                chapters.append({"title": title_ch, "id": ch_id})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Detail error: {e}")
    return {"title": title, "chapters": chapters[:2500], "synopsis": synopsis, "thumb": thumb, "genres": genres}


@app.get("/comic/chapter")
async def comic_chapter(request: Request, source: str = "komiku", id: str = ""):
    if not id:
        raise HTTPException(400, "id kosong")
    role = detect_role(request)
    if source in ADMIN_SOURCES and role != "admin":
        raise HTTPException(403, "Source Admin — khusus Admin.")
    if source in PREMIUM_SOURCES and role not in ("premium", "admin"):
        raise HTTPException(403, "Source Premium, Harap Gunakan Premium Untuk Membuka.")
    images = []

    if source == "mangadex":
        try:
            async with httpx.AsyncClient(timeout=35.0, follow_redirects=True, headers={
                "User-Agent": BROWSER_HEADERS["User-Agent"],
                "Referer": "https://mangadex.org/",
            }) as client:
                r = await client.get(f"{MD_API}/at-home/server/{id}")
                if r.status_code != 200:
                    r = await client.get(f"{MD_API}/at-home/server/{id}")
                if r.status_code != 200:
                    raise HTTPException(502, f"MangaDex at-home {r.status_code}")
                data = r.json() or {}
                base = (data.get("baseUrl") or "").rstrip("/")
                ch = data.get("chapter") or {}
                hash_ = ch.get("hash") or ""
                full = ch.get("data") or []
                saver = ch.get("dataSaver") or []
                if full and hash_ and base:
                    images = [f"{base}/data/{hash_}/{p}" for p in full]
                elif saver and hash_ and base:
                    images = [f"{base}/data-saver/{hash_}/{p}" for p in saver]
                images = [u for u in images if u.startswith("http")]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"MangaDex chapter: {e}")
        if not images:
            raise HTTPException(404, "Halaman MangaDex kosong. Coba chapter/bahasa lain.")
        return {"images": images, "count": len(images)}

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers={**BROWSER_HEADERS, "Referer": KEIKOMIK_BASE + "/"}) as client:
            if source == "keikomik":
                if id.startswith("http"):
                    url = id
                elif id.startswith("komik/"):
                    url = f"{KEIKOMIK_BASE}/{id.strip('/')}/"
                else:
                    url = f"{KEIKOMIK_BASE}/{id.strip('/')}/"
            elif source == "komikindo":
                if id.startswith("http"):
                    url = id
                elif "chapter" in id:
                    url = id if id.startswith("http") else f"{KOMIKINDO_BASE}/{id.strip('/')}/"
                else:
                    url = f"{KOMIKINDO_BASE}/{id.strip('/')}/"
            elif source == "voratoon":
                if id.startswith("http"):
                    url = id
                elif "/chapter/" in id:
                    url = f"{VORATOON_BASE}/series/{id}" if not id.startswith("series/") else f"{VORATOON_BASE}/{id}"
                else:
                    url = f"{VORATOON_BASE}/series/{id}"
            elif source == "wurmz":
                if id.startswith("http"):
                    url = id
                elif id.startswith("detail/"):
                    url = f"{WURMZ_BASE}/{id}"
                else:
                    url = f"{WURMZ_BASE}/detail/{id}"
            elif source == "komiku":
                url = id if id.startswith("http") else f"{KOMIKU_WEB}/{id}/"
            else:
                url = id if id.startswith("http") else f"{KOMIKU_WEB}/{id}/"

            r = await client.get(url)
            if r.status_code != 200:
                raise HTTPException(404, f"Chapter tidak ditemukan ({r.status_code})")
            if not HAS_BS4:
                raise HTTPException(500, "BeautifulSoup tidak tersedia")
            soup = BeautifulSoup(r.text, "html.parser")
            # prioritas selector reader
            candidates = soup.select("#Baca_Komik img, #Content img, #readerarea img, .reader-area img, #chimg img, .chapter-image img, img.klazy, img.ww, main img, .entry-content img, img")
            for img in candidates:
                src_img = (img.get("data-src") or img.get("data-lazy-src") or img.get("src") or "").strip()
                if src_img.startswith("//"):
                    src_img = "https:" + src_img
                if not src_img.startswith("http"):
                    continue
                low = src_img.lower()
                if any(x in low for x in ["logo", "avatar", "icon", "emoji", "favicon", "promosi", "promo.webp", "gravatar", "gstatic", "firebase", "pixel"]):
                    continue
                if source == "komiku":
                    if not _is_komiku_page_image(src_img, img):
                        continue
                else:
                    if not any(x in low for x in ["upload", "cdn", "imgkomik", "manhwature", "wp-content", "storage", "blogspot", "covers/", ".jpg", ".jpeg", ".png", ".webp"]):
                        continue
                if src_img not in images:
                    images.append(src_img)
            # fallback: semua data-src jpg di halaman komiku
            if source == "komiku" and len(images) < 2:
                for img in soup.find_all("img"):
                    src_img = (img.get("data-src") or img.get("src") or "").strip()
                    if "uploads" in src_img and src_img.startswith("http") and src_img not in images:
                        if "promosi" not in src_img.lower():
                            images.append(src_img)
            # fallback regex for keikomik CDN
            if source == "keikomik" and len(images) < 3:
                for m in re.findall(r'https?://[^"\'\s]+(?:imgkomik|manhwature|cdn\.ikiru)[^"\'\s]+\.(?:jpg|jpeg|png|webp)', r.text, re.I):
                    if m not in images:
                        images.append(m)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Chapter error: {e}")
    if not images:
        raise HTTPException(404, "Gambar chapter tidak ditemukan")
    return {"images": images, "count": len(images)}


# ============================================================
# ANIME — Jikan (stabil metadata) + best-effort HTML scrape
# ============================================================
@app.get("/anime/search")
async def anime_search(source: str = "all", q: str = ""):
    items = []
    q = (q or "").strip()

    # Jikan (MyAnimeList metadata — stabil, bukan stream)
    if source in ("all", "otakudesu", "jikan"):
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                if q:
                    r = await client.get("https://api.jikan.moe/v4/anime", params={"q": q, "limit": 20})
                else:
                    r = await client.get("https://api.jikan.moe/v4/seasons/now", params={"limit": 20})
                if r.status_code == 200:
                    data = r.json().get("data") or []
                    for a in data:
                        items.append({
                            "title": a.get("title") or a.get("title_english") or "?",
                            "thumb": (a.get("images") or {}).get("jpg", {}).get("image_url") or "",
                            "id": str(a.get("mal_id") or ""),
                            "source": "jikan",
                            "url": a.get("url") or "",
                            "episodes": a.get("episodes"),
                            "score": a.get("score"),
                        })
        except Exception:
            pass

    # Best-effort Anoboy HTML
    if source in ("all", "anoboy") and HAS_BS4 and len(items) < 5:
        try:
            async with httpx.AsyncClient(timeout=18.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
                url = f"https://anoboy.ch/?s={urllib.parse.quote(q)}" if q else "https://anoboy.ch/"
                r = await client.get(url)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        title = a.get_text(strip=True)
                        if not title or len(title) < 4:
                            continue
                        if "anoboy" not in href and not href.startswith("/"):
                            continue
                        img = a.find("img")
                        if not img:
                            continue
                        slug = href.rstrip("/").split("/")[-1]
                        items.append({
                            "title": title[:80],
                            "thumb": img.get("data-src") or img.get("src") or "",
                            "id": slug,
                            "source": "anoboy",
                        })
                        if len([x for x in items if x["source"] == "anoboy"]) >= 15:
                            break
        except Exception:
            pass

    seen, unique = set(), []
    for it in items:
        key = (it.get("title") or "").lower()[:40]
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)
    if not unique:
        return {"items": [], "hint": "Source anime sedang sibuk. Coba kata kunci lain atau nanti lagi."}
    return {"items": unique[:24]}


@app.get("/anime/detail")
async def anime_detail(source: str = "jikan", id: str = ""):
    if not id:
        raise HTTPException(400, "id kosong")
    title, synopsis, thumb, episodes, genres = id, "", "", [], []

    if source == "jikan" or id.isdigit():
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.get(f"https://api.jikan.moe/v4/anime/{id}/full")
                if r.status_code != 200:
                    r = await client.get(f"https://api.jikan.moe/v4/anime/{id}")
                if r.status_code == 200:
                    a = (r.json() or {}).get("data") or {}
                    title = a.get("title") or title
                    synopsis = a.get("synopsis") or ""
                    thumb = (a.get("images") or {}).get("jpg", {}).get("large_image_url") or ""
                    genres = [g.get("name") for g in (a.get("genres") or [])]
                    # episode list metadata only
                    ep_count = a.get("episodes") or 0
                    mal = a.get("url") or f"https://myanimelist.net/anime/{id}"
                    for i in range(1, min(int(ep_count or 0), 50) + 1):
                        episodes.append({"title": f"Episode {i}", "id": str(i), "external": mal})
                    if not episodes:
                        episodes.append({"title": "Buka di MyAnimeList", "id": "mal", "external": mal})
                    return {
                        "title": title, "synopsis": synopsis, "thumb": thumb,
                        "episodes": episodes, "genres": genres,
                        "note": "Jikan = metadata. Streaming full butuh sumber terpisah / VPS.",
                    }
        except Exception as e:
            raise HTTPException(502, str(e))

    # HTML fallback anoboy-style
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            url = f"https://anoboy.ch/{id}" if source == "anoboy" else f"https://otakudesu.cloud/anime/{id}"
            r = await client.get(url)
            if r.status_code != 200 or not HAS_BS4:
                raise HTTPException(404, "Detail anime tidak ditemukan")
            soup = BeautifulSoup(r.text, "html.parser")
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
            for a in soup.find_all("a", href=True):
                t = a.get_text(strip=True)
                if t.lower().startswith("episode") or "eps" in t.lower():
                    episodes.append({"title": t, "id": a["href"].rstrip("/").split("/")[-1]})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"title": title, "synopsis": synopsis, "thumb": thumb, "episodes": episodes[:100], "genres": genres}


@app.get("/anime/episode")
async def anime_episode(source: str = "jikan", id: str = ""):
    """Stream sering diblok di cloud. Kembalikan link eksternal jika ada."""
    if source == "jikan" or id == "mal":
        return {
            "stream_url": "",
            "embed": "",
            "message": "Metadata Jikan tidak menyediakan stream. Buka link MyAnimeList / situs favoritmu.",
        }
    stream = ""
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            url = id if str(id).startswith("http") else f"https://anoboy.ch/{id}"
            r = await client.get(url)
            if r.status_code == 200 and HAS_BS4:
                soup = BeautifulSoup(r.text, "html.parser")
                iframe = soup.find("iframe")
                if iframe and iframe.get("src"):
                    stream = iframe["src"]
                if not stream:
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if any(x in href for x in ["mp4", "m3u8", "player", "embed"]):
                            stream = href
                            break
    except Exception as e:
        raise HTTPException(502, str(e))
    if not stream:
        raise HTTPException(404, "Link stream tidak ditemukan (sering diblok di server cloud)")
    return {"stream_url": stream, "embed": stream}


# ============================================================
# NOVEL
# ============================================================
@app.get("/novel/search")
async def novel_search(q: str = "", source: str = "wbnovel"):
    """WB Novel (wbnovel.com) — web novel Indo."""
    items = []
    q = (q or "").strip()
    if not HAS_BS4:
        return {"items": [], "hint": "BeautifulSoup tidak tersedia"}
    try:
        async with httpx.AsyncClient(timeout=22.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            if q:
                url = f"https://wbnovel.com/?s={urllib.parse.quote(q)}&post_type=wp-manga"
            else:
                url = "https://wbnovel.com/"
            r = await client.get(url)
            if r.status_code != 200:
                return {"items": [], "hint": f"WB Novel HTTP {r.status_code}"}
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select(".c-tabs-item__content")
            if not cards:
                # homepage widgets
                for a in soup.select("a[href*='/nv/']")[:40]:
                    href = a.get("href") or ""
                    if "/chapter-" in href:
                        continue
                    title = a.get("title") or a.get_text(strip=True)
                    if not title or len(title) < 3:
                        continue
                    img = a.find("img")
                    slug = href.rstrip("/").split("/")[-1]
                    items.append({
                        "title": title[:90],
                        "thumb": (img.get("data-src") or img.get("src") or "") if img else "",
                        "id": slug,
                        "source": "wbnovel",
                    })
            else:
                for box in cards[:30]:
                    a = box.select_one(".post-title a, h3 a, h4 a, .tab-thumb a, a[href*='/nv/']")
                    if not a:
                        continue
                    href = a.get("href") or ""
                    title = a.get("title") or a.get_text(strip=True) or "?"
                    img = box.select_one("img")
                    slug = href.rstrip("/").split("/")[-1]
                    if not slug:
                        continue
                    items.append({
                        "title": title[:90],
                        "thumb": (img.get("data-src") or img.get("src") or "") if img else "",
                        "id": slug,
                        "source": "wbnovel",
                    })
            # dedupe
            seen, out = set(), []
            for it in items:
                if it["id"] in seen:
                    continue
                seen.add(it["id"])
                out.append(it)
            items = out
    except Exception as e:
        return {"items": [], "hint": str(e)[:120]}
    if not items:
        return {"items": [], "hint": "Tidak ada hasil. Coba kata kunci lain."}
    return {"items": items[:24]}


@app.get("/novel/detail")
async def novel_detail(id: str = "", source: str = "wbnovel"):
    if not id:
        raise HTTPException(400, "id kosong")
    title, synopsis, thumb, chapters = id, "", "", []
    url = id if id.startswith("http") else f"https://wbnovel.com/nv/{id}/"
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            r = await client.get(url)
            if r.status_code != 200 or not HAS_BS4:
                raise HTTPException(404, "Novel tidak ditemukan")
            soup = BeautifulSoup(r.text, "html.parser")
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
            img = soup.select_one(".summary_image img, .tab-summary img, img.img-responsive")
            if img:
                thumb = img.get("data-src") or img.get("src") or ""
            desc = soup.select_one(".description-summary, .summary__content, .manga-excerpt, [itemprop='description']")
            if desc:
                synopsis = desc.get_text(" ", strip=True)[:1500]
            seen = set()
            for a in soup.select(".wp-manga-chapter a, .listing-chapters_wrap a, li.wp-manga-chapter a, .version-chap a"):
                href = a.get("href") or ""
                text = a.get_text(strip=True)
                if not href or not text:
                    continue
                ch_id = href.rstrip("/").split("/")[-1]
                if not ch_id or ch_id in seen:
                    continue
                seen.add(ch_id)
                chapters.append({"title": text[:80], "id": href, "url": href})
            if not chapters:
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "/chapter-" in href or re.search(r"chapter-\d", href):
                        text = a.get_text(strip=True) or href
                        ch_id = href.rstrip("/").split("/")[-1]
                        if ch_id not in seen:
                            seen.add(ch_id)
                            chapters.append({"title": text[:80], "id": ch_id, "url": href})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, str(e))
    return {"title": title, "chapters": chapters[:2500], "synopsis": synopsis, "thumb": thumb}


@app.get("/novel/chapter")
async def novel_chapter(id: str = "", source: str = "wbnovel", novel: str = ""):
    """id = full path e.g. nv/slug/chapter-1 atau URL; novel = series slug."""
    if not id:
        raise HTTPException(400, "id kosong")
    id = id.strip().strip("/")
    if id.startswith("http"):
        url = id
    elif id.startswith("nv/"):
        url = f"https://wbnovel.com/{id}/"
    elif novel:
        ch = id if id.startswith("chapter") else f"chapter-{id}"
        url = f"https://wbnovel.com/nv/{novel.strip('/')}/{ch}/"
    elif "/" in id:
        url = f"https://wbnovel.com/{id}/"
    else:
        url = f"https://wbnovel.com/nv/{id}/"
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            r = await client.get(url)
            if r.status_code != 200:
                # fallback: try without trailing patterns
                r = await client.get(url.rstrip("/") + "/")
            if r.status_code != 200 or not HAS_BS4:
                raise HTTPException(404, f"Chapter tidak ditemukan ({r.status_code})")
            soup = BeautifulSoup(r.text, "html.parser")
            body = None
            for sel in [
                ".reading-content .text-left",
                ".reading-content",
                ".text-left",
                ".entry-content .text-left",
                ".entry-content",
                ".c-blog-post .entry-content",
                "article .entry-content",
            ]:
                body = soup.select_one(sel)
                if body and len(body.get_text(strip=True)) > 100:
                    break
            text = body.get_text("\n", strip=True) if body else ""
            # bersihkan navigasi pendek di awal/akhir
            lines = [ln for ln in text.split("\n") if ln.strip()]
            # drop pure nav lines
            cleaned = []
            for ln in lines:
                low = ln.lower().strip()
                if low in ("home", "next", "prev", "previous", "next chapter", "prev chapter"):
                    continue
                if re.match(r"^(chapter\s*)?\d+$", low):
                    continue
                cleaned.append(ln)
            text = "\n".join(cleaned)
            if len(text) < 80:
                raise HTTPException(404, "Teks chapter kosong — coba chapter lain")
            h = soup.find("h1") or soup.find("h2")
            title = h.get_text(strip=True) if h else id
            return {"content": text[:80000], "title": title}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Novel chapter: {e}")


@app.get("/movie/search")
async def movie_search(q: str = "", type: str = "movie"):
    items = []
    mirrors = ["https://tv1.nontondrama.click", "https://layarkaca21.net", "https://www.lk21official.co"]
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            for mirror in mirrors:
                try:
                    if type == "drama":
                        url = f"{mirror}/?s={q}" if q else f"{mirror}/drama/"
                    else:
                        url = f"{mirror}/?s={q}" if q else f"{mirror}/"
                    r = await client.get(url)
                    if r.status_code != 200 or not HAS_BS4:
                        continue
                    soup = BeautifulSoup(r.text, "html.parser")
                    cards = soup.find_all("div", class_="col-xs-4") or soup.find_all("article")
                    for card in cards[:20]:
                        link = card.find("a")
                        img = card.find("img")
                        title_tag = card.find("h3") or card.find("h2")
                        if link and img:
                            href = link.get("href", "")
                            slug = href.rstrip("/").split("/")[-1] if href else ""
                            title = title_tag.get_text(strip=True) if title_tag else img.get("alt", "?")
                            thumb = img.get("data-src") or img.get("src") or ""
                            year_tag = card.find("span", class_="year")
                            year = year_tag.get_text(strip=True) if year_tag else ""
                            items.append({
                                "title": title, "thumb": thumb, "id": slug,
                                "year": year, "type": type, "source": mirror,
                            })
                    if items:
                        break
                except Exception:
                    continue
    except Exception as e:
        raise HTTPException(502, str(e))
    if not items:
        return {"items": [], "hint": "Mirror LK21 sedang down. Coba lagi nanti."}
    return {"items": items}

@app.get("/movie/detail")
async def movie_detail(id: str = "", source: str = ""):
    title, synopsis, thumb, year, genres, streams = "", "", "", "", [], []
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            if not source:
                source = "https://tv1.nontondrama.click"
            url = f"{source}/{id}/"
            r = await client.get(url)
            if r.status_code != 200:
                raise HTTPException(404, "Film tidak ditemukan")
            if HAS_BS4:
                soup = BeautifulSoup(r.text, "html.parser")
                title_tag = soup.find("h1") or soup.find("h2", class_="title")
                if title_tag:
                    title = title_tag.get_text(strip=True)
                img_tag = soup.find("div", class_=re.compile(r"poster|image", re.I))
                if img_tag:
                    img = img_tag.find("img")
                    if img:
                        thumb = img.get("data-src") or img.get("src") or ""
                desc_tag = soup.find("div", class_=re.compile(r"sinopsis|description|overview", re.I))
                if desc_tag:
                    synopsis = desc_tag.get_text(strip=True)
                year_tag = soup.find("span", class_="year")
                if year_tag:
                    year = year_tag.get_text(strip=True)[:4]
                genre_tag = soup.find("div", class_=re.compile(r"genre|categories", re.I))
                if genre_tag:
                    genres = [g.get_text(strip=True) for g in genre_tag.find_all("a")]
                player = soup.find("div", class_=re.compile(r"player|embed", re.I))
                if player:
                    iframe = player.find("iframe")
                    if iframe:
                        streams.append({"quality": "Auto", "url": iframe.get("src", "")})
                download_section = soup.find("div", class_="download")
                if download_section:
                    for link in download_section.find_all("a"):
                        href = link.get("href", "")
                        quality = link.get_text(strip=True)
                        if href and ("google" in href or "mega" in href or "mediafire" in href):
                            streams.append({"quality": quality, "url": href})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Movie detail error: {str(e)}")
    return {"title": title, "synopsis": synopsis, "thumb": thumb, "year": year, "genres": genres, "streams": streams}

# ============================================================
# GIF
# ============================================================
GIFUKAI_ACTIONS = [
    "hug", "kiss", "pat", "cry", "sleep", "pout", "blush", "dance",
    "happy", "angry", "wave", "slap", "punch", "bite", "cuddle", "highfive",
    "bonk", "smile", "wink", "shrug", "facepalm", "nom", "poke", "stare",
]

@app.get("/gif/search")
async def gif_search(q: str = "hug"):
    q = (q or "hug").strip().lower()[:40]
    alias = {
        "anime": "hug", "love": "kiss", "sad": "cry", "happy": "happy",
        "angry": "angry", "mad": "angry", "dance": "dance", "sleep": "sleep",
        "wave": "wave", "hi": "wave", "hello": "wave", "punch": "punch",
        "slap": "slap", "bite": "bite", "cuddle": "cuddle", "blush": "blush",
        "reaction": "shrug", "meme": "facepalm", "cartoon": "dance",
    }
    action = alias.get(q, q if q in GIFUKAI_ACTIONS else "hug")
    items = []
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for _ in range(12):
                r = await client.get(f"https://api.gifukai.com/v1/{action}")
                if r.status_code != 200:
                    continue
                data = r.json()
                url = data.get("url") or ""
                if url:
                    items.append({
                        "url": url, "preview": url,
                        "title": f"{data.get('action', action)} · {data.get('anime', 'Anime')}",
                    })
            if len(items) < 6:
                for a in GIFUKAI_ACTIONS:
                    if a == action:
                        continue
                    r = await client.get(f"https://api.gifukai.com/v1/{a}")
                    if r.status_code == 200:
                        data = r.json()
                        url = data.get("url") or ""
                        if url:
                            items.append({"url": url, "preview": url, "title": f"{a} · {data.get('anime', '')}"})
                    if len(items) >= 16:
                        break
    except Exception as e:
        raise HTTPException(502, f"GIF error: {str(e)}")
    return {"items": items[:20], "query": action, "provider": "gifukai"}

@app.get("/gif/actions")
async def gif_actions():
    return {"actions": GIFUKAI_ACTIONS}


async def _maybe_sources(messages: list) -> list:
    """Sumber web sederhana untuk pertanyaan faktual; kosong untuk sapaan."""
    last = ""
    for m in reversed(messages or []):
        if m.get("role") == "user":
            last = (m.get("content") or "").strip()
            break
    if not last or len(last) < 8:
        return []
    low = last.lower()
    greet = ("halo", "hai", "hi", "hello", "pagi", "siang", "malam", "thanks", "terima kasih", "apa kabar")
    if any(low == g or low.startswith(g + " ") or low.startswith(g + "!") for g in greet):
        return []
    # skip pure chit-chat short
    if len(last.split()) < 3 and "?" not in last:
        return []
    sources = []
    try:
        q = urllib.parse.quote(last[:120])
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Wikipedia opensearch
            wr = await client.get(
                "https://id.wikipedia.org/w/api.php",
                params={"action": "opensearch", "search": last[:80], "limit": 1, "namespace": 0, "format": "json"},
            )
            if wr.status_code == 200:
                data = wr.json()
                if len(data) >= 4 and data[1] and data[3]:
                    sources.append({
                        "name": "Wikipedia",
                        "url": data[3][0],
                        "info": data[1][0],
                        "blurb": (data[2][0] if len(data) > 2 and data[2] else "Referensi ensiklopedia")[:160],
                        "logo": "https://www.wikipedia.org/static/favicon/wikipedia.ico",
                    })
    except Exception:
        pass
    return sources


# ============================================================
# AI CHAT
# ============================================================
@app.post("/ai/chat")
async def ai_chat(req: ChatRequest, request: Request):
    raw_messages = req.messages or []
    if not raw_messages:
        raise HTTPException(400, "Pesan kosong")

    # sanitasi pesan (role + content string)
    messages = []
    for m in raw_messages:
        if not isinstance(m, dict):
            continue
        role = (m.get("role") or "user").strip().lower()
        if role not in ("user", "assistant", "system"):
            role = "user"
        content = m.get("content")
        if content is None:
            continue
        content = str(content).strip()
        if not content:
            continue
        messages.append({"role": role, "content": content})
    if not messages:
        raise HTTPException(400, "Pesan kosong")
    # jangan kirim system ganda; max 20
    messages = messages[-20:]

    client_ip = request.client.host if request.client else "unknown"
    role_user = detect_role(request)
    usage, limits = get_usage(client_ip, role_user)
    if usage["chat"] >= limits["chat"]:
        raise HTTPException(429, f"Limit chat harian ({limits['chat']}x). Coba lagi besok atau aktifkan Premium.")

    system_id = {
        "role": "system",
        "content": (
            "Kamu asisten AI di aplikasi Nat-Multi Tools. "
            "Jawab jelas, ramah, dan dalam bahasa yang sama dengan user (utamakan Bahasa Indonesia). "
            "Jika tidak yakin, katakan tidak yakin. Jangan mengarang URL sumber."
        ),
    }

    if req.model == "groq":
        key = env("GROQ_API_KEY")
        if not key:
            raise HTTPException(503, "GROQ_API_KEY belum diset di Environment Variables Vercel")
        groq_models = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "llama-3.1-70b-versatile",
            "meta-llama/llama-4-scout-17b-16e-instruct",
        ]
        payload_msgs = [system_id] + messages
        last_err = ""
        async with httpx.AsyncClient(timeout=75.0) as client:
            for model in groq_models:
                try:
                    r = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json={
                            "model": model,
                            "messages": payload_msgs,
                            "temperature": 0.7,
                            "max_tokens": 2048,
                        },
                    )
                    if r.status_code == 200:
                        data = r.json()
                        reply_text = (
                            ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
                            or ""
                        ).strip()
                        if not reply_text:
                            last_err = "Balasan kosong dari model"
                            continue
                        usage["chat"] += 1
                        sources = []
                        try:
                            sources = await _maybe_sources(messages)
                        except Exception:
                            sources = []
                        return {
                            "reply": reply_text,
                            "model_used": model,
                            "provider": "groq",
                            "sources": sources,
                            "usage_left": limits["chat"] - usage["chat"],
                        }
                    last_err = (r.text or str(r.status_code))[:200]
                except Exception as e:
                    last_err = str(e)[:200]
                    continue
        raise HTTPException(502, f"Groq gagal: {last_err}")

    if req.model in ("gemini", "gemini-flash", "gemini-2.5"):
        key = env("GEMINI_API_KEY")
        if not key:
            raise HTTPException(503, "GEMINI_API_KEY belum diset di Environment Variables Vercel")
        gemini_models = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
        # Gemini: gabungkan system ke user pertama, role harus bergantian user/model
        contents = []
        for idx, m in enumerate(messages):
            role_g = "user" if m["role"] in ("user", "system") else "model"
            text = m["content"]
            if idx == 0 and m["role"] == "user":
                text = system_id["content"] + "\n\nUser: " + text
            # merge consecutive same roles
            if contents and contents[-1]["role"] == role_g:
                contents[-1]["parts"][0]["text"] += "\n" + text
            else:
                contents.append({"role": role_g, "parts": [{"text": text}]})
        if contents and contents[0]["role"] != "user":
            contents.insert(0, {"role": "user", "parts": [{"text": system_id["content"]}]})
        last_err = ""
        async with httpx.AsyncClient(timeout=75.0) as client:
            for model in gemini_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                    r = await client.post(url, json={"contents": contents})
                    if r.status_code == 200:
                        data = r.json()
                        cands = data.get("candidates") or []
                        if not cands:
                            last_err = "Tidak ada kandidat jawaban (mungkin diblok filter)"
                            continue
                        parts = ((cands[0].get("content") or {}).get("parts") or [])
                        reply = "".join(p.get("text", "") for p in parts).strip()
                        if not reply:
                            last_err = "Balasan Gemini kosong"
                            continue
                        usage["chat"] += 1
                        sources = []
                        try:
                            sources = await _maybe_sources(messages)
                        except Exception:
                            sources = []
                        return {
                            "reply": reply,
                            "model_used": model,
                            "provider": "gemini",
                            "sources": sources,
                            "usage_left": limits["chat"] - usage["chat"],
                        }
                    last_err = (r.text or str(r.status_code))[:200]
                except Exception as e:
                    last_err = str(e)[:200]
                    continue
        raise HTTPException(502, f"Gemini error: {last_err}")

    raise HTTPException(400, f"Model tidak dikenal: {req.model}. Pilih groq atau gemini.")


# ============================================================
# AI IMAGE
# ============================================================
@app.post("/ai/image")
async def ai_image(req: ImageRequest, request: Request):
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(400, "Prompt kosong")
    client_ip = request.client.host if request.client else "unknown"
    role = detect_role(request)
    usage, limits = get_usage(client_ip, role)
    if usage["image"] >= limits["image"]:
        raise HTTPException(429, f"Limit image harian ({limits['image']}x)")
    
    # PRIMARY: Gemini Image Generation
    key = env("GEMINI_API_KEY")
    last_err = ""
    if key:
        image_models = ["gemini-2.5-flash-image", "gemini-nano-banana-2.1", "gemini-2.5-flash-image-preview"]
        async with httpx.AsyncClient(timeout=90.0) as client:
            for model in image_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
                    }
                    r = await client.post(url, json=payload)
                    if r.status_code == 200:
                        data = r.json()
                        parts = data["candidates"][0]["content"]["parts"]
                        for p in parts:
                            if "inlineData" in p:
                                b64 = p["inlineData"]["data"]
                                mime = p["inlineData"].get("mimeType", "image/png")
                                usage["image"] += 1
                                return {
                                    "image_url": f"data:{mime};base64,{b64}",
                                    "b64": f"data:{mime};base64,{b64}",
                                    "model_used": model, "provider": "gemini",
                                    "usage_left": limits["image"] - usage["image"],
                                }
                    last_err = r.text[:150]
                except Exception as e:
                    last_err = str(e)[:150]
                    continue
    
    # FALLBACK: Pollinations.ai
    try:
        safe_prompt = urllib.parse.quote(prompt)
        seed = uuid.uuid4().int % 1000000
        image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true&seed={seed}&model=flux"
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.head(image_url)
            if r.status_code == 200:
                usage["image"] += 1
                return {
                    "image_url": image_url, "b64": image_url,
                    "model_used": "pollinations-flux", "provider": "pollinations",
                    "message": "Gambar dibuat via Pollinations",
                    "usage_left": limits["image"] - usage["image"],
                }
    except Exception:
        pass
    
    raise HTTPException(502, f"Image generation gagal: {last_err}")



# ============================================================
# LIHAT KENYATAAN (Groq)
# ============================================================
class RealityRequest(BaseModel):
    claim: str

class RefinePromptRequest(BaseModel):
    prompt: str

@app.post("/ai/reality")
async def ai_reality(req: RealityRequest, request: Request):
    claim = (req.claim or "").strip()
    if not claim:
        raise HTTPException(400, "Isi klaim / topik yang ingin dicek")
    if len(claim) > 2000:
        raise HTTPException(400, "Teks terlalu panjang")
    client_ip = request.client.host if request.client else "unknown"
    role = detect_role(request)
    usage, limits = get_usage(client_ip, role)
    if usage["chat"] >= limits["chat"]:
        raise HTTPException(429, f"Limit chat harian ({limits['chat']}x)")
    key = env("GROQ_API_KEY")
    if not key:
        raise HTTPException(503, "GROQ_API_KEY belum diset")
    system = (
        "Kamu analis fakta berbahasa Indonesia. User memberi klaim/topik. "
        "Balas HANYA JSON valid tanpa markdown, format: "
        '{"opinion":"penjelasan 2-5 kalimat","real_percent":0-100,"unreal_percent":0-100}. '
        "real_percent + unreal_percent harus = 100. "
        "Nilai real_percent = seberapa besar klaim itu masuk akal / didukung bukti umum. "
        "Jujur, netral, tidak mengarang sumber spesifik yang tidak pasti."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": claim},
    ]
    last_err = ""
    async with httpx.AsyncClient(timeout=60.0) as client:
        for model in ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]:
            try:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={"model": model, "messages": messages, "temperature": 0.4, "max_tokens": 800},
                )
                if r.status_code != 200:
                    last_err = r.text[:150]
                    continue
                raw = r.json()["choices"][0]["message"]["content"]
                # parse JSON
                m = re.search(r"\{[\s\S]*\}", raw)
                data = {}
                if m:
                    import json as _json
                    try:
                        data = _json.loads(m.group(0))
                    except Exception:
                        data = {}
                opinion = data.get("opinion") or raw.strip()[:800]
                real_p = int(data.get("real_percent") or data.get("real") or 50)
                unreal_p = int(data.get("unreal_percent") or data.get("unreal") or (100 - real_p))
                real_p = max(0, min(100, real_p))
                unreal_p = max(0, min(100, unreal_p))
                if real_p + unreal_p != 100:
                    unreal_p = 100 - real_p
                usage["chat"] += 1
                return {
                    "opinion": opinion,
                    "real_percent": real_p,
                    "unreal_percent": unreal_p,
                    "model_used": model,
                    "usage_left": limits["chat"] - usage["chat"],
                }
            except Exception as e:
                last_err = str(e)[:150]
                continue
    raise HTTPException(502, f"Reality check gagal: {last_err}")


@app.post("/ai/refine-prompt")
async def ai_refine_prompt(req: RefinePromptRequest, request: Request):
    prompt = (req.prompt or "").strip()
    if not prompt:
        raise HTTPException(400, "Prompt kosong")
    key = env("GEMINI_API_KEY")
    if not key:
        # fallback light rewrite without external if no key
        refined = (
            f"Highly detailed, cinematic lighting, sharp focus, masterpiece, {prompt}, "
            "intricate details, professional photography, 8k resolution"
        )
        return {"refined": refined, "provider": "local-template"}
    instruction = (
        "Perbaiki dan perluas prompt image generation berikut agar lebih jelas, visual, dan efektif. "
        "Balas HANYA teks prompt yang sudah diperbaiki dalam bahasa Inggris, tanpa penjelasan.\n\n"
        f"Prompt asli: {prompt}"
    )
    last_err = ""
    async with httpx.AsyncClient(timeout=45.0) as client:
        for model in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite"]:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                r = await client.post(url, json={"contents": [{"parts": [{"text": instruction}]}]})
                if r.status_code == 200:
                    text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    text = re.sub(r"^```[a-z]*\n?", "", text)
                    text = re.sub(r"\n?```$", "", text).strip()
                    return {"refined": text, "model_used": model, "provider": "gemini"}
                last_err = r.text[:120]
            except Exception as e:
                last_err = str(e)[:120]
                continue
    raise HTTPException(502, f"Refine gagal: {last_err}")


@app.get("/covers/random")
async def covers_random(type: str = "comic", n: int = 8):
    """Sampul acak untuk tarik minat saat user pilih source."""
    n = max(1, min(12, n))
    items = []
    try:
        async with httpx.AsyncClient(timeout=18.0) as client:
            if type in ("comic", "all"):
                r = await client.get(
                    "https://api.mangadex.org/manga",
                    params={"limit": n, "order[followedCount]": "desc", "includes[]": ["cover_art"],
                            "contentRating[]": ["safe", "suggestive"]},
                )
                if r.status_code == 200:
                    for m in (r.json().get("data") or [])[:n]:
                        attrs = m.get("attributes") or {}
                        title = (attrs.get("title") or {}).get("en") or next(iter((attrs.get("title") or {}).values()), "?")
                        cover = ""
                        for rel in m.get("relationships") or []:
                            if rel.get("type") == "cover_art":
                                fn = (rel.get("attributes") or {}).get("fileName") or ""
                                if fn:
                                    cover = f"https://uploads.mangadex.org/covers/{m['id']}/{fn}.256.jpg"
                        if cover:
                            items.append({"title": title, "thumb": cover, "type": "comic"})
            if type in ("anime", "all") and len(items) < n:
                r = await client.get("https://api.jikan.moe/v4/top/anime", params={"limit": n})
                if r.status_code == 200:
                    for a in (r.json().get("data") or [])[:n]:
                        items.append({
                            "title": a.get("title") or "?",
                            "thumb": (a.get("images") or {}).get("jpg", {}).get("image_url") or "",
                            "type": "anime",
                        })
            if type in ("novel", "movie", "drama") and len(items) < n:
                # reuse manga covers as visual filler if no dedicated source
                pass
    except Exception:
        pass
    if not items:
        # placeholder gradient cards
        for i in range(n):
            items.append({"title": f"Koleksi #{i+1}", "thumb": "", "type": type})
    
    return {"items": items[:n]}




# ============================================================
# SAFELINK BYPASS
# ============================================================
@app.get("/safelink/bypass")
async def safelink_bypass(url: str = ""):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL tidak valid")
    original_url = url
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            r = await client.get(url)
            html = r.text
            current_url = str(r.url)
            js_patterns = [
                r'window\.location\s*=\s*["\']([^"\']+)["\']',
                r'window\.location\.href\s*=\s*["\']([^"\']+)["\']',
                r'var\s+redirect_url\s*=\s*["\']([^"\']+)["\']',
                r'data-url=["\']([^"\']+)["\']',
            ]
            for pattern in js_patterns:
                match = re.search(pattern, html, re.I)
                if match:
                    target = urllib.parse.unquote(match.group(1))
                    if target.startswith("http"):
                        return {"original": original_url, "final": target, "method": "js_parse", "status": "success"}
            meta_match = re.search(r'<meta[^>]+content=["\']\d+;\s*url=([^"\']+)["\']', html, re.I)
            if meta_match:
                return {"original": original_url, "final": urllib.parse.unquote(meta_match.group(1)), "method": "meta_refresh", "status": "success"}
            if HAS_BS4:
                soup = BeautifulSoup(html, "html.parser")
                domain_asli = re.sub(r'https?://', '', current_url).split('/')[0]
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("http") and domain_asli not in href:
                        if not any(skip in href for skip in ["facebook", "twitter", "google.com/ads"]):
                            return {"original": original_url, "final": href, "method": "html_link", "status": "success"}
            return {"original": original_url, "final": current_url, "method": "http_redirect", "status": "partial"}
    except Exception as e:
        raise HTTPException(502, f"Bypass gagal: {str(e)}")

# ============================================================
# PREMIUM & ADMIN
# ============================================================
@app.post("/premium/verify")
async def premium_verify(request: Request):
    body = await request.json()
    code = (body.get("code") or "").strip()
    code_u = code.upper()
    if code == ADMIN_CODE or code_u == ADMIN_CODE.upper():
        return {"ok": True, "role": "admin", "message": "Admin aktif"}
    if code_u in FIXED_PREMIUM_CODES:
        return {"ok": True, "role": "premium", "message": "Premium aktif"}
    raise HTTPException(403, "Kode salah")

@app.post("/admin/verify")
async def admin_verify(request: Request):
    body = await request.json()
    code = (body.get("code") or "").strip()
    if code == ADMIN_CODE or code.upper() == ADMIN_CODE.upper():
        return {"ok": True, "role": "admin", "message": "Admin aktif"}
    if hashlib.sha256(code.encode()).hexdigest() == ADMIN_HASH:
        return {"ok": True, "role": "admin", "message": "Admin aktif"}
    raise HTTPException(403, "Kode salah")
