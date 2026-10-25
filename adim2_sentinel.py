"""
Adim 2: Sentinel-2'den aylik NDVI ve NDMI (bulutsuz medyan) indir.

Her ay icin sunucuda: bulut/golge pikselleri SCL maskesiyle atilir,
kalan gozlemlerin medyani alinir. ~1 km izgarada tek GeoTIFF doner.

Cikti: veri/ham/sentinel/s2_YYYY-MM.tif  (3 bant: NDVI, NDMI, gecerli_goruntu_sayisi)
Kota: ayda birkac islem birimi; 7 ay toplami ucretsiz kotanin cok altinda.
"""

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from sentinelhub import BBox, CRS, DataCollection, MimeType, SentinelHubRequest, SHConfig

import ayarlar as A

EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08", "B8A", "B11", "SCL", "dataMask"] }],
    output: { bands: 3, sampleType: "FLOAT32" },
    mosaicking: "ORBIT"
  };
}

function medyan(a) {
  if (a.length === 0) return NaN;
  a.sort(function (x, y) { return x - y; });
  var m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

// SCL siniflari: 4 = bitki, 5 = ciplak toprak. Bulut, golge, su, kar disarida.
var GECERLI = [4, 5];

function evaluatePixel(samples) {
  var ndvi = [], ndmi = [];
  for (var i = 0; i < samples.length; i++) {
    var s = samples[i];
    if (s.dataMask !== 1) continue;
    if (GECERLI.indexOf(s.SCL) === -1) continue;
    var a = s.B08 + s.B04;
    var b = s.B8A + s.B11;
    if (a > 0) ndvi.push((s.B08 - s.B04) / a);
    if (b > 0) ndmi.push((s.B8A - s.B11) / b);
  }
  return [medyan(ndvi), medyan(ndmi), ndvi.length];
}
"""


def yapilandirma():
    if not A.SH_CLIENT_ID or not A.SH_CLIENT_SECRET:
        raise RuntimeError("SH_CLIENT_ID / SH_CLIENT_SECRET .env icinde yok.")
    config = SHConfig()
    config.sh_client_id = A.SH_CLIENT_ID
    config.sh_client_secret = A.SH_CLIENT_SECRET
    config.sh_base_url = A.SH_BASE_URL
    config.sh_token_url = A.SH_TOKEN_URL
    return config


def ay_indir(config, koleksiyon, etiket, bas, bit):
    hedef = A.sentinel_dosyasi(etiket)
    if hedef.exists():
        print(f"  {etiket}: zaten var, atlaniyor.")
        return

    print(f"  {etiket}: {bas} - {bit} indiriliyor...", flush=True)
    istek = SentinelHubRequest(
        evalscript=EVALSCRIPT,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=koleksiyon,
                time_interval=(bas.isoformat(), bit.isoformat()),
                maxcc=0.8,  # cok bulutlu sahneleri bastan ele
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=BBox(bbox=A.BBOX, crs=CRS.WGS84),
        size=(A.GENISLIK, A.YUKSEKLIK),
        config=config,
    )
    veri = istek.get_data()[0].astype("float32")  # (satir, sutun, 3)

    transform = from_bounds(*A.BBOX, A.GENISLIK, A.YUKSEKLIK)
    with rasterio.open(
        hedef, "w", driver="GTiff", height=A.YUKSEKLIK, width=A.GENISLIK, count=3,
        dtype="float32", crs="EPSG:4326", transform=transform, nodata=np.nan, compress="deflate",
    ) as dst:
        for i in range(3):
            dst.write(veri[:, :, i], i + 1)
        dst.set_band_description(1, "NDVI")
        dst.set_band_description(2, "NDMI")
        dst.set_band_description(3, "gecerli_goruntu")

    dolu = np.isfinite(veri[:, :, 1]).mean() * 100
    print(f"           kaydedildi; piksellerin %{dolu:.0f}'inde NDMI var.")


def main():
    print("ADIM 2: Sentinel-2 aylik NDVI / NDMI")
    config = yapilandirma()
    koleksiyon = DataCollection.SENTINEL2_L2A.define_from("s2l2a_cdse", service_url=config.sh_base_url)
    for etiket, bas, bit in A.AYLAR:
        ay_indir(config, koleksiyon, etiket, bas, bit)


if __name__ == "__main__":
    main()
