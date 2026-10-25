"""
Adim 5: Tum veriyi ayni izgarada birlestir.

Her (hucre, ay) icin tek satir:
  NDVI, NDMI, gecerli goruntu sayisi           (Sentinel-2)
  ort. maks sicaklik, ort. min nem, ort. maks ruzgar,
  toplam yagis, kuru gun sayisi                (Open-Meteo)
  yangin noktasi sayisi, yangin var/yok        (FIRMS)

Cikti: veri/islenmis/hucre_ay.csv  -> risk skoru ve uygulama bu dosyayi okur.
"""

import numpy as np
import pandas as pd
import rasterio

import ayarlar as A


def sentinel_ekle(izgara):
    parcalar = []
    for etiket, _, _ in A.AYLAR:
        dosya = A.sentinel_dosyasi(etiket)
        df = izgara[["hucre_id"]].copy()
        df["ay"] = etiket
        if dosya.exists():
            with rasterio.open(dosya) as src:
                bantlar = src.read()  # (3, satir, sutun)
            s, c = izgara["satir"].to_numpy(), izgara["sutun"].to_numpy()
            df["ndvi"] = bantlar[0, s, c]
            df["ndmi"] = bantlar[1, s, c]
            df["gecerli_goruntu"] = bantlar[2, s, c]
        else:
            print(f"  Uyari: {dosya.name} yok, {etiket} icin uydu degerleri bos kalacak.")
            df["ndvi"] = np.nan
            df["ndmi"] = np.nan
            df["gecerli_goruntu"] = 0
        parcalar.append(df)
    return pd.concat(parcalar, ignore_index=True)


def bos_aylari_doldur(df):
    """Bulut yuzunden bos kalan hucreyi bir onceki ayin degeriyle doldur ve isaretle."""
    df = df.sort_values(["hucre_id", "ay"])
    df["uydu_dolduruldu"] = df["ndmi"].isna()
    for s in ("ndvi", "ndmi"):
        df[s] = df.groupby("hucre_id")[s].ffill()
    df.loc[df["ndmi"].isna(), "uydu_dolduruldu"] = False  # doldurulamadiysa hala bos
    return df


def hava_aylik():
    hava = pd.read_csv(A.HAVA_GUNLUK_DOSYASI)
    hava["ay"] = hava["tarih"].str[:7]
    hava["kuru_gun"] = (hava["precipitation_sum"].fillna(0) < 1).astype(int)
    aylik = hava.groupby(["nokta_id", "ay"]).agg(
        sicaklik_maks=("temperature_2m_max", "mean"),
        nem_min=("relative_humidity_2m_min", "mean"),
        ruzgar_maks=("wind_speed_10m_max", "mean"),
        yagis_toplam=("precipitation_sum", "sum"),
        kuru_gun=("kuru_gun", "sum"),
        hava_gun_sayisi=("tarih", "count"),
    ).reset_index()
    return aylik.round(2)


def hava_nokta_id(izgara):
    r = A.HAVA_COZUNURLUK
    j = np.floor((A.BBOX[3] - izgara["lat"]) / r).astype(int)
    i = np.floor((izgara["lon"] - A.BBOX[0]) / r).astype(int)
    return j.astype(str) + "_" + i.astype(str)


def firms_aylik():
    firms = pd.read_csv(A.FIRMS_DOSYASI)
    if firms.empty:
        return pd.DataFrame(columns=["hucre_id", "ay", "yangin_sayisi"])
    sut = np.floor((firms["longitude"] - A.BBOX[0]) / A.COZUNURLUK).astype(int)
    sat = np.floor((A.BBOX[3] - firms["latitude"]) / A.COZUNURLUK).astype(int)
    icinde = (sut >= 0) & (sut < A.GENISLIK) & (sat >= 0) & (sat < A.YUKSEKLIK)
    firms = firms[icinde].copy()
    firms["hucre_id"] = sat[icinde] * A.GENISLIK + sut[icinde]
    firms["ay"] = firms["acq_date"].astype(str).str[:7]
    return firms.groupby(["hucre_id", "ay"]).size().rename("yangin_sayisi").reset_index()


def main():
    print("ADIM 5: Birlestirme")
    izgara = pd.read_csv(A.IZGARA_DOSYASI)
    izgara["nokta_id"] = hava_nokta_id(izgara)

    df = sentinel_ekle(izgara)
    df = bos_aylari_doldur(df)
    df = df.merge(izgara, on="hucre_id", how="left")
    df = df.merge(hava_aylik(), on=["nokta_id", "ay"], how="left")
    df = df.merge(firms_aylik(), on=["hucre_id", "ay"], how="left")
    df["yangin_sayisi"] = df["yangin_sayisi"].fillna(0).astype(int)
    df["yangin_var"] = (df["yangin_sayisi"] > 0).astype(int)

    sira = ["hucre_id", "ay", "satir", "sutun", "lon", "lat", "nokta_id",
            "ndvi", "ndmi", "gecerli_goruntu", "uydu_dolduruldu",
            "sicaklik_maks", "nem_min", "ruzgar_maks", "yagis_toplam", "kuru_gun", "hava_gun_sayisi",
            "yangin_sayisi", "yangin_var"]
    df = df[sira].sort_values(["ay", "hucre_id"])
    df["ndvi"] = df["ndvi"].round(4)
    df["ndmi"] = df["ndmi"].round(4)
    df.to_csv(A.BIRLESIK_DOSYA, index=False)

    print(f"  Kaydedildi: {len(df):,} satir ({A.BIRLESIK_DOSYA.name})")
    ozet = df.groupby("ay").agg(
        ndmi_dolu=("ndmi", lambda s: f"%{s.notna().mean() * 100:.0f}"),
        ort_ndmi=("ndmi", "mean"),
        ort_sicaklik=("sicaklik_maks", "mean"),
        ort_min_nem=("nem_min", "mean"),
        yangin_hucre=("yangin_var", "sum"),
    ).round(2)
    print(ozet.to_string())


if __name__ == "__main__":
    main()
