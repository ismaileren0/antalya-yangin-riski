"""
Antalya Yangin Riski - Baglanti testi
Copernicus (Sentinel Hub), NASA FIRMS ve Open-Meteo servislerinin
.env dosyasindaki anahtarlarla yanit verip vermedigini kontrol eder.

Calistirma:  python test_baglanti.py
"""

import os
import sys

try:
    import requests
    from dotenv import load_dotenv
except ImportError:
    print("Eksik kutuphane var. Once su komutu calistir:")
    print("    pip install requests python-dotenv")
    sys.exit(1)

# .env dosyasini bu betigin bulundugu klasorden oku
BURASI = os.path.dirname(os.path.abspath(__file__))
ENV_YOLU = os.path.join(BURASI, ".env")
if not os.path.exists(ENV_YOLU):
    print(f"[HATA] .env dosyasi bulunamadi: {ENV_YOLU}")
    print("       .env dosyasi bu betikle ayni klasorde olmali (adi .env.txt olmamali).")
    sys.exit(1)
load_dotenv(ENV_YOLU)

# Antalya ilini kapsayan kutu: bati, guney, dogu, kuzey (derece)
ANTALYA_BBOX = [29.2, 36.1, 32.6, 37.6]
ANTALYA_MERKEZ = (36.90, 30.70)  # enlem, boylam

sonuclar = {}


def maskele(deger):
    if not deger:
        return "(bos)"
    return deger[:4] + "..." + deger[-2:] if len(deger) > 8 else "***"


def baslik(metin):
    print("\n" + "=" * 60)
    print(metin)
    print("=" * 60)


# ------------------------------------------------------------------
# 1) Copernicus Data Space / Sentinel Hub
# ------------------------------------------------------------------
baslik("1) Copernicus Data Space (Sentinel-2)")
client_id = os.getenv("SH_CLIENT_ID", "").strip()
client_secret = os.getenv("SH_CLIENT_SECRET", "").strip()
print(f"SH_CLIENT_ID     : {maskele(client_id)}")
print(f"SH_CLIENT_SECRET : {maskele(client_secret)}")

if not client_id or not client_secret:
    print("[HATA] SH_CLIENT_ID veya SH_CLIENT_SECRET .env icinde yok ya da bos.")
    sonuclar["Copernicus"] = False
else:
    try:
        token_yanit = requests.post(
            "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=30,
        )
        if token_yanit.status_code != 200:
            print(f"[HATA] Token alinamadi (HTTP {token_yanit.status_code}).")
            print("       Client ID / Secret yanlis kopyalanmis olabilir; bosluk veya tirnak olmamali.")
            print("       Sunucu yaniti:", token_yanit.text[:200])
            sonuclar["Copernicus"] = False
        else:
            token = token_yanit.json()["access_token"]
            print("[OK] Erisim tokeni alindi.")

            # Antalya uzerinde son goruntuleri ara (katalog aramasi kota harcamaz)
            arama = requests.post(
                "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "bbox": ANTALYA_BBOX,
                    "datetime": "2026-09-01T00:00:00Z/2026-09-30T23:59:59Z",
                    "collections": ["sentinel-2-l2a"],
                    "limit": 10,
                },
                timeout=60,
            )
            if arama.status_code == 200:
                sahneler = arama.json().get("features", [])
                print(f"[OK] Eylul 2026'da Antalya icin {len(sahneler)}+ Sentinel-2 sahnesi bulundu.")
                for s in sahneler[:3]:
                    tarih = s["properties"].get("datetime", "?")
                    bulut = s["properties"].get("eo:cloud_cover", "?")
                    print(f"     - {tarih}  bulut: %{bulut}")
                sonuclar["Copernicus"] = True
            else:
                print(f"[HATA] Katalog aramasi basarisiz (HTTP {arama.status_code}).")
                print("       Sunucu yaniti:", arama.text[:200])
                sonuclar["Copernicus"] = False
    except requests.RequestException as e:
        print(f"[HATA] Baglanti sorunu: {e}")
        sonuclar["Copernicus"] = False


# ------------------------------------------------------------------
# 2) NASA FIRMS
# ------------------------------------------------------------------
baslik("2) NASA FIRMS (yangin noktalari)")
map_key = os.getenv("FIRMS_MAP_KEY", "").strip()
print(f"FIRMS_MAP_KEY    : {maskele(map_key)}")

if not map_key:
    print("[HATA] FIRMS_MAP_KEY .env icinde yok ya da bos.")
    sonuclar["FIRMS"] = False
else:
    bbox_metin = ",".join(str(x) for x in ANTALYA_BBOX)
    url = (
        "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{map_key}/VIIRS_SNPP_NRT/{bbox_metin}/1"
    )
    try:
        yanit = requests.get(url, timeout=60)
        metin = yanit.text.strip()
        if yanit.status_code != 200 or "Invalid" in metin[:100]:
            print(f"[HATA] FIRMS anahtari kabul edilmedi (HTTP {yanit.status_code}).")
            print("       Sunucu yaniti:", metin[:200])
            sonuclar["FIRMS"] = False
        else:
            satirlar = metin.splitlines()
            nokta = max(len(satirlar) - 1, 0)
            print(f"[OK] FIRMS yanit verdi. Son 1 gunde Antalya'da {nokta} yangin noktasi tespit edilmis.")
            if nokta == 0:
                print("     (0 olmasi normal; Ekim'de yangin az olur. Onemli olan anahtarin calismasi.)")
            sonuclar["FIRMS"] = True
    except requests.RequestException as e:
        print(f"[HATA] Baglanti sorunu: {e}")
        sonuclar["FIRMS"] = False


# ------------------------------------------------------------------
# 3) Open-Meteo (anahtar gerekmez)
# ------------------------------------------------------------------
baslik("3) Open-Meteo (hava durumu arsivi)")
try:
    yanit = requests.get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": ANTALYA_MERKEZ[0],
            "longitude": ANTALYA_MERKEZ[1],
            "start_date": "2026-08-01",
            "end_date": "2026-08-07",
            "daily": "temperature_2m_max,relative_humidity_2m_min,wind_speed_10m_max,precipitation_sum",
            "timezone": "Europe/Istanbul",
        },
        timeout=60,
    )
    if yanit.status_code == 200:
        gunluk = yanit.json()["daily"]
        print("[OK] Open-Meteo yanit verdi. Antalya merkez, Agustos 2026 ilk hafta:")
        for i, gun in enumerate(gunluk["time"]):
            print(
                f"     {gun}  maks {gunluk['temperature_2m_max'][i]} C  "
                f"min nem %{gunluk['relative_humidity_2m_min'][i]}  "
                f"ruzgar {gunluk['wind_speed_10m_max'][i]} km/s  "
                f"yagis {gunluk['precipitation_sum'][i]} mm"
            )
        sonuclar["Open-Meteo"] = True
    else:
        print(f"[HATA] Open-Meteo HTTP {yanit.status_code}: {yanit.text[:200]}")
        sonuclar["Open-Meteo"] = False
except requests.RequestException as e:
    print(f"[HATA] Baglanti sorunu: {e}")
    sonuclar["Open-Meteo"] = False


# ------------------------------------------------------------------
# Ozet
# ------------------------------------------------------------------
baslik("OZET")
for servis, ok in sonuclar.items():
    print(f"{'[OK]  ' if ok else '[HATA]'} {servis}")

if all(sonuclar.values()):
    print("\nUc servis de calisiyor. Ilk kapi gecildi, veri hattina gecebiliriz.")
else:
    print("\nHata veren servisin mesajini Claude'a yapistir (anahtarlari yapistirma).")
