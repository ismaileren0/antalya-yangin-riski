# Antalya Yangın Riski Haritası

Antalya ili için son 6 ayın (18 Nisan – 18 Ekim 2026) uydu, hava ve yangın verisini
~1 km'lik ortak bir ızgarada birleştirir; kural tabanlı bir formül ve öğrenen bir AI
modeliyle aylık yangın riski haritası üretir ve bunu bir dashboard'da gösterir.

## Kurulum (Windows 11)

```
cd antalya-fire-risk
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

`.env` dosyası bu klasörde olmalı (GitHub'a yüklenmez):

```
SH_CLIENT_ID=...
SH_CLIENT_SECRET=...
FIRMS_MAP_KEY=...
```

## Çalıştırma

```
python veri_hatti.py            # 1-5: veriyi indir ve birleştir (~20 dk, bir kez)
python adim6_risk_model.py      # 6: risk skorları, AI modeli, dashboard verisi (~1 dk)
streamlit run dashboard/app.py  # dashboard (tarayıcıda açılır)
```

## Adımlar ve çıktılar

| Adım | Betik | Çıktı |
| --- | --- | --- |
| 1 | `adim1_sinir_izgara.py` | İl sınırı, ~20.500 hücrelik ızgara |
| 2 | `adim2_sentinel.py` | Aylık NDVI / NDMI GeoTIFF (Sentinel-2) |
| 3 | `adim3_hava.py` | Günlük hava (Open-Meteo) |
| 4 | `adim4_firms.py` | Yangın noktaları (NASA FIRMS, VIIRS) |
| 5 | `adim5_birlestir.py` | `veri/islenmis/hucre_ay.csv` |
| 6 | `adim6_risk_model.py` | `dashboard/veri/` (dashboard'un tek ihtiyacı) |

## Dashboard'u internete koymak

`dashboard/` klasörü kendi başına çalışır: yalnızca `dashboard/veri/` içindeki dosyaları okur,
API anahtarı gerektirmez. Streamlit Community Cloud'da ana dosya olarak `dashboard/app.py`
seçilir; bağımlılıklar `dashboard/requirements.txt` dosyasından kurulur.

## Veri kaynakları

- Sentinel-2 L2A — Copernicus Data Space Ecosystem (Sentinel Hub Process API)
- Hava — Open-Meteo Historical Weather API (ticari olmayan kullanım)
- Yangın noktaları — NASA FIRMS, VIIRS 375 m
- İl sınırı — geoBoundaries (CC BY 4.0)
- Harita altlığı — Esri, OpenStreetMap katkıda bulunanlar
