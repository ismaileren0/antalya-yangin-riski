"""
Hücre bazlı risk açıklaması.

Şu an kural ve şablon tabanlı: modelin önem verdiği değişkenlerden, seçilen
hücrenin il geneline göre belirgin şekilde farklı olanlarını seçer ve sade bir
dille yazar. Hesaplanmış değerlerin dışında sayı üretmez.

İleride (Meta Model API / Muse Spark gibi) bir dil modeli eklenecekse,
`aciklama_uret` aynı girdileri bir istemle modele verip aynı biçimde metin
döndürecek şekilde değiştirilebilir; dashboard'un geri kalanı değişmez.
"""

import math


def bos(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def sayi(x, basamak=2):
    """Türkçe ondalık: 0.06 -> 0,06"""
    return f"{x:.{basamak}f}".replace(".", ",")


def risk_sinifi(deger):
    if bos(deger):
        return "Veri yok"
    if deger >= 90:
        return "Çok yüksek"
    if deger >= 70:
        return "Yüksek"
    if deger >= 40:
        return "Orta"
    return "Düşük"


def aciklama_uret(hucre, ay_ortanca, onem):
    """
    hucre      : dict - seçilen hücrenin değerleri (ndmi, ndvi, sicaklik_maks, ...)
    ay_ortanca : dict - aynı ay için il genelindeki ortanca değerler
    onem       : dict - modelin değişken önemleri (toplam 1)
    Dönüş      : markdown metni
    """
    if bos(hucre.get("risk_model")):
        return "Bu hücre için uydu verisi eksik (bulut veya su yüzeyi); risk hesaplanamadı."

    artiran, azaltan = [], []
    h, o = hucre, ay_ortanca

    def ekle(liste, anahtar, metin):
        liste.append((onem.get(anahtar, 0), metin))

    if not bos(h["ndmi"]):
        fark = h["ndmi"] - o["ndmi"]
        if fark <= -0.03:
            ekle(artiran, "ndmi", f"Bitki örtüsü il geneline göre daha kuru (NDMI {sayi(h['ndmi'])}; il ortancası {sayi(o['ndmi'])}).")
        elif fark >= 0.03:
            ekle(azaltan, "ndmi", f"Bitki örtüsü il geneline göre daha nemli (NDMI {sayi(h['ndmi'])}; il ortancası {sayi(o['ndmi'])}).")

    if not bos(h["ndvi"]) and h["ndvi"] < 0.15:
        ekle(azaltan, "ndvi", f"Bitki örtüsü seyrek (NDVI {sayi(h['ndvi'])}); yanacak yakıt az.")

    if not bos(h["sicaklik_maks"]):
        if h["sicaklik_maks"] - o["sicaklik_maks"] >= 1.5:
            ekle(artiran, "sicaklik_maks", f"Gündüz sıcaklıkları il ortalamasının üzerinde (ort. maks. {sayi(h['sicaklik_maks'], 1)} °C).")
        elif h["sicaklik_maks"] - o["sicaklik_maks"] <= -1.5:
            ekle(azaltan, "sicaklik_maks", f"İl geneline göre serin (ort. maks. {sayi(h['sicaklik_maks'], 1)} °C).")

    if not bos(h["nem_min"]):
        if h["nem_min"] <= 30:
            ekle(artiran, "nem_min", f"Öğleden sonra bağıl nem çok düşük (ort. %{h['nem_min']:.0f}).")
        elif h["nem_min"] >= 50:
            ekle(azaltan, "nem_min", f"Hava nemli (ort. min. nem %{h['nem_min']:.0f}).")

    if not bos(h["ruzgar_maks"]) and h["ruzgar_maks"] - o["ruzgar_maks"] >= 3:
        ekle(artiran, "ruzgar_maks", f"Rüzgâr il geneline göre güçlü (ort. maks. {h['ruzgar_maks']:.0f} km/sa).")

    if not bos(h["yagis_toplam"]):
        if h["yagis_toplam"] < 5:
            ekle(artiran, "yagis_toplam", f"Ay boyunca neredeyse hiç yağış yok ({h['yagis_toplam']:.0f} mm).")
        elif h["yagis_toplam"] >= 40:
            ekle(azaltan, "yagis_toplam", f"Ay içinde belirgin yağış var ({h['yagis_toplam']:.0f} mm).")

    artiran.sort(key=lambda t: t[0], reverse=True)
    azaltan.sort(key=lambda t: t[0], reverse=True)

    sinif = risk_sinifi(h["risk_model"])
    if h["risk_model"] >= 50:
        konum = f"en riskli %{max(1, round(100 - h['risk_model']))} içinde"
    else:
        konum = f"en az riskli %{max(1, round(h['risk_model']))} içinde"
    satirlar = [f"**{sinif} risk.** Bu alan, 6 aylık tüm alan-aylar arasında {konum}."]
    if artiran:
        satirlar.append("\n**Riski artıranlar**")
        satirlar += [f"- {m}" for _, m in artiran[:3]]
    if azaltan:
        satirlar.append("\n**Riski azaltanlar**")
        satirlar += [f"- {m}" for _, m in azaltan[:2]]
    if not artiran and not azaltan:
        satirlar.append("\nDeğerler il ortalamasına yakın; belirgin bir etken öne çıkmıyor.")

    if not bos(h.get("risk_kural")) and abs(h["risk_model"] - h["risk_kural"]) >= 25:
        yon = "daha yüksek" if h["risk_model"] > h["risk_kural"] else "daha düşük"
        satirlar.append(
            f"\n_Öğrenen model bu hücreyi basit formüle göre {yon} riskli buluyor; "
            f"geçmiş yangın desenlerinden öğrendiği bir ilişki olabilir._"
        )

    if not bos(h.get("yangin_sayisi")) and h["yangin_sayisi"] > 0:
        satirlar.append(f"\nBu ay bu hücrede uydu **{int(h['yangin_sayisi'])} yangın noktası** tespit etti.")

    return "\n".join(satirlar)
