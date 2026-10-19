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
    auth = request.headers.get("Authorization", "").strip().lower()
    if auth == "admin": return "admin"
    if auth == "premium": return "premium"
    return "free"

# ---------- Config ----------
ADMIN_CODE = env("ADMIN_CODE", "PEANUTSBUTTERCUP")
ADMIN_HASH = hashlib.sha256(ADMIN_CODE.encode()).hexdigest()
FIXED_PREMIUM_CODES = {"ZURAALMOND", "NATSIGMA", "OHYAYES", "SKIBIDIMOMENT", "ROHANCHESS"}

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
WURMZ_BASE = "https://wurmz.net"


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
        h3 = card.find("h3")
        title = (h3.get_text(strip=True) if h3 else None) or (img.get("alt") if img else None) or "?"
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


@app.get("/comic/search")
async def comic_search(source: str = "all", q: str = ""):
    items = []
    q = (q or "").strip()

    # 1) MangaDex
    if source in ("all", "mangadex"):
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
                    url = f"{KOMIKU_WEB}/"
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

    # 3) Voratoon — domain baca: v10.voratoon.com / voratoon.co (bukan voratoon.id)
    if source in ("all", "voratoon") and HAS_BS4:
        try:
            async with httpx.AsyncClient(timeout=22.0, follow_redirects=True, headers={**BROWSER_HEADERS, "Referer": VORATOON_BASE + "/"}) as client:
                url = f"{VORATOON_BASE}/?s={urllib.parse.quote(q)}" if q else f"{VORATOON_BASE}/"
                r = await client.get(url)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    seen_v = set()
                    for a in soup.select('a[href*="/series/"]'):
                        href = a.get("href") or ""
                        slug = href.rstrip("/").split("/")[-1]
                        if not slug or slug == "series" or slug in seen_v or "chapter" in slug:
                            continue
                        img = a.find("img")
                        title = (img.get("alt") if img else "") or ""
                        if not title:
                            raw = a.get_text(" ", strip=True)
                            title = re.sub(r"[\d.,]+[KkMm]?\s*[\d.,]*[KkMm]?\s*#?\d*", "", raw).strip()
                        title = re.sub(r"\b(Action|Fantasy|Comedy|Romance|Drama|Adventure|Ecchi|Seinen|Shounen)\b", "", title, flags=re.I).strip()
                        if not title or len(title) < 3:
                            continue
                        seen_v.add(slug)
                        items.append({
                            "title": title[:90],
                            "thumb": (img.get("data-src") or img.get("src") or "") if img else "",
                            "id": slug,
                            "source": "voratoon",
                            "label": "PROJECT",
                        })
                        if len(seen_v) >= 24:
                            break
        except Exception:
            pass

    
    # 3b) Wurmz (Premium) — https://wurmz.net
    if source in ("all", "wurmz") and HAS_BS4:
        # Premium: frontend must gate; backend still serves for admin/premium clients
        try:
            async with httpx.AsyncClient(timeout=22.0, follow_redirects=True, headers={**BROWSER_HEADERS, "Referer": WURMZ_BASE + "/"}) as client:
                url = f"{WURMZ_BASE}/?s={urllib.parse.quote(q)}" if q else f"{WURMZ_BASE}/"
                r = await client.get(url)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    seen_w = set()
                    for art in soup.find_all("article"):
                        a = art.find("a", href=True)
                        if not a:
                            continue
                        href = a["href"]
                        if "/detail/" not in href:
                            continue
                        # /detail/manga/slug or /detail/manhwa/slug
                        parts = href.strip("/").split("/")
                        if len(parts) < 3:
                            continue
                        kind, slug = parts[-2], parts[-1]
                        if slug in seen_w or slug in ("manga", "manhwa", "manhua"):
                            continue
                        img = art.find("img")
                        title = (img.get("alt") if img else "") or a.get_text(strip=True) or slug
                        # skip pure "Manga" type labels as sole title if short
                        if title.lower() in ("manga", "manhwa", "manhua"):
                            # try next text node
                            for t in art.stripped_strings:
                                if t.lower() not in ("manga", "manhwa", "manhua") and len(t) > 3:
                                    title = t
                                    break
                        seen_w.add(slug)
                        items.append({
                            "title": title[:90],
                            "thumb": (img.get("data-src") or img.get("src") or "") if img else "",
                            "id": f"{kind}/{slug}",
                            "source": "wurmz",
                            "label": "PREMIUM",
                        })
                        if len(seen_w) >= 24:
                            break
        except Exception:
            pass


    # 4) Other premium sources (best-effort)
    if source in ("kiryuu", "manhwadesu", "shinigami") and HAS_BS4:
        bases = {
            "kiryuu": ("https://kiryuu.io", f"https://kiryuu.io/?s={urllib.parse.quote(q)}" if q else "https://kiryuu.io/"),
            "manhwadesu": ("https://manhwadesu.org", f"https://manhwadesu.org/?s={urllib.parse.quote(q)}" if q else "https://manhwadesu.org/"),
            "shinigami": ("https://shinigami.asia", f"https://shinigami.asia/?s={urllib.parse.quote(q)}" if q else "https://shinigami.asia/"),
            "voratoon": ("https://voratoon.com", f"https://voratoon.com/?s={urllib.parse.quote(q)}" if q else "https://voratoon.com/"),
        }
        try:
            base, url = bases[source]
            async with httpx.AsyncClient(timeout=18.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for a in soup.select("a[href*='/manga/'], a[href*='/comic/'], a[href*='/series/']")[:40]:
                        href = a.get("href") or ""
                        title = a.get_text(strip=True)
                        if not title or len(title) < 3:
                            continue
                        img = a.find("img")
                        if not img and a.parent:
                            img = a.parent.find("img")
                        slug = _slug_from_href(href)
                        if slug in ("manga", "comic", "series"):
                            continue
                        items.append({
                            "title": title[:80],
                            "thumb": (img.get("data-src") or img.get("src") or "") if img else "",
                            "id": slug,
                            "source": source,
                            "label": "PREMIUM",
                        })
        except Exception:
            pass

    # dedupe
    seen, unique = set(), []
    for it in items:
        key = ((it.get("title") or "").lower()[:40], it.get("source"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)
    return {"items": unique[:30]}


@app.get("/comic/detail")
async def comic_detail(source: str = "komiku", id: str = ""):
    if not id:
        raise HTTPException(400, "id kosong")
    chapters, title, synopsis, thumb, genres = [], id, "", "", []

    if source == "mangadex":
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                r = await client.get(f"{MD_API}/manga/{id}", params={"includes[]": ["cover_art"]})
                if r.status_code != 200:
                    raise HTTPException(502, "MangaDex detail gagal")
                m = (r.json() or {}).get("data") or {}
                attrs = m.get("attributes") or {}
                title = (attrs.get("title") or {}).get("en") or next(iter((attrs.get("title") or {}).values()), id)
                synopsis = (attrs.get("description") or {}).get("en") or next(iter((attrs.get("description") or {}).values()), "")
                offset = 0
                while offset < 200:
                    rf = await client.get(f"{MD_API}/manga/{id}/feed", params={
                        "limit": 100, "offset": offset,
                        "translatedLanguage[]": ["id", "en"],
                        "order[chapter]": "desc",
                        "includeEmptyPages": 0,
                        "contentRating[]": ["safe", "suggestive", "erotica"],
                    })
                    batch = (rf.json() or {}).get("data") or []
                    if not batch:
                        break
                    for ch in batch:
                        a = ch.get("attributes") or {}
                        num = a.get("chapter") or "?"
                        chapters.append({
                            "title": f"Chapter {num}" + (f" — {a['title']}" if a.get("title") else ""),
                            "id": ch["id"],
                        })
                    offset += 100
                    if len(batch) < 100:
                        break
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, str(e))
        return {"title": title, "chapters": chapters, "synopsis": synopsis, "thumb": thumb, "genres": genres}

    # Komiku + other HTML sources
    try:
        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            if source == "komiku":
                url = f"{KOMIKU_WEB}/manga/{id}/"
            elif source == "kiryuu":
                url = f"https://kiryuu.io/manga/{id}/"
            elif source == "manhwadesu":
                url = f"https://manhwadesu.org/manga/{id}/"
            elif source == "shinigami":
                url = f"https://shinigami.asia/series/{id}/"
            elif source == "voratoon":
                url = f"{VORATOON_BASE}/series/{id}"
            elif source == "wurmz":
                # id = "manga/slug" or "manhwa/slug"
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

            # chapter links
            seen_ch = set()
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(" ", strip=True)
                if not text:
                    continue
                low = href.lower()
                if "chapter" in low or re.search(r"ch[ap]*-?\d", low) or re.search(r"chapter[-\s]?\d", text.lower()):
                    if href.rstrip("/").endswith(f"/manga/{id}") or href.rstrip("/").endswith(f"/series/{id}"):
                        if "/chapter/" not in low:
                            continue
                    # Voratoon: keep "slug/chapter/N"
                    if source == "voratoon" and "/chapter/" in low:
                        parts = href.split("/series/")[-1].strip("/")
                        ch_id = parts
                        title_ch = re.sub(r"[\d.,]+[KkMm].*", "", text).strip() or text[:40]
                    elif source == "wurmz" and "/chapter/" in low and "/detail/" in low:
                        # detail/manga/slug/chapter/N
                        ch_id = href.split("/detail/")[-1].strip("/")
                        title_ch = re.sub(r"[\d.,]+[KkMm].*", "", text).strip() or text[:40]
                    else:
                        ch_id = _slug_from_href(href)
                        title_ch = text[:80]
                    if not ch_id or ch_id == id or ch_id in seen_ch:
                        continue
                    if len(ch_id) < 3:
                        continue
                    seen_ch.add(ch_id)
                    chapters.append({"title": title_ch[:80], "id": ch_id})
            # prefer longer lists; komiku lists newest first often
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Detail error: {e}")

    return {"title": title, "chapters": chapters[:200], "synopsis": synopsis, "thumb": thumb, "genres": genres}


@app.get("/comic/chapter")
async def comic_chapter(source: str = "komiku", id: str = ""):
    if not id:
        raise HTTPException(400, "id kosong")
    images = []

    if source == "mangadex":
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(f"{MD_API}/at-home/server/{id}")
                if r.status_code != 200:
                    raise HTTPException(502, f"MangaDex at-home {r.status_code}")
                data = r.json()
                base = data.get("baseUrl") or ""
                ch = data.get("chapter") or {}
                hash_ = ch.get("hash") or ""
                pages = ch.get("dataSaver") or ch.get("data") or []
                quality = "data-saver" if ch.get("dataSaver") else "data"
                images = [f"{base}/{quality}/{hash_}/{p}" for p in pages]
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, str(e))
        if not images:
            raise HTTPException(404, "Halaman MangaDex kosong (region/IP?)")
        return {"images": images}

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers={**BROWSER_HEADERS, "Referer": VORATOON_BASE + "/"}) as client:
            if source == "voratoon":
                if id.startswith("http"):
                    url = id
                elif "/chapter/" in id:
                    url = f"{VORATOON_BASE}/series/{id}" if not id.startswith("series/") else f"{VORATOON_BASE}/{id}"
                else:
                    url = f"{VORATOON_BASE}/series/{id}"
            elif source == "wurmz":
                # id = "manga/slug/chapter/1" or full
                if id.startswith("http"):
                    url = id
                elif id.startswith("detail/"):
                    url = f"{WURMZ_BASE}/{id}"
                else:
                    url = f"{WURMZ_BASE}/detail/{id}"
            elif source == "komiku":
                url = id if id.startswith("http") else f"{KOMIKU_WEB}/{id}/"
            else:
                url = id if id.startswith("http") else f"https://kiryuu.io/{id}/"

            r = await client.get(url)
            if r.status_code != 200:
                raise HTTPException(404, f"Chapter tidak ditemukan ({r.status_code})")
            if not HAS_BS4:
                raise HTTPException(500, "BeautifulSoup tidak tersedia")
            soup = BeautifulSoup(r.text, "html.parser")
            skip = ("logo", "icon", "avatar", "emoji", "promosi", "ads", "banner", "pixel", "spinner", "cover", "background")
            for img in soup.find_all("img"):
                src_img = img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
                if not src_img.startswith("http"):
                    continue
                low = src_img.lower()
                if any(s in low for s in skip):
                    continue
                if source in ("voratoon", "wurmz"):
                    if "cdn.voratoon.com" in low or "wurmz" in low or "/wp-content/img/" in low or "/chapter/" in low:
                        if src_img not in images:
                            images.append(src_img.split("?")[0] if "X-Amz" in src_img else src_img)
                else:
                    if any(x in low for x in ["komiku", "upload", "cdn", "manga", "chapter", "wp-content", "image"]):
                        if src_img not in images:
                            images.append(src_img)
            if not images and source == "voratoon":
                for img in soup.find_all("img"):
                    src_img = img.get("data-src") or img.get("src") or ""
                    if "cdn.voratoon.com" in src_img and src_img not in images:
                        images.append(src_img)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, str(e))

    if not images:
        raise HTTPException(404, "Gambar chapter tidak ditemukan")
    return {"images": images}


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
async def novel_search(q: str = ""):
    items = []
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            url = "https://wbnovel.com/"
            params = {"s": q, "post_type": "wp-manga"} if q else None
            r = await client.get(url, params=params)
            if r.status_code != 200 or not HAS_BS4:
                return {"items": []}
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.find_all("div", class_="c-tabs-item__content") or soup.find_all("article")
            seen = set()
            for card in cards[:24]:
                link = card.find("a")
                img = card.find("img")
                title_tag = card.find("h3") or card.find("h4")
                if link:
                    href = link.get("href", "")
                    slug = href.rstrip("/").split("/")[-1] if href else ""
                    if slug in seen or "chapter" in slug.lower():
                        continue
                    seen.add(slug)
                    items.append({
                        "title": title_tag.get_text(strip=True) if title_tag else slug.replace("-", " ").title(),
                        "thumb": (img.get("data-src") or img.get("src") or "") if img else "",
                        "id": slug, "source": "wbnovel",
                    })
    except Exception as e:
        raise HTTPException(502, f"Novel search error: {str(e)}")
    return {"items": items}

