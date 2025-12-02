#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国土地理院の標高タイル DEM5A/DEM5B を、
左上・右下の緯度経度（WGS84）で指定した範囲について
必要なタイルを自動ダウンロードし、1枚の GeoTIFF に出力する。

5m が存在しない場所は DEM10 (dem) を同じ範囲でモザイク＋再投影して
穴を埋める（出力グリッドは 5m 相当のまま）。

出典: 「地理院タイル（標高タイル）」
  https://cyberjapandata.gsi.go.jp/xyz/dem5a/{z}/{x}/{y}.txt
  https://cyberjapandata.gsi.go.jp/xyz/dem/{z}/{x}/{y}.txt
利用時は「地理院タイル」「国土地理院」と出典を明記してください。
"""

import math
import csv
import io
import sys

import requests
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling
from rasterio.crs import CRS

# -------------------------------
# 設定
# -------------------------------

DEM5A_URL = "https://cyberjapandata.gsi.go.jp/xyz/dem5a/{z}/{x}/{y}.txt"
DEM5B_URL = "https://cyberjapandata.gsi.go.jp/xyz/dem5b/{z}/{x}/{y}.txt"
DEM10_URL = "https://cyberjapandata.gsi.go.jp/xyz/dem/{z}/{x}/{y}.txt"   # 10m DEM

USER_AGENT = "Mozilla/5.0 (compatible; dem5-downloader/1.0; +https://maps.gsi.go.jp/)"

# -------------------------------
# タイル ⇔ 緯度経度 変換
# -------------------------------

def latlon_to_tile(lat_deg: float, lon_deg: float, zoom: int):
    """
    緯度経度(WGS84) -> Webメルカトルのタイル座標 (x, y)
    （地理院タイル／Google Maps と同じ式）
    """
    lat_rad = math.radians(lat_deg)
    n = 2 ** zoom
    x = int((lon_deg + 180.0) / 360.0 * n)
    y = int(
        (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi)
        / 2.0
        * n
    )
    return x, y


def tile_to_latlon(x: int, y: int, zoom: int):
    """
    タイル座標 (x, y, z) -> 左上隅の緯度経度 (lat, lon)
    """
    n = 2 ** zoom
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat_deg = math.degrees(lat_rad)
    return lat_deg, lon_deg

# -------------------------------
# タイル 1 枚ダウンロード（DEM5 専用）
# -------------------------------

def _download_tile(url: str, session: requests.Session, timeout: float = 10.0):
    """
    dem*.txt をダウンロードして 256x256 の float32 配列を返す。
    'e' は NaN。
    """
    headers = {"User-Agent": USER_AGENT}
    r = session.get(url, headers=headers, timeout=timeout)
    if r.status_code != 200:
        return None

    txt = r.text.strip()
    if not txt:
        return None

    reader = csv.reader(io.StringIO(txt))
    rows = list(reader)
    if len(rows) != 256 or any(len(row) != 256 for row in rows):
        return None

    arr = np.empty((256, 256), dtype="float32")
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            arr[i, j] = np.nan if val == "e" else float(val)
    return arr


def fetch_dem5_tile(z: int, x: int, y: int, session: requests.Session, timeout=10.0):
    """
    DEM5A → DEM5B の順に試して 1 タイル取得。
    どちらも無い場合は None を返す。
    """
    # DEM5A
    url_a = DEM5A_URL.format(z=z, x=x, y=y)
    a = _download_tile(url_a, session, timeout)
    if a is not None:
        return a, "DEM5A", url_a

    # DEM5B
    url_b = DEM5B_URL.format(z=z, x=x, y=y)
    b = _download_tile(url_b, session, timeout)
    if b is not None:
        return b, "DEM5B", url_b

    return None, None, None

# -------------------------------
# DEM10 モザイクを作る
# -------------------------------

def build_dem10_mosaic(
    north: float,
    west: float,
    south: float,
    east: float,
    zoom: int = 14,
    nodata_value: float = -9999.0,
):
    """
    DEM10 (dem) を使って指定範囲をカバーするモザイク配列と transform を返す。
    """
    x_west, y_north = latlon_to_tile(north, west, zoom)
    x_east, y_south = latlon_to_tile(south, east, zoom)

    x0 = min(x_west, x_east)
    x1 = max(x_west, x_east)
    y0 = min(y_north, y_south)
    y1 = max(y_north, y_south)

    h_tiles = x1 - x0 + 1
    v_tiles = y1 - y0 + 1

    width = h_tiles * 256
    height = v_tiles * 256

    dem10 = np.full((height, width), nodata_value, dtype="float32")

    with requests.Session() as sess:
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                iy = ty - y0
                ix = tx - x0
                url = DEM10_URL.format(z=zoom, x=tx, y=ty)
                tile = _download_tile(url, sess)
                if tile is None:
                    # 無いタイルはスキップ
                    continue

                r0 = iy * 256
                c0 = ix * 256
                dest = dem10[r0:r0+256, c0:c0+256]

                mask_valid = ~np.isnan(tile)
                overwrite = (dest == nodata_value) & mask_valid
                dest[overwrite] = tile[overwrite]
                dem10[r0:r0+256, c0:c0+256] = dest

    # タイル全体の境界
    north_b, west_b = tile_to_latlon(x0, y0, zoom)
    south_b, east_b = tile_to_latlon(x1 + 1, y1 + 1, zoom)

    transform10 = from_bounds(west_b, south_b, east_b, north_b, width, height)

    return dem10, transform10

# -------------------------------
# メイン：DEM5 モザイク + DEM10 で穴埋め
# -------------------------------

def download_dem5_fill10_bbox(
    out_tif: str,
    north: float,
    west: float,
    south: float,
    east: float,
    zoom_5m: int = 15,
    nodata_value: float = -9999.0,
):
    """
    左上（north, west）と右下（south, east）の緯度経度で指定した範囲を
    DEM5A/5B のタイルでモザイクし、欠けている場所を DEM10 で補完して
    1 枚の GeoTIFF に出力する。
    """
    if south >= north:
        raise ValueError("south < north になるように指定してください。")
    if east <= west:
        raise ValueError("east > west になるように指定してください。")

    # --- DEM5 のタイル範囲 ---
    x_west, y_north = latlon_to_tile(north, west, zoom_5m)
    x_east, y_south = latlon_to_tile(south, east, zoom_5m)

    x0 = min(x_west, x_east)
    x1 = max(x_west, x_east)
    y0 = min(y_north, y_south)
    y1 = max(y_north, y_south)

    h_tiles = x1 - x0 + 1
    v_tiles = y1 - y0 + 1

    width = h_tiles * 256
    height = v_tiles * 256

    print(f"[DEM5] tile x: {x0}..{x1} (count={h_tiles})")
    print(f"[DEM5] tile y: {y0}..{y1} (count={v_tiles})")
    print(f"[DEM5] raster size: {width} x {height}")

    dem5 = np.full((height, width), nodata_value, dtype="float32")

    # --- DEM5A/5B のモザイク ---
    with requests.Session() as sess:
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                iy = ty - y0
                ix = tx - x0
                print(f"fetch DEM5 z={zoom_5m}, x={tx}, y={ty} ...")
                tile, kind, url = fetch_dem5_tile(zoom_5m, tx, ty, sess)
                if tile is None:
                    print("  -> no DEM5 here")
                    continue
                print(f"  -> {kind} from {url}")
                r0 = iy * 256
                c0 = ix * 256
                dest = dem5[r0:r0+256, c0:c0+256]

                mask_valid = ~np.isnan(tile)
                overwrite = (dest == nodata_value) & mask_valid
                dest[overwrite] = tile[overwrite]
                dem5[r0:r0+256, c0:c0+256] = dest

    # DEM5 タイル全体の境界
    north_b, west_b = tile_to_latlon(x0, y0, zoom_5m)
    south_b, east_b = tile_to_latlon(x1 + 1, y1 + 1, zoom_5m)

    print("bounds from DEM5 tiles (lat, lon):")
    print(f"  north={north_b}, south={south_b}, west={west_b}, east={east_b}")
    print("※ 指定した範囲を必ず含みますが、タイル境界の分だけ少し広くなります。")

    transform5 = from_bounds(west_b, south_b, east_b, north_b, width, height)

    # --- DEM10 で穴埋め ---
    if np.any(dem5 == nodata_value):
        print("Some gaps remain in DEM5; trying to fill with DEM10 (10m)...")

        dem10, transform10 = build_dem10_mosaic(
            north=north_b,
            west=west_b,
            south=south_b,
            east=east_b,
            zoom=14,
            nodata_value=nodata_value,
        )

        if np.all(dem10 == nodata_value):
            print("DEM10 mosaic is all nodata; skip filling.")
        else:
            dem10_on_5m = np.full_like(dem5, nodata_value, dtype="float32")

            reproject(
                source=dem10,
                destination=dem10_on_5m,
                src_transform=transform10,
                src_crs=CRS.from_epsg(4326),
                dst_transform=transform5,
                dst_crs=CRS.from_epsg(4326),
                resampling=Resampling.bilinear,
                src_nodata=nodata_value,
                dst_nodata=nodata_value,
            )

            mask_fill = (dem5 == nodata_value) & (dem10_on_5m != nodata_value)
            filled_count = np.count_nonzero(mask_fill)
            print(f"Filled {filled_count} pixels with DEM10.")
            dem5[mask_fill] = dem10_on_5m[mask_fill]

    # --- GeoTIFF 出力 ---
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "width": width,
        "height": height,
        "crs": "EPSG:4326",
        "transform": transform5,
        "nodata": nodata_value,
    }

    with rasterio.open(out_tif, "w", **profile) as dst:
        dst.write(dem5, 1)

    print(f"saved: {out_tif}")


if __name__ == "__main__":

    download_dem5_fill10_bbox(
        out_tif = "/Users/fogushi/Documents/Develop/gsidem/data/test_5m_dem.tif",
        north = 42.33,
        west = 142.96,
        south = 42.19,
        east = 143.07,
        #zoom = 15,
        #nodata_value = -9999.0,
        )