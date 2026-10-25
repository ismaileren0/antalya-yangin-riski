"""
GitHub'a yuklemeden ONCE calistir:  python guvenlik_kontrol.py

1) Proje klasorunun yanina "antalya-fire-risk-github" adinda TEMIZ bir kopya
   olusturur: .env, .venv, ham veri ve model dosyasi bu kopyaya girmez.
2) Bu kopyadaki her dosyayi tarar; .env'deki gercek anahtarlardan biri
   herhangi bir dosyada geciyorsa uyarir ve hata koduyla cikar.

GitHub web sitesine YALNIZCA bu temiz kopyanin icindekileri surukle-birak.
(Web'den yuklemede .gitignore uygulanmaz; bu yuzden temiz kopya sarttir.)
"""

import shutil
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent
ATLANAN_KLASORLER = {".venv", "veri", ".git", "__pycache__", "node_modules"}
METIN_UZANTILARI = {".py", ".md", ".txt", ".toml", ".json", ".csv", ".yaml", ".yml", ".ini", ".cfg", ".example", ".html", ".js"}


def env_degerleri():
    env = KOK / ".env"
    if not env.exists():
        return {}
    degerler = {}
    for satir in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        ad, deger = satir.split("=", 1)
        deger = deger.strip().strip('"').strip("'")
        if len(deger) >= 8:  # cok kisa degerler anahtar degildir
            degerler[ad.strip()] = deger
    return degerler


def yuklenecek_dosyalar():
    """Git deposuysa git'in yukleyecegi dosyalar, degilse klasordeki tum metin dosyalari."""
    try:
        cikti = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=KOK, capture_output=True, text=True, check=True,
        ).stdout
        return [KOK / p for p in cikti.splitlines() if p], True
    except (FileNotFoundError, subprocess.CalledProcessError):
        dosyalar = []
        for p in KOK.rglob("*"):
            if p.is_file() and not (set(p.relative_to(KOK).parts) & ATLANAN_KLASORLER):
                dosyalar.append(p)
        return dosyalar, False


GITIGNORE = "# --- Gizli anahtarlar: ASLA GitHub'a yuklenmez ---\n.env\n.env.*\n*.env\n!.env.example\nsecrets.toml\n.streamlit/secrets.toml\n\n# --- Yerel ortam ve buyuk ham veri ---\n.venv/\n__pycache__/\n/veri/\n*.joblib\n"
ENV_ORNEK = '# Bu dosyayi ".env" adiyla kopyala ve kendi anahtarlarini yaz.\n# .env dosyasi .gitignore ile GitHub\'a yuklenmez; bu ornek dosyada gercek anahtar OLMAMALI.\n#\n# Copernicus Data Space -> Sentinel Hub panel -> User settings -> OAuth clients\nSH_CLIENT_ID=buraya-kendi-client-id\nSH_CLIENT_SECRET=buraya-kendi-client-secret\n#\n# NASA FIRMS -> https://firms.modaps.eosdis.nasa.gov/api/map_key/\nFIRMS_MAP_KEY=buraya-kendi-firms-anahtari\n#\n# Open-Meteo icin anahtar gerekmez.\n# Dashboard (dashboard/app.py) hicbir anahtar kullanmaz.\n'


def koruma_dosyalarini_yaz():
    """Eksikse .gitignore ve .env.example dosyalarini olusturur (Windows'ta elle adlandirmak zor)."""
    gi = KOK / ".gitignore"
    if not gi.exists() or ".env.*" not in gi.read_text(encoding="utf-8", errors="ignore"):
        gi.write_text(GITIGNORE, encoding="utf-8")
        print("  .gitignore olusturuldu/guncellendi.")
    ornek = KOK / ".env.example"
    if not ornek.exists():
        ornek.write_text(ENV_ORNEK, encoding="utf-8")
        print("  .env.example olusturuldu.")


TEMIZ = KOK.parent / f"{KOK.name}-github"
DISARIDA = shutil.ignore_patterns(".env", ".env.*", "*.env", "secrets.toml", ".venv", "veri", ".git",
                                  "__pycache__", "*.joblib", "*.pyc")


def temiz_kopya():
    if TEMIZ.exists():
        shutil.rmtree(TEMIZ)

    def yoksay(klasor, adlar):
        atla = set(DISARIDA(klasor, adlar))
        # .env.example korunur; kok dizindeki ham "veri" atlanir ama dashboard/veri kalir
        atla.discard(".env.example")
        if Path(klasor).resolve() != KOK and "veri" in atla:
            atla.discard("veri")
        return atla

    shutil.copytree(KOK, TEMIZ, ignore=yoksay)
    return [p for p in TEMIZ.rglob("*") if p.is_file()]


def main():
    koruma_dosyalarini_yaz()
    sorunlar = []
    degerler = env_degerleri()
    dosyalar, git_var = yuklenecek_dosyalar()
    if not git_var:
        dosyalar = temiz_kopya()
        kok_goreli = TEMIZ
    else:
        kok_goreli = KOK
    adlar = {p.relative_to(kok_goreli).as_posix() for p in dosyalar}

    # 1) .env'in kendisi yuklenecek mi?
    for ad in adlar:
        dosya_adi = ad.rsplit("/", 1)[-1]
        if dosya_adi == ".env" or (dosya_adi.startswith(".env.") and dosya_adi != ".env.example") or dosya_adi.endswith("secrets.toml"):
            sorunlar.append(f"{ad}: gizli anahtar dosyasi yuklenecek listede!")

    # 2) Anahtar degerleri baska bir dosyaya kopyalanmis mi?
    for p in dosyalar:
        if p.name == ".env" or (p.suffix not in METIN_UZANTILARI and p.name != ".env.example"):
            continue
        try:
            icerik = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for ad, deger in degerler.items():
            if deger in icerik:
                sorunlar.append(f"{p.relative_to(kok_goreli).as_posix()}: {ad} anahtarinin gercek degeri bu dosyada geciyor!")

    print("Guvenlik kontrolu")
    print(f"  Kontrol edilen dosya: {len(dosyalar)}  ({'git listesi' if git_var else 'klasordeki tum dosyalar'})")
    print(f"  .env'de bulunan anahtar: {len(degerler)}")
    if sorunlar:
        print("\n[DUR] GitHub'a YUKLEME. Sorunlar:")
        for s in sorunlar:
            print("  - " + s)
        if not git_var and TEMIZ.exists():
            shutil.rmtree(TEMIZ)  # sorunlu kopya yanlislikla yuklenmesin
            print("\nTemiz kopya silindi. Sorunu duzeltip betigi tekrar calistir.")
        sys.exit(1)
    print("\n[OK] Hicbir gercek anahtar yuklenecek dosyalarda yok. GitHub'a yuklemek guvenli.")
    if not git_var:
        print(f"\nYuklenecek temiz kopya hazir: {TEMIZ}")
        print("GitHub web sitesine YALNIZCA bu klasorun ICINDEKILERI surukle-birak.")


if __name__ == "__main__":
    main()
