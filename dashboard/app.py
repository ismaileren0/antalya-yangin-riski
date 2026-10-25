"""
Antalya Yangın Riski — dashboard

Yerelde:   streamlit run dashboard/app.py
Bulutta:   Streamlit Community Cloud, ana dosya dashboard/app.py

Yalnızca dashboard/veri/ klasörünü okur; API anahtarı gerektirmez.
"""

import json
import math
from pathlib import Path

import altair as alt
import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from aciklama import aciklama_uret, bos, risk_sinifi
from bildirim import KITLELER, ay_araligi, bildirim_metni, telefon_karti, uyari_gerekli

KLASOR = Path(__file__).resolve().parent / "veri"
OZELLIKLER = ["ndmi", "ndvi", "sicaklik_maks", "nem_min", "ruzgar_maks", "yagis_toplam", "kuru_gun"]
AY_ADLARI = {"01": "Ocak", "02": "Şubat", "03": "Mart", "04": "Nisan", "05": "Mayıs", "06": "Haziran",
             "07": "Temmuz", "08": "Ağustos", "09": "Eylül", "10": "Ekim", "11": "Kasım", "12": "Aralık"}

KATMANLAR = {
    "AI risk modeli": "risk_model",
    "Kural tabanlı formül": "risk_kural",
    "Bitki nemi (NDMI)": "ndmi",
}
RISK_RENKLERI = [(0, (26, 152, 80)), (40, (254, 224, 139)), (70, (253, 141, 60)),
                 (90, (215, 48, 39)), (100, (110, 0, 30))]
NDMI_RENKLERI = [(-0.05, (140, 81, 10)), (0.08, (246, 232, 195)), (0.30, (1, 102, 94))]

