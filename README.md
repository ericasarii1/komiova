# KomiOva 🦸

Web app baca komik dengan data asli dari [MangaDex API](https://api.mangadex.org) (resmi & legal).

## Fitur
- Daftar komik populer + pencarian judul (data live MangaDex)
- Cover, status, genre, sinopsis asli
- Daftar chapter (bahasa Inggris) + reader scroll vertikal
- Navigasi prev/next chapter + keyboard (←/→/Esc)
- Favorit (localStorage)
- Proxy gambar server-side (uploads.mangadex.org)

## Jalankan lokal
```
pip install -r requirements.txt
python app.py
```

## Deploy
Dockerfile included (gunicorn). Railway-ready.
