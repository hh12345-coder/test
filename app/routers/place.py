# app/routers/places.py
import math
import httpx
from fastapi import APIRouter, HTTPException, FastAPI
from pydantic import BaseModel
from typing import List, Tuple, Any
from app.core.utils import compute_center
from app.config import BAIDU_MAPS_API_KEY

router = APIRouter()

ROUTEMATRIX_DRIVING = "http://api.map.baidu.com/routematrix/v2/driving"
PLACE_SEARCH = "http://api.map.baidu.com/place/v2/search"

class PlaceRequest(BaseModel):
    coords: List[Tuple[float, float]]  # [[lat, lon], ...]
    budget: int | None = None
    cuisine: str | None = None
    radius: int | None = 3000  # 搜索半径，默认 3km

class POI(BaseModel):
    name: str
    addr: str
    lat: float
    lon: float
    avg_travel_time_min: float | None = None
    raw: Any | None = None

def haversine_km(a, b):
    lat1, lon1 = a; lat2, lon2 = b
    R = 6371
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1); dlambda = math.radians(lon2 - lon1)
    x = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(x))

from fastapi.responses import JSONResponse

@router.post("/recommend")
async def recommend_places(req: PlaceRequest):
    """
    返回按平均出行时长排序的 POI（默认取前6）
    流程：
     1) 用 coords 计算地理中心
     2) 用百度 place/v2/search 拉取候选 POI（最多 12 个）
     3) 调用百度 routematrix/v2/driving 计算每个 origin->destination 的时长
     4) 计算每个 POI 的平均时长并排序
    注意：当路网矩阵失败时回退为直线距离估算
    """
    if not BAIDU_MAPS_API_KEY:
        raise HTTPException(status_code=500, detail="BAIDU_MAPS_API_KEY 未配置，请在 .env 中设置。")

    if not req.coords or len(req.coords) == 0:
        raise HTTPException(status_code=400, detail="coords 不能为空")

    # 校验并清洗 coords
    cleaned_coords = []
    for item in req.coords:
        if not (isinstance(item, (list, tuple)) and len(item) == 2):
            raise HTTPException(status_code=400, detail=f"coords 项目格式错误：{item}")
        try:
            lat = float(item[0]); lon = float(item[1])
        except Exception:
            raise HTTPException(status_code=400, detail=f"coords 项目无法转为浮点数：{item}")
        cleaned_coords.append((lat, lon))

    center = compute_center(cleaned_coords)

    # POI 搜索
    params = {
        "query": req.cuisine or "餐厅",
        "location": f"{center[0]},{center[1]}",
        "radius": int(req.radius or 3000),
        "output": "json",
        "ak": BAIDU_MAPS_API_KEY,
        "scope": 2,
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            ps_resp = await client.get(PLACE_SEARCH, params=params)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"调用百度 POI 搜索网络错误: {e}")

    if ps_resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"调用百度 POI 搜索失败: HTTP {ps_resp.status_code}")

    try:
        ps_json = ps_resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="百度 POI 搜索返回非 JSON")

    if ps_json.get("status") != 0:
        error_msg = ps_json.get('message', '未知错误')
        # 记录详细的API错误信息
        error_detail = f"百度地图API返回错误 - 状态码: {ps_json.get('status')}, 错误信息: {error_msg}, 完整响应: {ps_json}"
        print(error_detail)  # 在日志中打印详细错误信息
        
        # 提供一个模拟的响应，以便在API调用失败时也能展示功能
        # 扩展错误类型捕获，包含更多可能的API错误
        if any(keyword in error_msg for keyword in ["IP校验失败", "Referer校验失败", "APP Referer校验失败", "invalid key", "AK验证失败"]):
            # 返回模拟数据，展示接口格式
            mock_center = center
            mock_candidates = [
                {
                    "name": "星巴克咖啡",
                    "addr": "上海市徐汇区淮海中路1000号",
                    "lat": 31.2150,
                    "lon": 121.4450,
                    "avg_travel_time_min": 12.5,
                    "raw": None
                },
                {
                    "name": "瑞幸咖啡",
                    "addr": "上海市徐汇区宜山路900号",
                    "lat": 31.2180,
                    "lon": 121.4430,
                    "avg_travel_time_min": 15.3,
                    "raw": None
                },
                {
                    "name": "COSTA咖啡",
                    "addr": "上海市徐汇区华山路888号",
                    "lat": 31.2130,
                    "lon": 121.4460,
                    "avg_travel_time_min": 14.7,
                    "raw": None
                }
            ]
            # 确保返回正确编码的JSON响应
            response_data = {
                "center": mock_center,
                "candidates": mock_candidates,
                "note": f"百度API调用失败: {error_msg}。返回模拟数据用于演示。",
                "api_error_code": ps_json.get('status')
            }
            return JSONResponse(content=response_data, media_type="application/json; charset=utf-8")
        # 返回明确编码的错误响应
        return JSONResponse(
            status_code=502,
            content={"detail": f"百度POI错误: {error_msg}", "error_code": ps_json.get('status')},
            media_type="application/json; charset=utf-8"
        )

    raw_results = ps_json.get("results", [])[:12]
    if not raw_results:
        return {"center": center, "candidates": []}

    # 构造 origins / destinations
    origins = "|".join([f"{lat},{lon}" for lat, lon in cleaned_coords])
    destinations = "|".join([f"{float(item['location']['lat'])},{float(item['location']['lng'])}" for item in raw_results])

    matrix_params = {
        "output": "json",
        "ak": BAIDU_MAPS_API_KEY,
        "origins": origins,
        "destinations": destinations,
    }

    # 调用路网矩阵
    print(f"开始调用百度路网矩阵API，origins: {origins}, destinations: {destinations}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            matrix_resp = await client.get(ROUTEMATRIX_DRIVING, params=matrix_params)
            print(f"百度路网矩阵API返回状态码: {matrix_resp.status_code}")
        except Exception as e:
            # 记录详细的异常信息
            print(f"百度路网矩阵API请求异常: {str(e)}")
            # 回退：直线距离估算（分钟）
            candidates = []
            for item in raw_results:
                lat = float(item['location']['lat']); lon = float(item['location']['lng'])
                avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
                # 估速：30 km/h => 0.5 km/min
                avg_min = avg_km / 0.5
                candidates.append(POI(name=item.get('name'), addr=item.get('address',''), lat=lat, lon=lon, avg_travel_time_min=round(avg_min,1), raw=item))
            candidates.sort(key=lambda x: x.avg_travel_time_min)
            return {"center": center, "candidates": [c.dict() for c in candidates[:6]], "note": f"路网矩阵请求失败，退回直线估算: {str(e)}", "api_error_type": "network_exception"}

    if matrix_resp.status_code != 200:
        # 记录HTTP错误状态码
        print(f"百度路网矩阵API返回HTTP错误状态码: {matrix_resp.status_code}")
        # 回退为直线估算
        candidates = []
        for item in raw_results:
            lat = float(item['location']['lat']); lon = float(item['location']['lng'])
            avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
            avg_min = avg_km / 0.5
            candidates.append(POI(name=item.get('name'), addr=item.get('address',''), lat=lat, lon=lon, avg_travel_time_min=round(avg_min,1), raw=item))
        candidates.sort(key=lambda x: x.avg_travel_time_min)
        return {"center": center, "candidates": [c.dict() for c in candidates[:6]], "note": f"路网矩阵 HTTP {matrix_resp.status_code}, 已退回直线估算", "api_error_type": "http_error", "http_status_code": matrix_resp.status_code}

    try:
        matrix_json = matrix_resp.json()
        print(f"百度路网矩阵API返回JSON数据: {matrix_json}")
    except Exception as e:
        # 记录JSON解析错误
        print(f"百度路网矩阵API返回数据JSON解析失败: {str(e)}")
        candidates = []
        for item in raw_results:
            lat = float(item['location']['lat']); lon = float(item['location']['lng'])
            avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
            avg_min = avg_km / 0.5
            candidates.append(POI(name=item.get('name'), addr=item.get('address',''), lat=lat, lon=lon, avg_travel_time_min=round(avg_min,1), raw=item))
        candidates.sort(key=lambda x: x.avg_travel_time_min)
        return {"center": center, "candidates": [c.dict() for c in candidates[:6]], "note": "路网矩阵返回非 JSON，已退回直线估算", "api_error_type": "json_parse_error"}

    if matrix_json.get("status") != 0:
        # 记录API错误信息
        error_msg = matrix_json.get('message', '未知错误')
        print(f"百度路网矩阵API返回错误状态码: {matrix_json.get('status')}, 错误信息: {error_msg}")
        candidates = []
        for item in raw_results:
            lat = float(item['location']['lat']); lon = float(item['location']['lng'])
            avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
            avg_min = avg_km / 0.5
            candidates.append(POI(name=item.get('name'), addr=item.get('address',''), lat=lat, lon=lon, avg_travel_time_min=round(avg_min,1), raw=item))
        candidates.sort(key=lambda x: x.avg_travel_time_min)
        return {"center": center, "candidates": [c.dict() for c in candidates[:6]], "note": f"路网矩阵返回错误: {error_msg}, 已退回直线估算", "api_error_type": "api_error", "api_error_code": matrix_json.get('status')}

    # 解析 matrix elements（origin 列表，每个 origin 包含 destination 列表）
    try:
        elements = matrix_json['result']['elements']
        print(f"成功解析百度路网矩阵API返回的elements，数量: {len(elements)}")
    except Exception as e:
        # 记录解析错误
        print(f"百度路网矩阵API返回数据格式解析失败: {str(e)}, 响应结构: {list(matrix_json.keys())}")
        candidates = []
        for item in raw_results:
            lat = float(item['location']['lat']); lon = float(item['location']['lng'])
            avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
            avg_min = avg_km / 0.5
            candidates.append(POI(name=item.get('name'), addr=item.get('address',''), lat=lat, lon=lon, avg_travel_time_min=round(avg_min,1), raw=item))
        candidates.sort(key=lambda x: x.avg_travel_time_min)
        return {"center": center, "candidates": [c.dict() for c in candidates[:6]], "note": "路网矩阵响应格式不符，已退回直线估算", "api_error_type": "format_error"}

    # 累加 duration（秒）并统计有效条数
    dest_count = len(raw_results)
    dest_durations = [0.0] * dest_count
    dest_valid_counts = [0] * dest_count

    for origin_elem in elements:
        if not isinstance(origin_elem, list):
            continue
        for j, elem in enumerate(origin_elem):
            if not isinstance(elem, dict):
                continue
            if elem.get("status") == 0 and isinstance(elem.get("duration"), dict) and 'value' in elem["duration"]:
                try:
                    dest_durations[j] += float(elem["duration"]["value"])
                    dest_valid_counts[j] += 1
                except Exception:
                    continue

    candidates = []
    for idx, item in enumerate(raw_results):
        name = item.get('name')
        addr = item.get('address', '')
        lat = float(item['location']['lat']); lon = float(item['location']['lng'])

        # 计算平均时长（分钟），避免除零错误
        avg_travel_time_min = round(dest_durations[idx] / 60, 1) if dest_valid_counts[idx] > 0 else None
        candidates.append(POI(name=name, addr=addr, lat=lat, lon=lon, avg_travel_time_min=avg_travel_time_min, raw=item))

    # 按照平均时长排序
    candidates.sort(key=lambda x: x.avg_travel_time_min)

    return {"center": center, "candidates": [c.dict() for c in candidates[:6]]}

from fastapi import FastAPI

app = FastAPI()

app.include_router(router, prefix="/api/places")