st.set_page_config(page_title="Antalya Yangın Riski", layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """<style>
    .block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
    [data-testid="stMetricValue"] {font-size: 1.6rem;}
    .lejant {height: 12px; border-radius: 6px; margin: 4px 0 2px 0;}
    .lejant-yazi {display: flex; justify-content: space-between; font-size: 0.78rem; opacity: 0.75;}
    </style>""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------
# Veri
# ------------------------------------------------------------------
@st.cache_data(show_spinner="Veri yükleniyor...")
def yukle():
    df = pd.read_csv(KLASOR / "app_veri.csv.gz")
    firms = pd.read_csv(KLASOR / "firms.csv")
    sinir = json.loads((KLASOR / "sinir.geojson").read_text(encoding="utf-8"))
    sonuc = json.loads((KLASOR / "model_sonuc.json").read_text(encoding="utf-8"))
    if not firms.empty:
        firms["ay"] = firms["acq_date"].astype(str).str[:7]
        g = sonuc["izgara"]
        sut = np.floor((firms["longitude"] - g["bbox"][0]) / g["cozunurluk"]).astype(int)
        sat = np.floor((g["bbox"][3] - firms["latitude"]) / g["cozunurluk"]).astype(int)
        firms = firms[(sat * g["genislik"] + sut).isin(set(df["hucre_id"]))]  # yalnizca il icindekiler
    return df, firms, sinir, sonuc


def ay_etiketi(ay):
    return f"{AY_ADLARI[ay[5:7]]} {ay[:4]}"


def tr(x, basamak=1):
    return f"{x:.{basamak}f}".replace(".", ",")


def ay_grafigi(veri, tur, renk, baslik_y, yukseklik=220):
    """Aylari takvim sirasinda, yatay etiketle cizen kucuk grafik. veri: index=ay ('2026-04'), sutunlar=seriler."""
    uzun = veri.reset_index(names="ay").melt("ay", var_name="seri", value_name="deger")
    uzun["etiket"] = uzun["ay"].map(lambda a: AY_ADLARI[a[5:7]][:3])
    sira = [AY_ADLARI[a[5:7]][:3] for a in sorted(veri.index)]
    x = alt.X("etiket:N", sort=sira, title=None, axis=alt.Axis(labelAngle=0))
    y = alt.Y("deger:Q", title=baslik_y)
    if tur == "bar":
        grafik = alt.Chart(uzun).mark_bar(color=renk, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(x=x, y=y, tooltip=["etiket", "deger"])
    else:
        renkler = alt.Color("seri:N", title=None, scale=alt.Scale(range=renk), legend=alt.Legend(orient="bottom"))
        grafik = alt.Chart(uzun).mark_line(point=True).encode(x=x, y=y, color=renkler, tooltip=["etiket", "seri", "deger"])
    return grafik.properties(height=yukseklik)


def renklendir(dizi, duraklar):
    xs = [d[0] for d in duraklar]
    rgba = np.zeros(dizi.shape + (4,), dtype=np.uint8)
    gecerli = np.isfinite(dizi)
    for k in range(3):
        rgba[..., k][gecerli] = np.interp(dizi[gecerli], xs, [d[1][k] for d in duraklar]).astype(np.uint8)
    rgba[..., 3][gecerli] = 255
    return rgba


def lejant(duraklar, sol, sag):
    renkler = ", ".join(f"rgb{d[1]} {100 * (d[0] - duraklar[0][0]) / (duraklar[-1][0] - duraklar[0][0]):.0f}%" for d in duraklar)
    return (f'<div class="lejant" style="background: linear-gradient(to right, {renkler});"></div>'
            f'<div class="lejant-yazi"><span>{sol}</span><span>{sag}</span></div>')


@st.cache_data
def katman_goruntusu(ay, sutun):
    df, _, _, sonuc = yukle()
    g = sonuc["izgara"]
    ay_df = df[df["ay"] == ay]
    dizi = np.full((g["yukseklik"], g["genislik"]), np.nan)
    dizi[ay_df["satir"].to_numpy(), ay_df["sutun"].to_numpy()] = ay_df[sutun].to_numpy(dtype=float)
    return renklendir(dizi, NDMI_RENKLERI if sutun == "ndmi" else RISK_RENKLERI)


def yakalama(ay_df, sutun):
    yangin = ay_df[ay_df["yangin_sayisi"] > 0]
    if yangin.empty or ay_df[sutun].isna().all():
        return None
    esik = ay_df[sutun].quantile(0.80)
    return 100 * (yangin[sutun] >= esik).mean()


def hucre_bul(lat, lon, g):
    b, r = g["bbox"], g["cozunurluk"]
    sutun = math.floor((lon - b[0]) / r)
    satir = math.floor((b[3] - lat) / r)
    if 0 <= sutun < g["genislik"] and 0 <= satir < g["yukseklik"]:
        return satir * g["genislik"] + sutun
    return None


# ------------------------------------------------------------------
# Başlangıç
# ------------------------------------------------------------------
if not (KLASOR / "app_veri.csv.gz").exists():
    st.error("Dashboard verisi bulunamadı. Önce proje klasöründe `python adim6_risk_model.py` çalıştır.")
    st.stop()

df, firms, sinir, sonuc = yukle()
g = sonuc["izgara"]
aylar = sorted(df["ay"].unique())
onem = sonuc["degisken_onemi"]
adlar = sonuc["degisken_adlari"]

# ------------------------------------------------------------------
# Kenar çubuğu
# ------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Antalya Yangın Riski")
    st.caption("Uydu + hava + yapay zekâ ile aylık orman yangını risk haritası")
    ay = st.select_slider("Ay", options=aylar, value=aylar[-3] if len(aylar) >= 3 else aylar[-1],
                          format_func=ay_etiketi)
    katman_adi = st.radio("Harita katmanı", list(KATMANLAR), index=0)
    katman = KATMANLAR[katman_adi]
    yangin_goster = st.checkbox("Uydunun tespit ettiği yangınları göster", value=True)
    opaklik = st.slider("Katman opaklığı", 0.2, 1.0, 0.75, 0.05)
    st.divider()
    st.caption(
        f"Dönem: {sonuc['donem']['baslangic']} – {sonuc['donem']['bitis']}  \n"
        "Kaynaklar: Copernicus Sentinel-2, Open-Meteo, NASA FIRMS (VIIRS), geoBoundaries"
    )

ay_df = df[df["ay"] == ay]
firms_ay = firms[firms["ay"] == ay] if not firms.empty else firms
risk_sutunu = katman if katman != "ndmi" else "risk_model"

# ------------------------------------------------------------------
# Başlık ve göstergeler
# ------------------------------------------------------------------
st.markdown(f"## Antalya orman yangını riski · {ay_etiketi(ay)}")
st.caption("Haritada bir noktaya tıkla: o 1 km²'lik alanın riskini ve nedenlerini sağ panelde gör.")

k1, k2, k3, k4 = st.columns(4)
cok_yuksek = int((ay_df[risk_sutunu] >= 90).sum())
k1.metric("Çok yüksek riskli alan", f"≈ {cok_yuksek:,} km²".replace(",", "."))
k2.metric("Uydunun tespit ettiği yangın noktası", f"{len(firms_ay):,}".replace(",", "."))
oran = yakalama(ay_df, risk_sutunu)
k3.metric("Riskli bölgede yakalanan yangın",
          "—" if oran is None else f"%{oran:.0f}",
          help="Bu ay yangın görülen alanların yüzde kaçı, haritanın en riskli %20'lik dilimindeydi. Rastgele tahmin %20 verir. "
               "AI katmanında her ay, o ayı eğitimde hiç görmemiş bir modelle hesaplanır; yani bu bir ezber değil, test sonucudur.")
k4.metric("İl geneli bitki nemi (NDMI)", f"{ay_df['ndmi'].median():.2f}".replace(".", ","),
          help="Bitki nemi. Düşük değer kuru bitki örtüsü demek.")

# ------------------------------------------------------------------
# Harita + hücre paneli
# ------------------------------------------------------------------
sol, sag = st.columns([2.1, 1], gap="large")

with sol:
    b = g["bbox"]
    m = folium.Map(location=[36.85, 30.9], zoom_start=8, control_scale=True,
                   tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
                   attr="Esri, HERE, Garmin, © OpenStreetMap katkıda bulunanlar")
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", show=False).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, Maxar, Earthstar Geographics", name="Uydu görüntüsü", show=False,
    ).add_to(m)
    folium.raster_layers.ImageOverlay(
        image=katman_goruntusu(ay, katman), bounds=[[b[1], b[0]], [b[3], b[2]]],
        opacity=opaklik, mercator_project=True, name=katman_adi,
    ).add_to(m)
    folium.GeoJson(sinir, name="İl sınırı",
                   style_function=lambda f: {"color": "#333333", "weight": 1.5, "fill": False}).add_to(m)

    if yangin_goster and not firms_ay.empty:
        for r in firms_ay.itertuples():
            folium.CircleMarker(
                location=[r.latitude, r.longitude], radius=3, color="#111111", weight=1,
                fill=True, fill_color="#ffd60a", fill_opacity=0.95,
                tooltip=f"Yangın noktası · {r.acq_date} · FRP {r.frp} MW",
            ).add_to(m)

    secili = st.session_state.get("secili")
    if secili is not None:
        s_sat, s_sut = divmod(secili, g["genislik"])
        r_ = g["cozunurluk"]
        folium.Rectangle(
            bounds=[[b[3] - (s_sat + 1) * r_, b[0] + s_sut * r_], [b[3] - s_sat * r_, b[0] + (s_sut + 1) * r_]],
            color="#1d4ed8", weight=3, fill=False,
        ).add_to(m)

    folium.LayerControl(position="topright", collapsed=True).add_to(m)
    cikti = st_folium(m, height=600, use_container_width=True, returned_objects=["last_clicked"], key="harita")
    if katman == "ndmi":
        st.markdown(lejant(NDMI_RENKLERI, "Kuru", "Nemli"), unsafe_allow_html=True)
    else:
        st.markdown(lejant(RISK_RENKLERI, "Düşük risk", "Çok yüksek risk"), unsafe_allow_html=True)

    if cikti and cikti.get("last_clicked"):
        yeni = hucre_bul(cikti["last_clicked"]["lat"], cikti["last_clicked"]["lng"], g)
        if yeni is not None and yeni != st.session_state.get("secili"):
            st.session_state["secili"] = yeni
            st.rerun()

with sag:
    secili = st.session_state.get("secili")
    satir = ay_df[ay_df["hucre_id"] == secili] if secili is not None else ay_df.iloc[0:0]
    if satir.empty:
        st.markdown("#### Bir alan seç")
        st.info("Haritada il sınırı içinde bir noktaya tıkla.")
        st.markdown(f"**{ay_etiketi(ay)} ayının en riskli alanları**")
        en = ay_df.nlargest(8, risk_sutunu)[["lat", "lon", risk_sutunu, "ndmi"]].copy()
        en.columns = ["Enlem", "Boylam", "Risk", "NDMI"]
        en = en.round({"Enlem": 2, "Boylam": 2, "Risk": 0, "NDMI": 2})
        st.dataframe(en, hide_index=True, width="stretch")
    else:
        h = satir.iloc[0].to_dict()
        st.markdown(f"#### Seçilen alan · {h['lat']:.2f}° K, {h['lon']:.2f}° D")
        c1, c2 = st.columns(2)
        c1.metric("AI modeli", "—" if bos(h["risk_model"]) else f"{h['risk_model']:.0f}/100",
                  risk_sinifi(h["risk_model"]), delta_color="off")
        c2.metric("Formül", "—" if bos(h["risk_kural"]) else f"{h['risk_kural']:.0f}/100",
                  risk_sinifi(h["risk_kural"]), delta_color="off")

        ortanca = ay_df[OZELLIKLER].median().to_dict()
        st.markdown(aciklama_uret(h, ortanca, onem))

        # --- Uyari bildirimi ---
        st.markdown("**🔔 Bu bölge için uyarı bildirimi**")
        kitle = st.selectbox("Kime gidecek?", KITLELER, key="kitle_hucre")
        konum = f"{h['lat']:.2f}° K, {h['lon']:.2f}° D çevresi".replace(".", ",")
        if st.button("Bildirim gönder", type="primary", key="bildirim_hucre", width="stretch"):
            if bos(h["risk_model"]):
                st.warning("Bu alan için risk hesaplanamadığından bildirim oluşturulamadı.")
            else:
                baslik, govde = bildirim_metni(h["risk_model"], ay, kitle, konum)
                uyari = uyari_gerekli(h["risk_model"])
                st.toast(baslik, icon="🔥" if uyari else "ℹ️")
                st.markdown(telefon_karti(baslik, govde, uyari), unsafe_allow_html=True)
                st.caption("Prototip: bildirim burada önizleniyor. Gerçek sürümde bu bölgeye kayıtlı "
                           "kullanıcıların telefonuna gönderilecek.")

        gecmis = df[df["hucre_id"] == secili].sort_values("ay")
        if len(gecmis) > 1:
            st.markdown("**6 ay boyunca bu alan**")
            seri = gecmis.set_index("ay")[["risk_model", "risk_kural"]]
            seri.columns = ["AI modeli", "Formül"]
            st.altair_chart(ay_grafigi(seri, "line", ["#e4572e", "#4c78a8"], "Risk (0–100)", 200)
                            .encode(y=alt.Y("deger:Q", title="Risk (0–100)", scale=alt.Scale(domain=[0, 100]))),
                            width="stretch")

        with st.expander("Ham değerler"):
            tablo = pd.DataFrame({
                "Değişken": [adlar[k] for k in OZELLIKLER] + ["Yangın noktası"],
                "Bu alan": [h[k] for k in OZELLIKLER] + [h["yangin_sayisi"]],
                "İl ortancası": [ortanca[k] for k in OZELLIKLER] + [None],
            })
            st.dataframe(tablo.round(2), hide_index=True, width="stretch")
            if h.get("uydu_dolduruldu") in (True, "True", 1):
                st.caption("Bu ay bulut nedeniyle uydu değeri bir önceki aydan taşındı.")

# ------------------------------------------------------------------
# Alt sekmeler
# ------------------------------------------------------------------
st.divider()
t0, t1, t2, t3 = st.tabs(["🔔 Uyarı bildirimleri", "AI'ın çözümdeki rolü", "Doğrulama", "Altyapı, veri ve sınırlamalar"])

with t0:
    yuksek = ay_df[ay_df["risk_model"] >= 90]
    st.markdown(
        f"**{ay_etiketi(ay)} ({ay_araligi(ay)})** için AI modeli **≈ {len(yuksek):,} km²** alanı "
        f"çok yüksek riskli buldu. Bu alanların yakınında yaşayan ve uygulamaya kayıtlı kullanıcılara "
        f"kendi gruplarına uygun bir uyarı gönderilir.".replace(",", ".")
    )
    b1, b2 = st.columns([1, 1.3], gap="large")
    with b1:
        kitle_toplu = st.selectbox("Hedef kitle", KITLELER, key="kitle_toplu")
        if len(yuksek):
            ornek = yuksek.nlargest(1, "risk_model").iloc[0]
            konum_t = f"{ornek['lat']:.2f}° K, {ornek['lon']:.2f}° D çevresi".replace(".", ",")
            baslik_t, govde_t = bildirim_metni(float(ornek["risk_model"]), ay, kitle_toplu, konum_t)
        else:
            baslik_t, govde_t = bildirim_metni(50.0, ay, kitle_toplu, "Antalya")
        if st.button("Toplu uyarıyı gönder (simülasyon)", type="primary", key="bildirim_toplu",
                     disabled=len(yuksek) == 0):
            st.toast(f"{len(yuksek):,} km² çok yüksek riskli alanın çevresine uyarı kuyruğa alındı "
                     f"(simülasyon).".replace(",", "."), icon="🔥")
            st.session_state["toplu_gonderildi"] = True
        st.caption(
            "Gerçek sürümün işleyişi: kullanıcı uygulamayı yükleyip konumunu ve grubunu (çiftçi, köy sakini…) "
            "seçer → risk haritası her hafta 7 günlük hava tahminiyle güncellenir → konumu çok yüksek riskli "
            "bir alana yakın olanlara telefon bildirimi gider. Bu prototipte gönderim simüle edilir."
        )
    with b2:
        st.markdown("**Bildirim önizlemesi**")
        st.markdown(telefon_karti(baslik_t, govde_t, len(yuksek) > 0), unsafe_allow_html=True)

with t1:
    a, b_ = st.columns([1.2, 1], gap="large")
    with a:
        st.markdown(
            """
**Öğrenen risk modeli (Random Forest).** Antalya'daki ~20.500 alanın 6 aylık verisini
inceleyerek *"bu alanda bu ay yangın çıkar mı?"* sorusunu gerçek uydu yangın
tespitlerinden öğrenir. Bir uzmanın ağırlık seçtiği formülün aksine, hangi
etkenin ne kadar önemli olduğuna veriye bakarak kendisi karar verir.

**Açıklama katmanı.** Haritada seçilen her alan için modelin en çok önem verdiği
etkenlerden il ortalamasından belirgin şekilde sapanları seçer ve riskin nedenini
sade bir dille yazar. Yalnızca hesaplanmış değerleri kullanır; sayı uydurmaz.

**Geliştirmede AI.** Veri hattı, model ve bu arayüz bir AI kodlama asistanıyla
birkaç günde kuruldu.
            """
        )
    with b_:
        st.markdown("**Model neye bakıyor? (değişken önemi)**")
        onem_seri = pd.Series({adlar[k]: v * 100 for k, v in onem.items()}).sort_values()
        st.bar_chart(onem_seri, horizontal=True, height=280, y_label="", x_label="Önem (%)")

with t2:
    test = sonuc.get("test") or {}
    if test:
        st.markdown(
            f"Model **Nisan–Ağustos** verisiyle eğitildi ve hiç görmediği "
            f"**{', '.join(ay_etiketi(a) for a in sonuc['test_aylari'])}** aylarında test edildi "
            f"({test.get('yangin_sayisi', '?')} yangınlı alan)."
        )
        dt = pd.DataFrame({
            "Yöntem": ["Rastgele tahmin", "Kural tabanlı formül", "AI risk modeli"],
            "Yangınların en riskli %20'de yakalanma oranı": ["%20", f"%{tr(test['kural']['yakalama_yuzde'])}", f"%{tr(test['model']['yakalama_yuzde'])}"],
            "AUC (0,5 = rastgele, 1 = mükemmel)": ["0,50", tr(test['kural']['auc'], 2), tr(test['model']['auc'], 2)],
        })
        st.dataframe(dt, hide_index=True, width="stretch")
        ayd = sonuc.get("ay_disarida") or {}
        if ayd.get("model_yakalama_yuzde") is not None:
            st.caption(
                f"Haritadaki AI katmanı da aynı dürüstlükle üretildi: her ay, o ayı hiç görmemiş bir modelle tahmin edildi. "
                f"7 ayın tamamında yangınların %{tr(ayd['model_yakalama_yuzde'])}'i en riskli %20'de "
                f"(formül: %{tr(ayd['kural_yakalama_yuzde'])})."
            )
    else:
        st.info("Zaman bazlı test için yeterli yangın verisi yoktu.")

    aylik = df.groupby("ay").agg(yangin=("yangin_sayisi", lambda s: int((s > 0).sum())), ndmi=("ndmi", "median"))
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Yangın görülen alan sayısı**")
        st.altair_chart(ay_grafigi(aylik[["yangin"]], "bar", "#d7301f", "Alan"), width="stretch")
    with c2:
        st.markdown("**İl geneli bitki nemi (NDMI ortancası)**")
        st.altair_chart(ay_grafigi(aylik[["ndmi"]].round(3), "line", ["#01665e"], "NDMI").encode(
            color=alt.value("#01665e")), width="stretch")
    st.caption("Bitki nemi düştükçe yangınlar artıyor: Temmuz–Eylül hem en kuru hem en çok yangın görülen dönem.")

with t3:
    st.markdown(
        """
| Katman | Araç |
| --- | --- |
| Uydu verisi | Copernicus Sentinel-2 L2A, Sentinel Hub Process API (aylık bulutsuz medyan, ~1 km) |
| Hava verisi | Open-Meteo geçmiş arşivi (günlük maks. sıcaklık, min. nem, maks. rüzgâr, yağış) |
| Yangın tespitleri | NASA FIRMS, VIIRS 375 m (sanayi kaynakları ve düşük güvenli noktalar ayıklandı) |
| İşleme | Python: pandas, numpy, rasterio, geopandas |
| AI modeli | scikit-learn Random Forest + açıklama katmanı |
| Arayüz | Streamlit + Folium, Streamlit Community Cloud |

**Sınırlamalar.** Bu bir prototiptir; resmî bir erken uyarı sistemi değildir.
Uydu yangın noktaları tarım anızı yakmayı da içerebilir. Rüzgâr yönü, eğim ve yakıt
türü bu sürümde yok. Risk değerleri göreli sıradır (0–100): 90, o alanın 6 aylık tüm
alan-aylar arasında en riskli %10'da olduğu anlamına gelir.
        """
    )
