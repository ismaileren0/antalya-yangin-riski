"""
Ortak ayarlar: alan, cozunurluk, tarih araligi, klasorler, anahtarlar.
Diger tum betikler bu dosyayi kullanir.
"""

import os
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

# ------------------------------------------------------------------
# Klasorler
# ------------------------------------------------------------------
KOK = Path(__file__).resolve().parent
load_dotenv(KOK / ".env")

VERI = KOK / "veri"
HAM = VERI / "ham"
SENTINEL_KLASOR = HAM / "sentinel"
ISLENMIS = VERI / "islenmis"
for _k in (HAM, SENTINEL_KLASOR, ISLENMIS):
    _k.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# Alan ve izgara
# ------------------------------------------------------------------
# Antalya ilini kapsayan kutu: bati, guney, dogu, kuzey (derece, WGS84)
BBOX = (29.2, 36.1, 32.6, 37.6)

# Ince izgara: 0.01 derece (~1 km). Uydu verisi bu izgarada alinir.
COZUNURLUK = 0.01
GENISLIK = round((BBOX[2] - BBOX[0]) / COZUNURLUK)   # 340 sutun
YUKSEKLIK = round((BBOX[3] - BBOX[1]) / COZUNURLUK)  # 150 satir

# Hava izgarasi: 0.1 derece (~10 km). Hava verisi bu noktalarda alinir,
# her ince hucre icinde bulundugu kaba hucrenin degerini kullanir.
HAVA_COZUNURLUK = 0.1

# ------------------------------------------------------------------
# Tarih araligi: son 6 ay (sabit, demo tekrar uretilebilir olsun)
# ------------------------------------------------------------------
BITIS = date(2026, 10, 18)
BASLANGIC = BITIS - timedelta(days=183)  # 2026-04-18

# Open-Meteo arsivi birkac gun geriden gelir
HAVA_BITIS = min(BITIS, date.today() - timedelta(days=6))


def ay_listesi():
    """Takvim aylarina bolunmus donemler: [(etiket, baslangic, bitis), ...]"""
    aylar = []
    yil, ay = BASLANGIC.year, BASLANGIC.month
    while (yil, ay) <= (BITIS.year, BITIS.month):
        ilk = date(yil, ay, 1)
        sonraki = date(yil + (ay == 12), ay % 12 + 1, 1)
        son = sonraki - timedelta(days=1)
        aylar.append((f"{yil}-{ay:02d}", max(ilk, BASLANGIC), min(son, BITIS)))
        yil, ay = sonraki.year, sonraki.month
    return aylar


AYLAR = ay_listesi()

# ------------------------------------------------------------------
# Anahtarlar (.env)
# ------------------------------------------------------------------
SH_CLIENT_ID = os.getenv("SH_CLIENT_ID", "").strip()
SH_CLIENT_SECRET = os.getenv("SH_CLIENT_SECRET", "").strip()
FIRMS_MAP_KEY = os.getenv("FIRMS_MAP_KEY", "").strip()

SH_BASE_URL = "https://sh.dataspace.copernicus.eu"
SH_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
)

# ------------------------------------------------------------------
# Cikti dosyalari
# ------------------------------------------------------------------
SINIR_DOSYASI = ISLENMIS / "antalya_sinir.geojson"
IZGARA_DOSYASI = ISLENMIS / "izgara.csv"
HAVA_GUNLUK_DOSYASI = HAM / "hava_gunluk.csv"
FIRMS_DOSYASI = HAM / "firms_noktalar.csv"
BIRLESIK_DOSYA = ISLENMIS / "hucre_ay.csv"


def sentinel_dosyasi(ay_etiketi):
    return SENTINEL_KLASOR / f"s2_{ay_etiketi}.tif"