@app.get("/novel/detail")
async def novel_detail(id: str = ""):
    if not id:
        raise HTTPException(400, "id kosong")
    chapters, title, synopsis = [], id.replace("-", " ").title(), ""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            r = await client.get(f"https://wbnovel.com/nv/{id}/")
            if r.status_code != 200:
                raise HTTPException(404, "Novel tidak ditemukan")
            if HAS_BS4:
                soup = BeautifulSoup(r.text, "html.parser")
                title_tag = soup.find("h1")
                if title_tag:
                    title = title_tag.get_text(strip=True)
                desc_tag = soup.find("div", class_=re.compile(r"summary|description", re.I))
                if desc_tag:
                    synopsis = desc_tag.get_text(strip=True)[:1500]
                chapter_list = soup.find("ul", class_="chapter") or soup.find("div", class_="listing-chapters_wrap")
                if chapter_list:
                    for link in chapter_list.find_all("a")[:150]:
                        ch_title = link.get_text(strip=True)
                        href = link.get("href", "")
                        ch_id = href.rstrip("/").split("/")[-1] if href else ""
                        if ch_id and "chapter" in ch_id.lower():
                            chapters.append({"title": ch_title, "id": ch_id})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Novel detail error: {str(e)}")
    return {"title": title, "synopsis": synopsis, "chapters": chapters, "genres": []}

