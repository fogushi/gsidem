#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChatGPT
国土地理院の標高タイル DEM5A/DEM5B を、
左上・右下の緯度経度（WGS84）で指定した範囲について
必要なタイルを自動ダウンロードし、1枚の GeoTIFF に出力するスクリプト。

出典: 「地理院タイル（標高タイル）」
  https://cyberjapandata.gsi.go.jp/xyz/dem5a/{z}/{x}/{y}.txt
利用時は「地理院タイル」「国土地理院」と出典を明記してください。
"""

import os
import math
import csv
import io
import sys
import requests
import numpy as np
import rasterio
from rasterio.transform import from_bounds

# 標高タイル URL テンプレート
DEM5A_URL = "https://cyberjapandata.gsi.go.jp/xyz/dem5a/{z}/{x}/{y}.txt"
DEM5B_URL = "https://cyberjapandata.gsi.go.jp/xyz/dem5b/{z}/{x}/{y}.txt"

USER_AGENT = "Mozilla/5.0 (compatible; dem5-downloader/1.0; +https://maps.gsi.go.jp/)"

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


def fetch_one_tile(z: int, x: int, y: int, session: requests.Session, timeout=10.0):
    """
    1枚のタイルをダウンロードして numpy.ndarray (256x256, float32) を返す。
    まず DEM5A を試し、ダメなら DEM5B を試す。
    どちらも取得できなければ RuntimeError。
    """
    headers = {"User-Agent": USER_AGENT}

    def _download(url):
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
                if val == "e":
                    arr[i, j] = np.nan  # 一旦 NaN
                else:
                    arr[i, j] = float(val)
        return arr

    url_a = DEM5A_URL.format(z=z, x=x, y=y)
    data = _download(url_a)
    if data is not None:
        return data, "DEM5A", url_a

    url_b = DEM5B_URL.format(z=z, x=x, y=y)
    data = _download(url_b)
    if data is not None:
        return data, "DEM5B", url_b

    raise RuntimeError(f"No DEM5A/5B tile at z={z}, x={x}, えぃty={y}")


def download_dem5_bbox(
    out_tif: str,
    north: float,
    west: float,
    south: float,
    east: float,
    zoom: int = 15,
    nodata_value: float = -9999.0,
):

    
    """
    左上（north, west）と右下（south, east）の緯度経度で指定した範囲を
    完全に覆うタイルを自動で取得し、1枚の GeoTIFF に出力する。

    Parameters
    ----------
    out_tif : str
        出力 GeoTIFF ファイルパス
    north : float
        左上の緯度（北）
    west : float
        左上の経度（西）
    south : float
        右下の緯度（南）
    east : float
        右下の経度（東）
    zoom : int
        ズームレベル（DEM5A/5B は z=15 が標準）
    nodata_value : float
        NoData に使う値
    """

    print("out_tif =", out_tif, "type:", type(out_tif))
    print("dirname exists?", os.path.isdir(os.path.dirname(out_tif)))
    
    if south >= north:
        raise ValueError("south < north になるように指定してください。")
    if east <= west:
        raise ValueError("east > west になるように指定してください。")

    # 範囲の4隅ではなく、北端・南端・西端・東端それぞれから代表タイルを取る
    # （タイル境界誤差を減らすため、少し内側にオフセットしてもよい）
    x_west, y_north = latlon_to_tile(north, west, zoom)
    x_east, y_south = latlon_to_tile(south, east, zoom)

    # 念のため min/max
    x0 = min(x_west, x_east)
    x1 = max(x_west, x_east)
    y0 = min(y_north, y_south)
    y1 = max(y_north, y_south)

    h_tiles = x1 - x0 + 1
    v_tiles = y1 - y0 + 1

    width = h_tiles * 256
    height = v_tiles * 256

    print(f"tile x range: {x0}..{x1} (count={h_tiles})")
    print(f"tile y range: {y0}..{y1} (count={v_tiles})")
    print(f"output raster size: {width} x {height}")

    dem = np.full((height, width), nodata_value, dtype="float32")

    with requests.Session() as sess:
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                iy = ty - y0
                ix = tx - x0
                print(f"fetching tile z={zoom}, x={tx}, y={ty} ...")
                try:
                    tile_arr, kind, url = fetch_one_tile(zoom, tx, ty, sess)
                    print(f"  -> {kind} from {url}")
                except Exception as e:
                    print(f"  !! FAILED: z={zoom}, x={tx}, y={ty}, error={e}")
                    continue

                r0 = iy * 256
                c0 = ix * 256
                dest = dem[r0 : r0 + 256, c0 : c0 + 256]

                tile = tile_arr.copy()
                mask_valid = ~np.isnan(tile)
                overwrite = (dest == nodata_value) & mask_valid
                dest[overwrite] = tile[overwrite]
                dem[r0 : r0 + 256, c0 : c0 + 256] = dest

    # 取得したタイル全体の実際の境界（タイル境界）を算出
    north_bound, west_bound = tile_to_latlon(x0, y0, zoom)
    south_bound, east_bound = tile_to_latlon(x1 + 1, y1 + 1, zoom)

    print("bounds from tiles (lat, lon):")
    print(f"  north={north_bound}, south={south_bound}, west={west_bound}, east={east_bound}")
    print("※ 指定した範囲を必ず含みますが、タイル境界の分だけ少し広くなります。")

    transform = from_bounds(west_bound, south_bound, east_bound, north_bound, width, height)

    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "width": width,
        "height": height,
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": nodata_value,
    }

    with rasterio.open(out_tif, "w", **profile) as dst:
        dst.write(dem, 1)

    print(f"saved: {out_tif}")
          
          
if __name__ == "__main__":

    download_dem5_bbox(
        out_tif = "/Users/fogushi/Documents/Develop/gsidem/data/test_5m_dem.tif",
        north = 42.33,
        west = 142.96,
        south = 42.19,
        east = 143.07,
        #zoom = 15,
        #nodata_value = -9999.0,
        )