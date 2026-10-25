"""
Adim 6: Risk skorlari ve ogrenen model (AI).

1) Kural tabanli skor: kuruluk, sicaklik, nem, ruzgar, yagis ve yakit miktarindan
   agirlikli formul.
2) Ogrenen model: Random Forest, "bu hucrede bu ay yangin tespit edildi mi?"
   sorusunu 6 aylik gercek FIRMS verisinden ogrenir.
3) Durust dogrulama: model Nisan-Agustos ile egitilir, hic gormedigi
   Eylul-Ekim'de test edilir. Iki yontem ayni olcutle karsilastirilir:
   "yangin goren hucrelerin yuzde kaci, o ayin en riskli %20'lik dilimindeydi?"
4) Dashboard'un ihtiyac duydugu tum veri dashboard/veri/ klasorune yazilir;
   dashboard bu klasorle tek basina calisir (API anahtari gerekmez).

Calistirma:  python adim6_risk_model.py
"""

import json
import shutil

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

import ayarlar as A

OZELLIKLER = ["ndmi", "ndvi", "sicaklik_maks", "nem_min", "ruzgar_maks", "yagis_toplam", "kuru_gun"]
OZELLIK_ADLARI = {
    "ndmi": "Bitki nemi (NDMI)",
    "ndvi": "Bitki yoğunluğu (NDVI)",
    "sicaklik_maks": "Maks. sıcaklık",
    "nem_min": "Min. bağıl nem",
    "ruzgar_maks": "Maks. rüzgâr",
    "yagis_toplam": "Aylık yağış",
    "kuru_gun": "Kuru gün sayısı",
}
TEST_AYLARI = ["2026-09", "2026-10"]  # model bunlari egitimde hic gormez

DASHBOARD = A.KOK / "dashboard"
DASH_VERI = DASHBOARD / "veri"


# ------------------------------------------------------------------
# Yardimcilar
# ------------------------------------------------------------------
def normalle(seri, alt, ust):
    return ((seri - alt) / (ust - alt)).clip(0, 1)


def kural_skoru(df, sinirlar):
    n = {k: normalle(df[k], *sinirlar[k]) for k in ("ndmi", "sicaklik_maks", "nem_min", "ruzgar_maks", "yagis_toplam")}
    kuruluk = 1 - n["ndmi"]
    ham = 0.35 * kuruluk + 0.25 * n["sicaklik_maks"] + 0.20 * (1 - n["nem_min"]) + 0.20 * n["ruzgar_maks"]
    yagis_cezasi = 1 - 0.3 * n["yagis_toplam"]
    # Yakit: NDVI cok dusukse (kaya, yerlesim, su) yanacak bitki yok; NDMI'nin dusuk
    # cikmasi orada kuruluk degil, bitki yoklugu demektir.
    yakit = ((df["ndvi"] - 0.10) / 0.30).clip(0, 1)
    return (100 * ham * yagis_cezasi * (0.3 + 0.7 * yakit)).round(1)


def yuzdelik(seri):
    """0-100 arasi goreli risk: tum hucre-aylar icindeki sira."""
    return (seri.rank(pct=True) * 100).round(1)


def yakalama_orani(df, skor_sutunu, dilim=0.20):
    """Yangin goren hucrelerin yuzde kaci, kendi ayinin en riskli %20'sinde?"""
    yakalanan, toplam = 0, 0
    for _, g in df.groupby("ay"):
        if g["yangin_var"].sum() == 0:
            continue
        esik = g[skor_sutunu].quantile(1 - dilim)
        yangin = g[g["yangin_var"] == 1]
        yakalanan += int((yangin[skor_sutunu] >= esik).sum())
        toplam += len(yangin)
    return (round(100 * yakalanan / toplam, 1) if toplam else None), toplam


def auc(df, skor_sutunu):
    if df["yangin_var"].nunique() < 2:
        return None
    return round(float(roc_auc_score(df["yangin_var"], df[skor_sutunu])), 3)


def model_kur():
    return RandomForestClassifier(
        n_estimators=300,
        max_depth=10,
        min_samples_leaf=20,
        class_weight="balanced_subsample",
        n_jobs=-1,
        random_state=42,
    )