@app.get("/novel/chapter")
async def novel_chapter(id: str = ""):
    if not id:
        raise HTTPException(400, "id kosong")
    content, title = "", ""
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=BROWSER_HEADERS) as client:
            url = id if id.startswith("http") else f"https://wbnovel.com/nv/{id}/"
            r = await client.get(url)
            if r.status_code != 200:
                raise HTTPException(404, "Chapter tidak ditemukan")
            if HAS_BS4:
                soup = BeautifulSoup(r.text, "html.parser")
                title_tag = soup.find("h1") or soup.find("h2")
                if title_tag:
                    title = title_tag.get_text(strip=True)
                content_tag = (
                    soup.find("div", class_="reading-content") or
                    soup.find("div", class_="text-left") or
                    soup.find("div", class_="entry-content")
                )
                if content_tag:
                    for script in content_tag.find_all(["script", "style"]):
                        script.decompose()
                    content = content_tag.get_text(separator="\n", strip=True)
                    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Novel chapter error: {str(e)}")
    return {"title": title, "content": content}

# ============================================================
# MOVIE / DRAMA
# ============================================================
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
    messages = req.messages or []
    if not messages:
        raise HTTPException(400, "Pesan kosong")
    client_ip = request.client.host if request.client else "unknown"
    role = detect_role(request)
    usage, limits = get_usage(client_ip, role)
    if usage["chat"] >= limits["chat"]:
        raise HTTPException(429, f"Limit chat harian ({limits['chat']}x)")
    
    if req.model == "groq":
        key = env("GROQ_API_KEY")
        if not key:
            raise HTTPException(503, "GROQ_API_KEY belum diset")
        groq_models = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile"]
        last_err = ""
        async with httpx.AsyncClient(timeout=60.0) as client:
            for model in groq_models:
                try:
                    r = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json={"model": model, "messages": messages, "temperature": 0.7, "max_tokens": 2048},
                    )
                    if r.status_code == 200:
                        data = r.json()
                        usage["chat"] += 1
                        reply_text = data["choices"][0]["message"]["content"]
                        sources = await _maybe_sources(messages)
                        return {
                            "reply": reply_text,
                            "model_used": model, "provider": "groq",
                            "sources": sources,
                            "usage_left": limits["chat"] - usage["chat"],
                        }
                    last_err = r.text[:150]
                except Exception as e:
                    last_err = str(e)[:150]
                    continue
        raise HTTPException(502, f"Groq gagal: {last_err}")
    
    if req.model in ("gemini", "gemini-flash", "gemini-2.5"):
        key = env("GEMINI_API_KEY")
        if not key:
            raise HTTPException(503, "GEMINI_API_KEY belum diset")
        gemini_models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
        contents = []
        for m in messages:
            role_g = "user" if m.get("role") == "user" else "model"
            contents.append({"role": role_g, "parts": [{"text": m.get("content", "")}]})
        last_err = ""
        async with httpx.AsyncClient(timeout=60.0) as client:
            for model in gemini_models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                    r = await client.post(url, json={"contents": contents})
                    if r.status_code == 200:
                        data = r.json()
                        reply = data["candidates"][0]["content"]["parts"][0]["text"]
                        usage["chat"] += 1
                        sources = await _maybe_sources(messages)
                        return {
                            "reply": reply, "model_used": model, "provider": "gemini",
                            "sources": sources,
                            "usage_left": limits["chat"] - usage["chat"],
                        }
                    last_err = r.text[:150]
                except Exception as e:
                    last_err = str(e)[:150]
                    continue
        raise HTTPException(502, f"Gemini error: {last_err}")
    
    raise HTTPException(400, f"Model tidak dikenal: {req.model}")

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
        image_models = ["gemini-2.5-flash-preview-image-generation", "gemini-2.0-flash-exp-image-generation"]
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
        for model in ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile"]:
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
        for model in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
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
    code = (body.get("code") or "").strip().upper()
    if code == ADMIN_CODE:
        return {"ok": True, "role": "admin", "message": "Admin aktif"}
    if code in FIXED_PREMIUM_CODES:
        return {"ok": True, "role": "premium", "message": "Premium aktif"}
    raise HTTPException(403, "Kode salah")

@app.post("/admin/verify")
async def admin_verify(request: Request):
    body = await request.json()
    code = (body.get("code") or "").strip()
    if hashlib.sha256(code.encode()).hexdigest() == ADMIN_HASH:
        token = hashlib.sha256(f"{code}:{int(time.time()//3600)}".encode()).hexdigest()[:24]
        return {"ok": True, "token": token, "role": "admin"}
    raise HTTPException(403, "Kode salah")
