"""
Adim 4: NASA FIRMS'ten son 6 ayin yangin noktalari (VIIRS, 375 m).

FIRMS her istekte en fazla 5 gun verir; donem 5 gunluk pencerelerle taranir.
Arsiv (SP) ve yakin-gercek-zamanli (NRT) urunler birlikte kullanilir.
Sanayi gibi sabit isi kaynaklari (type=2) ve deniz ustu noktalar (type=3) atilir.

Cikti: veri/ham/firms_noktalar.csv
"""

import io
import time
from datetime import date, timedelta

import pandas as pd
import requests

import ayarlar as A

TABAN = "https://firms.modaps.eosdis.nasa.gov/api"
PENCERE = 5
YEDEK_KAYNAKLAR = ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"]
SUTUNLAR = ["latitude", "longitude", "acq_date", "acq_time", "satellite",
            "confidence", "frp", "daynight", "type", "kaynak"]


def kaynak_araliklari():
    """Hangi VIIRS urunu hangi tarihleri kapsiyor."""
    try:
        yanit = requests.get(f"{TABAN}/data_availability/csv/{A.FIRMS_MAP_KEY}/ALL", timeout=60)
        tablo = pd.read_csv(io.StringIO(yanit.text))
        tablo = tablo[tablo["data_id"].str.startswith("VIIRS_")]
        if tablo.empty:
            raise ValueError("bos tablo")
        return [
            (r.data_id, date.fromisoformat(str(r.min_date)[:10]), date.fromisoformat(str(r.max_date)[:10]))
            for r in tablo.itertuples()
        ]
    except Exception as e:  # noqa: BLE001
        print(f"  Uyari: kapsama tablosu alinamadi ({e}); yalnizca NRT urunleri deneniyor.")
        return [(k, A.BASLANGIC - timedelta(days=PENCERE), A.BITIS + timedelta(days=PENCERE))
                for k in YEDEK_KAYNAKLAR]


def pencere_indir(kaynak, gun):
    bbox = ",".join(str(x) for x in A.BBOX)
    url = f"{TABAN}/area/csv/{A.FIRMS_MAP_KEY}/{kaynak}/{bbox}/{PENCERE}/{gun.isoformat()}"
    for deneme in range(3):
        try:
            yanit = requests.get(url, timeout=90)
        except requests.RequestException:
            time.sleep(5)
            continue
        metin = yanit.text.strip()
        if yanit.status_code == 200 and metin.startswith("latitude"):
            return pd.read_csv(io.StringIO(metin))
        if yanit.status_code == 200 and not metin:
            return pd.DataFrame()
        if "Invalid" in metin[:80] or yanit.status_code >= 400:
            if yanit.status_code == 429 or "limit" in metin.lower():
                time.sleep(60)
                continue
            return pd.DataFrame()
    return pd.DataFrame()


def main():
    print("ADIM 4: NASA FIRMS yangin noktalari")
    if A.FIRMS_DOSYASI.exists():
        print(f"  Zaten var: {A.FIRMS_DOSYASI.name}")
        return
    if not A.FIRMS_MAP_KEY:
        raise RuntimeError("FIRMS_MAP_KEY .env icinde yok.")

    # Pencere tarihinin geriye mi ileriye mi sayildigindan bagimsiz olmak icin
    # donemi her iki uctan 5 gun genis tariyoruz, sonra tam araliga kirpiyoruz.
    ilk = A.BASLANGIC - timedelta(days=PENCERE)
    son = A.BITIS + timedelta(days=PENCERE)

    parcalar = []
    for kaynak, kmin, kmax in kaynak_araliklari():
        bas, bit = max(ilk, kmin), min(son, kmax)
        if bas > bit:
            continue
        gunler = []
        g = bas
        while g <= bit:
            gunler.append(g)
            g += timedelta(days=PENCERE)
        print(f"  {kaynak}: {bas} - {bit} ({len(gunler)} istek)", flush=True)
        for g in gunler:
            df = pencere_indir(kaynak, g)
            if not df.empty:
                df["kaynak"] = kaynak
                parcalar.append(df)
            time.sleep(0.3)

    if not parcalar:
        print("  Uyari: hic yangin noktasi gelmedi. Anahtari ve tarih araligini kontrol et.")
        pd.DataFrame(columns=SUTUNLAR).to_csv(A.FIRMS_DOSYASI, index=False)
        return

    firms = pd.concat(parcalar, ignore_index=True)
    for s in SUTUNLAR:
        if s not in firms.columns:
            firms[s] = pd.NA
    firms = firms[SUTUNLAR]

    firms["acq_date"] = pd.to_datetime(firms["acq_date"]).dt.date
    firms = firms[(firms["acq_date"] >= A.BASLANGIC) & (firms["acq_date"] <= A.BITIS)]
    firms = firms[~pd.to_numeric(firms["type"], errors="coerce").isin([2, 3])]
    firms = firms[firms["confidence"].astype(str).str.lower() != "l"]  # dusuk guvenli noktalar disarida
    firms = firms.drop_duplicates(subset=["latitude", "longitude", "acq_date", "acq_time", "satellite"])

    firms.to_csv(A.FIRMS_DOSYASI, index=False)
    print(f"  Kaydedildi: {len(firms):,} yangin noktasi ({A.FIRMS_DOSYASI.name})")
    aylik = pd.to_datetime(firms["acq_date"]).dt.strftime("%Y-%m").value_counts().sort_index()
    for ay, n in aylik.items():
        print(f"     {ay}: {n}")


if __name__ == "__main__":
    main()
