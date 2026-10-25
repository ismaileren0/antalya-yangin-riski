"""
Tum veri hattini sirayla calistirir.

    python veri_hatti.py

Her adim ciktisi zaten varsa onu atlar; yarida kesilirse tekrar calistirmak yeterli.
Bir adimi bastan yapmak icin ilgili dosyayi veri/ klasorunden sil.
Toplam sure: ilk calistirmada ~15-25 dakika (cogu Open-Meteo beklemesi).
"""

import sys
import time
import traceback

import adim1_sinir_izgara
import adim2_sentinel
import adim3_hava
import adim4_firms
import adim5_birlestir

ADIMLAR = [
    ("Il siniri ve izgara", adim1_sinir_izgara.main),
    ("Sentinel-2 NDVI / NDMI", adim2_sentinel.main),
    ("Open-Meteo hava", adim3_hava.main),
    ("NASA FIRMS yangin", adim4_firms.main),
    ("Birlestirme", adim5_birlestir.main),
]

if __name__ == "__main__":
    t0 = time.time()
    for n, (ad, fonk) in enumerate(ADIMLAR, 1):
        t = time.time()
        print(f"\n[{n}/{len(ADIMLAR)}] {ad}")
        try:
            fonk()
        except Exception:  # noqa: BLE001
            print("\n" + "!" * 60)
            print(f"HATA: '{ad}' adiminda durdu. Asagidaki mesaji Claude'a yapistir:")
            print("!" * 60)
            traceback.print_exc()
            sys.exit(1)
        print(f"  ({time.time() - t:.0f} sn)")
    print(f"\nVeri hatti tamam ({(time.time() - t0) / 60:.1f} dk). Ikinci kapi gecildi.")
