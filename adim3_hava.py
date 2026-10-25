"""
Adim 3: Open-Meteo arsivinden gunluk hava verisi.

Il sinirinin icindeki (ve 0.1 derece cevresindeki) ~10 km'lik noktalar icin
gunluk maks sicaklik, min nem, maks ruzgar ve yagis indirilir.

Cikti: veri/ham/hava_gunluk.csv
Not: Open-Meteo ucretsiz kotayi korumak icin istekler arasinda bekler (~6-8 dk).
"""

import time

import numpy as np
import pandas as pd
import requests
import geopandas as gpd
from shapely import contains_xy

import ayarlar as A

URL = "https://archive-api.open-meteo.com/v1/archive"
DEGISKENLER = [
    "temperature_2m_max",
    "relative_humidity_2m_min",
    "wind_speed_10m_max",
    "precipitation_sum",
]
GRUP = 10          # bir istekteki nokta sayisi (kucuk tutuldu: buyuk istekleri sunucu kesebiliyor)
BEKLEME_SN = 15    # gruplar arasi bekleme (dakikalik limiti asmamak icin)


def hava_noktalari():
    sinir = gpd.read_file(A.SINIR_DOSYASI)
    geom = sinir.geometry.union_all() if hasattr(sinir.geometry, "union_all") else sinir.unary_union
    tampon = geom.buffer(A.HAVA_COZUNURLUK)

    r = A.HAVA_COZUNURLUK
    nx = round((A.BBOX[2] - A.BBOX[0]) / r)
    ny = round((A.BBOX[3] - A.BBOX[1]) / r)
    i = np.arange(nx)
    j = np.arange(ny)
    lon = A.BBOX[0] + (i + 0.5) * r
    lat = A.BBOX[3] - (j + 0.5) * r
    LON, LAT = np.meshgrid(lon, lat)
    J, I = np.meshgrid(j, i, indexing="ij")
    icinde = contains_xy(tampon, LON, LAT)
    return pd.DataFrame(
        {
            "nokta_id": [f"{a}_{b}" for a, b in zip(J[icinde], I[icinde])],
            "lat": LAT[icinde].round(3),
            "lon": LON[icinde].round(3),
        }
    )


def grup_indir(grup):
    params = {
        "latitude": ",".join(str(x) for x in grup["lat"]),
        "longitude": ",".join(str(x) for x in grup["lon"]),
        "start_date": A.BASLANGIC.isoformat(),
        "end_date": A.HAVA_BITIS.isoformat(),
        "daily": ",".join(DEGISKENLER),
        "timezone": "Europe/Istanbul",
    }
    for deneme in range(6):
        try:
            yanit = requests.get(URL, params=params, timeout=120)
        except requests.RequestException as e:
            bekle = 20 * (deneme + 1)
            print(f"    Baglanti koptu ({type(e).__name__}), {bekle} sn sonra tekrar deneniyor...", flush=True)
            time.sleep(bekle)
            continue
        if yanit.status_code == 200:
            veri = yanit.json()
            return veri if isinstance(veri, list) else [veri]
        if yanit.status_code == 429:
            print("    Open-Meteo limiti doldu, 70 sn bekleniyor...", flush=True)
            time.sleep(70)
            continue
        raise RuntimeError(f"Open-Meteo HTTP {yanit.status_code}: {yanit.text[:200]}")
    raise RuntimeError(
        "Open-Meteo saatlik kotasi doldu. Indirilen gruplar kaydedildi; "
        "1 saat sonra ayni komutu tekrar calistir, kaldigi yerden devam eder."
    )


def main():
    print("ADIM 3: Open-Meteo gunluk hava verisi")
    if A.HAVA_GUNLUK_DOSYASI.exists():
        print(f"  Zaten var: {A.HAVA_GUNLUK_DOSYASI.name}")
        return

    noktalar = hava_noktalari()
    gruplar = [noktalar.iloc[k:k + GRUP] for k in range(0, len(noktalar), GRUP)]
    print(f"  {len(noktalar)} nokta, {len(gruplar)} istek, {A.BASLANGIC} - {A.HAVA_BITIS}")

    # Her grup ayri dosyaya yazilir: kesilirse tekrar calistirinca kaldigi yerden devam eder
    ara_klasor = A.HAM / f"hava_parcalar_{GRUP}"
    ara_klasor.mkdir(exist_ok=True)

    for n, grup in enumerate(gruplar, 1):
        ara_dosya = ara_klasor / f"grup_{n:03d}.csv"
        if ara_dosya.exists():
            continue
        print(f"  Istek {n}/{len(gruplar)}...", flush=True)
        sonuclar = grup_indir(grup)
        parca = []
        for (_, nokta), sonuc in zip(grup.iterrows(), sonuclar):
            g = pd.DataFrame(sonuc["daily"]).rename(columns={"time": "tarih"})
            g.insert(0, "nokta_id", nokta["nokta_id"])
            g.insert(1, "lat", nokta["lat"])
            g.insert(2, "lon", nokta["lon"])
            parca.append(g)
        pd.concat(parca, ignore_index=True).to_csv(ara_dosya, index=False)
        if n < len(gruplar):
            time.sleep(BEKLEME_SN)

    hava = pd.concat(
        [pd.read_csv(ara_klasor / f"grup_{n:03d}.csv") for n in range(1, len(gruplar) + 1)],
        ignore_index=True,
    )
    hava.to_csv(A.HAVA_GUNLUK_DOSYASI, index=False)
    print(f"  Kaydedildi: {len(hava):,} satir ({A.HAVA_GUNLUK_DOSYASI.name})")


if __name__ == "__main__":
    main()
