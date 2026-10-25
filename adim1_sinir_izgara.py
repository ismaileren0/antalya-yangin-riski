"""
Adim 1: Antalya il sinirini indir ve ~1 km'lik izgarayi olustur.

Cikti:
  veri/islenmis/antalya_sinir.geojson
  veri/islenmis/izgara.csv  (il icindeki her hucre: hucre_id, satir, sutun, lon, lat)
"""

import numpy as np
import pandas as pd
import requests
import geopandas as gpd
from shapely import contains_xy

import ayarlar as A

GEOBOUNDARIES_API = "https://www.geoboundaries.org/api/current/gbOpen/TUR/ADM1/"


def sinir_indir():
    if A.SINIR_DOSYASI.exists():
        print(f"  Sinir zaten var: {A.SINIR_DOSYASI.name}")
        return gpd.read_file(A.SINIR_DOSYASI)

    print("  geoBoundaries'ten Turkiye il sinirlari indiriliyor...")
    meta = requests.get(GEOBOUNDARIES_API, timeout=60).json()
    url = meta.get("simplifiedGeometryGeoJSON") or meta["gjDownloadURL"]
    geojson = requests.get(url, timeout=180).json()
    iller = gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4326")

    ad_sutunu = "shapeName" if "shapeName" in iller.columns else iller.columns[0]
    antalya = iller[iller[ad_sutunu].astype(str).str.strip().str.lower() == "antalya"]
    if antalya.empty:
        raise RuntimeError(
            f"Antalya bulunamadi. Mevcut adlar: {sorted(iller[ad_sutunu].astype(str))[:10]}..."
        )
    antalya = antalya[[ad_sutunu, "geometry"]].rename(columns={ad_sutunu: "ad"})
    antalya.to_file(A.SINIR_DOSYASI, driver="GeoJSON")
    print(f"  Kaydedildi: {A.SINIR_DOSYASI.name}")
    return antalya


def izgara_olustur(sinir):
    geom = sinir.geometry.union_all() if hasattr(sinir.geometry, "union_all") else sinir.unary_union

    sutunlar = np.arange(A.GENISLIK)
    satirlar = np.arange(A.YUKSEKLIK)
    lon = A.BBOX[0] + (sutunlar + 0.5) * A.COZUNURLUK
    lat = A.BBOX[3] - (satirlar + 0.5) * A.COZUNURLUK  # 0. satir en kuzeyde
    LON, LAT = np.meshgrid(lon, lat)
    SAT, SUT = np.meshgrid(satirlar, sutunlar, indexing="ij")

    icinde = contains_xy(geom, LON, LAT)
    izgara = pd.DataFrame(
        {
            "satir": SAT[icinde],
            "sutun": SUT[icinde],
            "lon": LON[icinde].round(5),
            "lat": LAT[icinde].round(5),
        }
    )
    izgara.insert(0, "hucre_id", izgara["satir"] * A.GENISLIK + izgara["sutun"])
    izgara.to_csv(A.IZGARA_DOSYASI, index=False)
    print(f"  Izgara: {len(izgara):,} hucre il sinirinin icinde ({A.GENISLIK}x{A.YUKSEKLIK} kutudan).")
    return izgara


def main():
    print("ADIM 1: Il siniri ve izgara")
    sinir = sinir_indir()
    izgara_olustur(sinir)


if __name__ == "__main__":
    main()
