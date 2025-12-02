#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.crs import CRS
from pathlib import Path

# local subroutine
from _load_gsidem import _load_gsidem  
#debug
import pdb


def convert_gsi_xml_to_geotiff_latlon(xml_path, out_tif, set_nodata: float | None = None):
    """
    GSIDEM XML -> WGS84 (EPSG:4326) の “一般的な” GeoTIFF（ストライプ方式）
    - 圧縮: deflate（必要なければ None に変更可）
    - nodata タグは省略（データ中の NaN をそのまま保持）。付けたい場合は set_nodata を数値で指定
    """
    # 読み込み（欠損は NaN 前提）
    xs, ys, zs, _ = _load_gsidem(xml_path)
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    zs = np.asarray(zs, dtype=float)

    N = zs.size
    if N == 0:
        raise ValueError("データが空です。")

    # 列数W（1行目の y が変わらなくなるまで）
    y0 = ys[0]
    atol = max(1e-9, float(np.nanmax(np.abs(ys))) * 1e-10)
    W = 1
    for k in range(1, N):
        if np.isfinite(ys[k]) and np.isfinite(y0) and abs(ys[k] - y0) <= atol:
            W += 1
        else:
            break
    if N % W != 0:
        raise ValueError(f"行列サイズ推定に失敗: N={N}, W={W}")
    H = N // W

    arr = zs.reshape(H, W).astype("float32")

    # アフィン（ピクセル中心→左上角へ 0.5 ピクセル補正）
    lon0, lat0 = xs[0], ys[0]
    lon_step = (xs[1] - xs[0]) if W > 1 else 0.0
    lat_step = (ys[W] - ys[0]) if H > 1 else 0.0  # 北→南なら負
    transform = Affine.translation(lon0 - lon_step/2.0, lat0 - lat_step/2.0) * Affine.scale(lon_step, lat_step)

    # ここがポイント：タイル設定を入れない＝ストライプ（一般的なGeoTIFF）
    profile = dict(
        driver="GTiff",
        height=H,
        width=W,
        count=1,
        dtype="float32",
        crs=CRS.from_epsg(4326),
        transform=transform
    )

    if set_nodata is not None:
        profile["nodata"] = float(set_nodata)  # 例: -9999.0

    #out_tif.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_tif, "w", **profile) as dst:
        dst.write(arr, 1)

    print("success!")

if __name__ == "__main__":
    # テスト
    xml_path = "/Users/fogushi/Documents/Develop/gsidem/data/check_syns_ortho/FG-GML-624372-DEM5A-20250620/FG-GML-6243-72-10-DEM5A-20250620.xml"
    out_tif = "/Users/fogushi/Documents/Develop/gsidem/data/check_syns_ortho/dem_test.tif"
    convert_gsi_xml_to_geotiff_latlon(xml_path, out_tif)