# ------------------------------------------------------------------
def main():
    print("ADIM 6: Risk skorlari ve ogrenen model")
    df = pd.read_csv(A.BIRLESIK_DOSYA)
    tam = df.dropna(subset=OZELLIKLER).copy()
    print(f"  {len(tam):,} / {len(df):,} hucre-ay tum degiskenlere sahip; model bunlarla calisir.")
    print(f"  Yangin goren hucre-ay sayisi: {int(tam['yangin_var'].sum())}")

    sinirlar = {k: (float(tam[k].quantile(0.02)), float(tam[k].quantile(0.98))) for k in OZELLIKLER}

    # 1) Kural tabanli skor
    tam["kural_skor"] = kural_skoru(tam, sinirlar)

    # 2) Durust test: Nisan-Agustos ile egit, Eylul-Ekim'de dene
    egitim = tam[~tam["ay"].isin(TEST_AYLARI)]
    test = tam[tam["ay"].isin(TEST_AYLARI)].copy()
    sonuc_test = {}
    if egitim["yangin_var"].sum() >= 10 and test["yangin_var"].sum() >= 5:
        m_test = model_kur().fit(egitim[OZELLIKLER], egitim["yangin_var"])
        test["model_olasilik"] = m_test.predict_proba(test[OZELLIKLER])[:, 1]
        for ad, sutun in (("kural", "kural_skor"), ("model", "model_olasilik")):
            oran, n = yakalama_orani(test, sutun)
            sonuc_test[ad] = {"yakalama_yuzde": oran, "auc": auc(test, sutun)}
        sonuc_test["yangin_sayisi"] = n
        print("  Test (Eylul-Ekim, model egitimde gormedi):")
        print(f"    Kural  : yangin hucrelerinin %{sonuc_test['kural']['yakalama_yuzde']}'i en riskli %20'de, AUC {sonuc_test['kural']['auc']}")
        print(f"    Model  : yangin hucrelerinin %{sonuc_test['model']['yakalama_yuzde']}'i en riskli %20'de, AUC {sonuc_test['model']['auc']}")
        print("    (Rastgele tahmin: %20 ve AUC 0.5)")
    else:
        print("  Uyari: test icin yeterli yangin yok; zaman bazli test atlandi.")

    # 3) Harita: her ay, O AYI HIC GORMEMIS bir modelle tahmin edilir
    #    (ayi disarida birakan capraz dogrulama). Boylece haritadaki her
    #    aylik basari orani, modelin ezberi degil gercek bir test sonucudur.
    print("  Harita icin her ay, o ayi gormemis modelle tahmin ediliyor...", flush=True)
    tam["model_olasilik"] = np.nan
    for ay in sorted(tam["ay"].unique()):
        egit = tam[tam["ay"] != ay]
        if egit["yangin_var"].sum() < 10:
            continue
        m_ay = model_kur().fit(egit[OZELLIKLER], egit["yangin_var"])
        secim = tam["ay"] == ay
        tam.loc[secim, "model_olasilik"] = m_ay.predict_proba(tam.loc[secim, OZELLIKLER])[:, 1]
    tam["risk_model"] = yuzdelik(tam["model_olasilik"])
    model_ayd, _ = yakalama_orani(tam, "model_olasilik")
    kural_ayd, _ = yakalama_orani(tam, "kural_skor")
    print(f"    Ay disarida (7 ay): model %{model_ayd}, kural %{kural_ayd} yakalama")

    # 4) Son model: tum aylarla egitilir; degisken onemleri ve ileride yeni aylar icin
    model = model_kur().fit(tam[OZELLIKLER], tam["yangin_var"])
    tam["risk_kural"] = yuzdelik(tam["kural_skor"])
    joblib.dump(model, A.ISLENMIS / "risk_modeli.joblib")

    onem = pd.Series(model.feature_importances_, index=OZELLIKLER).sort_values(ascending=False)
    print("  Degisken onemleri (model neye bakiyor):")
    for k, v in onem.items():
        print(f"    {OZELLIK_ADLARI[k]:<24} %{v * 100:.0f}")

    kural_tum, _ = yakalama_orani(tam, "kural_skor")

    # 5) Dashboard verisi
    DASH_VERI.mkdir(parents=True, exist_ok=True)
    sutunlar = ["hucre_id", "ay", "satir", "sutun", "lat", "lon", "uydu_dolduruldu",
                *OZELLIKLER, "yangin_sayisi", "kural_skor", "risk_kural", "risk_model"]
    app = df[["hucre_id", "ay", "satir", "sutun", "lat", "lon", "uydu_dolduruldu", *OZELLIKLER, "yangin_sayisi"]].merge(
        tam[["hucre_id", "ay", "kural_skor", "risk_kural", "risk_model"]], on=["hucre_id", "ay"], how="left"
    )[sutunlar]
    for k in ("ndmi", "ndvi"):
        app[k] = app[k].round(3)
    for k in ("sicaklik_maks", "nem_min", "ruzgar_maks", "yagis_toplam"):
        app[k] = app[k].round(1)
    app.to_csv(DASH_VERI / "app_veri.csv.gz", index=False, compression="gzip")

    firms = pd.read_csv(A.FIRMS_DOSYASI)
    if not firms.empty:
        firms = firms[["latitude", "longitude", "acq_date", "acq_time", "frp", "confidence", "daynight"]]
    firms.to_csv(DASH_VERI / "firms.csv", index=False)
    shutil.copy(A.SINIR_DOSYASI, DASH_VERI / "sinir.geojson")

    ozet = {
        "izgara": {"bbox": list(A.BBOX), "cozunurluk": A.COZUNURLUK,
                   "genislik": A.GENISLIK, "yukseklik": A.YUKSEKLIK},
        "donem": {"baslangic": A.BASLANGIC.isoformat(), "bitis": A.BITIS.isoformat()},
        "test_aylari": TEST_AYLARI,
        "test": sonuc_test,
        "kural_tum_aylar_yakalama": kural_tum,
        "ay_disarida": {"model_yakalama_yuzde": model_ayd, "kural_yakalama_yuzde": kural_ayd},
        "degisken_onemi": {k: round(float(v), 4) for k, v in onem.items()},
        "degisken_adlari": OZELLIK_ADLARI,
        "normalleme_sinirlari": sinirlar,
        "satir_sayisi": int(len(app)),
        "yangin_hucre_ay": int(tam["yangin_var"].sum()),
    }
    with open(DASH_VERI / "model_sonuc.json", "w", encoding="utf-8") as f:
        json.dump(ozet, f, ensure_ascii=False, indent=2)

    boyut = sum(p.stat().st_size for p in DASH_VERI.iterdir()) / 1e6
    print(f"  Dashboard verisi yazildi: {DASH_VERI} ({boyut:.1f} MB)")
    print("  Simdi dashboard'u ac:  streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
