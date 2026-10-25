"""
Yangın riski uyarı bildirimleri.

Seçilen bölgenin risk seviyesine ve hedef kitleye göre kısa bir bildirim
metni üretir. Metin yalnızca hesaplanmış risk değerinden ve ayın tarih
aralığından oluşturulur; öneriler genel yangın önleme kurallarıdır.

Prototipte bildirimler dashboard içinde önizlenir ve toplu gönderim
simüle edilir. Gerçek gönderim (mobil uygulama + push servisi) yol haritasındadır.
"""

import calendar
import html

AY_ADLARI = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
             "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

KITLELER = ["Herkes", "Çiftçiler", "Orman köyü sakinleri", "Ziyaretçi ve piknikçiler"]

ONLEMLER = {
    "Herkes": [
        "Cam şişe, kırık cam ve metal ambalajları doğaya bırakmayın; güneşte kıvılcım çıkarabilir.",
        "Sigara izmaritlerini yere ya da araçtan dışarı atmayın.",
        "Açık alanda ateş yakmayın, bahçe atıklarını yakmayın.",
        "Duman veya alev görürseniz hemen 112'yi arayın.",
    ],
    "Çiftçiler": [
        "Anız ve tarla artıklarını kesinlikle yakmayın.",
        "Biçerdöver ve traktörlerin egzoz ve kıvılcım tutucularını kontrol edin.",
        "Tarlanın orman tarafında sürülmüş bir yangın şeridi bırakın.",
        "Çalışırken yanınızda su, kürek ve yangın söndürücü bulundurun.",
    ],
    "Orman köyü sakinleri": [
        "Evinizin çevresindeki en az 10 metrelik alanda kuru ot ve çalıları temizleyin.",
        "Çatı ve oluklardaki kuru yaprakları temizleyin.",
        "Bahçe atıklarını yakmayın; çöpleri kapalı kaplarda tutun.",
        "Köyünüzün tahliye yolunu ve toplanma alanını önceden öğrenin.",
    ],
    "Ziyaretçi ve piknikçiler": [
        "Mangalı yalnızca izin verilen piknik alanlarında yakın; ormanda ateş yakmayın.",
        "Alanı terk etmeden önce közün tamamen söndüğünden emin olun.",
        "Aracınızı kuru otların üzerine park etmeyin; sıcak egzoz otları tutuşturabilir.",
        "Cam şişe ve çöplerinizi yanınızda geri götürün.",
    ],
}


def ay_araligi(ay):
    """'2026-09' -> '1–30 Eylül 2026'"""
    yil, a = int(ay[:4]), int(ay[5:7])
    son = calendar.monthrange(yil, a)[1]
    return f"1–{son} {AY_ADLARI[a - 1]} {yil}"


def uyari_gerekli(risk):
    return risk is not None and risk == risk and risk >= 70


def seviye(risk):
    if risk >= 90:
        return "ÇOK YÜKSEK"
    if risk >= 70:
        return "YÜKSEK"
    if risk >= 40:
        return "ORTA"
    return "DÜŞÜK"


def bildirim_metni(risk, ay, kitle, konum):
    """Bildirim başlığı ve gövdesi. konum: '37,10° K, 30,80° D çevresi' gibi."""
    tarih = ay_araligi(ay)
    onlemler = ONLEMLER.get(kitle, ONLEMLER["Herkes"])[:3]
    if uyari_gerekli(risk):
        baslik = f"🔥 Yangın riski {seviye(risk)}: {konum}"
        giris = f"{tarih} arasında bölgenizde orman yangını riski {seviye(risk).lower()}. Lütfen:"
    else:
        baslik = f"Yangın riski {seviye(risk).lower()}: {konum}"
        giris = f"{tarih} için bölgenizde özel bir uyarı yok. Yine de:"
    govde = giris + "\n" + "\n".join(f"• {o}" for o in onlemler)
    return baslik, govde


def telefon_karti(baslik, govde, uyari=True):
    """Bildirimi telefon bildirimi görünümünde HTML olarak döndürür."""
    renk = "#d7301f" if uyari else "#4c78a8"
    satirlar = "<br>".join(html.escape(s) for s in govde.split("\n"))
    return f"""
<div style="max-width:420px;border-radius:16px;padding:14px 16px;margin:8px 0 4px 0;
            background:rgba(127,127,127,0.10);border:1px solid rgba(127,127,127,0.25);
            border-left:5px solid {renk};font-family:sans-serif;">
  <div style="font-size:0.75rem;opacity:0.7;margin-bottom:4px;">ANTALYA YANGIN RİSKİ · şimdi</div>
  <div style="font-weight:700;margin-bottom:6px;">{html.escape(baslik)}</div>
  <div style="font-size:0.9rem;line-height:1.45;">{satirlar}</div>
</div>"""
