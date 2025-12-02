import xml.etree.ElementTree as ET
import numpy as np
import re
#debug
import pdb

def _load_gsidem(infile, nodata_fill=np.nan):
    """
    GSIのDEM(GML/XML)を読み込み、(lon_list, lat_list, elev_list, mesh_code) を返す。
    10mメッシュのXMLに対応
    - Envelope の (lat lon)/(lon lat) どちらでも自動補正
    - GridEnvelope (low/high) からサイズ計算
    - tupleList / doubleOrNilReasonTupleList の両方に対応
    - -9999, -32768, 999999, 9999 や非数は NaN で返す（デフォルト）
    """
    SENTS = {-9999.0, -32768.0, 999999.0, 9999.0}

    def _lname(tag): return tag.split('}')[-1] if '}' in tag else tag
    def _txt(el): return "".join(el.itertext()).strip() if el is not None else ""
    def _ints(s): return [int(n) for n in re.findall(r"-?\d+", s or "")]
    def _flts(s): return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", s or "")]
    def _last_float(s):
        xs = _flts(s);  return (xs[-1] if xs else float("nan"))
    def _to_lonlat(x, y):
        # (lat,lon) と判定できる並びなら (lon,lat) に入替
        if -90 <= x <= 90 and -180 <= y <= 180 and not (-180 <= x <= 180 and -90 <= y <= 90):
            return y, x
        return x, y

    tree = ET.parse(infile)
    root = tree.getroot()

    # ---- DEMノード & coverage ----
    dem_data = root.find("{http://fgd.gsi.go.jp/spec/2008/FGD_GMLSchema}DEM") or root
    coverage_data = dem_data.find("{http://fgd.gsi.go.jp/spec/2008/FGD_GMLSchema}coverage")
    if coverage_data is None:
        # 一部は gml:GridCoverage 直下パターン
        coverage_data = dem_data.find("{http://www.opengis.net/gml/3.2}GridCoverage")
    if coverage_data is None:
        raise ValueError("coverage が見つかりません")

    # ---- Envelope（bbox）----
    bby = coverage_data.find("{http://www.opengis.net/gml/3.2}boundedBy")
    env = None
    if bby is not None:
        env = bby.find("{http://www.opengis.net/gml/3.2}Envelope")
    if env is None:
        env = coverage_data.find("{http://www.opengis.net/gml/3.2}Envelope")
    if env is None:
        # 念のため総当り
        env = root.find(".//{http://www.opengis.net/gml/3.2}Envelope")
    if env is None:
        raise ValueError("gml:Envelope が見つかりません")

    lc_vals = _flts(_txt(env.find("{http://www.opengis.net/gml/3.2}lowerCorner")))
    uc_vals = _flts(_txt(env.find("{http://www.opengis.net/gml/3.2}upperCorner")))
    if len(lc_vals) < 2 or len(uc_vals) < 2:
        raise ValueError("Envelope の lowerCorner/upperCorner が不正です")
    lo_lon_raw, lo_lat_raw = lc_vals[:2]
    hi_lon_raw, hi_lat_raw = uc_vals[:2]
    lo_lon, lo_lat = _to_lonlat(lo_lon_raw, lo_lat_raw)
    hi_lon, hi_lat = _to_lonlat(hi_lon_raw, hi_lat_raw)

    # ---- Grid / GridEnvelope（サイズ）----
    gridDomain = coverage_data.find("{http://www.opengis.net/gml/3.2}gridDomain") or coverage_data
    Grid = gridDomain.find("{http://www.opengis.net/gml/3.2}Grid")
    if Grid is None:
        Grid = root.find(".//{http://www.opengis.net/gml/3.2}Grid")
    if Grid is None:
        raise ValueError("gml:Grid が見つかりません")

    limits = Grid.find("{http://www.opengis.net/gml/3.2}limits")
    GE = limits.find("{http://www.opengis.net/gml/3.2}GridEnvelope") if limits is not None else None
    if GE is None:
        GE = Grid.find("{http://www.opengis.net/gml/3.2}GridEnvelope")
    if GE is None:
        GE = root.find(".//{http://www.opengis.net/gml/3.2}GridEnvelope")
    if GE is None:
        raise ValueError("gml:GridEnvelope が見つかりません")

    low_nums  = _ints(_txt(GE.find("{http://www.opengis.net/gml/3.2}low")))
    high_nums = _ints(_txt(GE.find("{http://www.opengis.net/gml/3.2}high")))
    if len(low_nums) < 2 or len(high_nums) < 2:
        raise ValueError("GridEnvelope の low/high が不正です")
    li, lj = low_nums[:2]; hi, hj = high_nums[:2]
    size_x = (hi - li + 1)
    size_y = (hj - lj + 1)
    if size_x <= 0 or size_y <= 0:
        raise ValueError(f"Gridサイズが不正です: ({size_x},{size_y})")

    # ---- rangeSet / DataBlock / tupleList ----
    range_set = coverage_data.find("{http://www.opengis.net/gml/3.2}rangeSet") or root.find(".//{http://www.opengis.net/gml/3.2}rangeSet")
    if range_set is None:
        raise ValueError("gml:rangeSet が見つかりません")
    data_block = range_set.find("{http://www.opengis.net/gml/3.2}DataBlock") or range_set

    tuple_el = data_block.find("{http://www.opengis.net/gml/3.2}tupleList")
    if tuple_el is None:
        tuple_el = data_block.find("{http://www.opengis.net/gml/3.2}doubleOrNilReasonTupleList")
    if tuple_el is None:
        # さらに別名
        tuple_el = data_block.find("{http://www.opengis.net/gml/3.2}doubleOrNilReasonList")
    if tuple_el is None:
        raise ValueError("標高データ(tupleList系) が見つかりません")

    txt = _txt(tuple_el)
    if not txt:
        raise ValueError("標高データ(tupleList系) が空です")

    # ---- 標高・座標の生成 ----
    lon_size = (hi_lon - lo_lon) / size_x
    lat_size = (hi_lat - lo_lat) / size_y

    elevation_data = []
    lon_data = []
    lat_data = []

    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    need = size_x * size_y
    if len(lines) < need:
        # 行が足りない（空行や途中改行） → 連結で再分解
        lines = re.split(r"[\r\n]+", txt.strip())
        lines = [ln.strip() for ln in lines if ln.strip()]

    # 各行の「最後の数値」を標高として採用（ラベル,値 形式に強い）
    for j in range(size_y):
        for i in range(size_x):
            k = i + size_x * j
            if k >= len(lines):
                v = nodata_fill
            else:
                v = _last_float(lines[k])
                if (v in SENTS) or (not np.isfinite(v)):
                    v = nodata_fill
            elevation_data.append(float(v))
            lon_data.append(lo_lon + lon_size * i)
            # 上(北)→下(南)に j が増える想定
            lat_data.append(hi_lat - lat_size * j)

    mesh_node = dem_data.find("{http://fgd.gsi.go.jp/spec/2008/FGD_GMLSchema}mesh")
    mesh_code = _txt(mesh_node)

    print(f"GSIDEMを読み込みました: {mesh_code}  size=({size_x},{size_y}) points={len(elevation_data)}")
    return lon_data, lat_data, elevation_data, mesh_code


# main
if __name__ == "__main__":

    infile = "/Users/fogushi/Documents/Develop/gsidem/data/check_syns_ortho/FG-GML-624372-DEM5A-20250620/FG-GML-6243-72-10-DEM5A-20250620.xml"
    lon_data, lat_data, elevation_data, mesh_code=_load_gsidem(infile)
    pdb.set_trace()


