# app/routers/places.py
import math
import httpx
import asyncio
from fastapi import APIRouter, HTTPException, FastAPI, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Tuple, Any
from app.core.utils import compute_center
from app.config import BAIDU_MAPS_API_KEY
from app.database import get_db

router = APIRouter()

# 百度地图API URL配置
ROUTEMATRIX_DRIVING = "http://api.map.baidu.com/routematrix/v2/driving"
ROUTEMATRIX_WALKING = "http://api.map.baidu.com/routematrix/v2/walking"
# 注意：百度地图routematrix/v2 API不支持transit（公共交通）模式
# 尝试使用routematrix/v2/transit会返回404错误
ROUTEMATRIX_TRANSIT = "http://api.map.baidu.com/routematrix/v2/transit"  # 此API不存在

# 百度地图方向lite API（支持公共交通）
DIRECTIONLITE_BASE = "http://api.map.baidu.com/directionlite/v1"
DIRECTIONLITE_WALKING = f"{DIRECTIONLITE_BASE}/walking"
DIRECTIONLITE_TRANSIT = f"{DIRECTIONLITE_BASE}/transit"

PLACE_SEARCH = "http://api.map.baidu.com/place/v2/search"

class PlaceRequest(BaseModel):
    coords: List[Tuple[float, float]] | None = None  # [[lat, lon], ...] - 已废弃，使用school_ids
    school_ids: List[int] | None = None  # 学校ID列表
    budget: int | None = None
    cuisine: str | None = None
    radius: int | None = 3000  # 搜索半径，默认 3km
    preference_mode: str = "walking"  # walking, transit, driving - 仅用于显示偏好，系统会智能选择最优出行方式

class POI(BaseModel):
    name: str
    addr: str
    lat: float
    lon: float
    avg_travel_time_min: float | None = None
    travel_mode: str | None = None  # 系统选择的出行方式
    url: str | None = None  # 百度地图链接或应用内页面链接
    uid: str | None = None  # POI 的唯一标识
    raw: Any | None = None

def haversine_km(a, b):
    lat1, lon1 = a; lat2, lon2 = b
    R = 6371
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1); dlambda = math.radians(lon2 - lon1)
    x = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.asin(math.sqrt(x))

from fastapi.responses import JSONResponse
from app.models.school import School

import time

@router.post("/recommend")
async def recommend_places(req: PlaceRequest, db: Session = Depends(get_db)):
    """
    返回按平均出行时长排序的 POI（默认取前6）
    流程：
     1) 从学校ID获取坐标，或用coords计算地理中心
     2) 用百度 place/v2/search 拉取候选 POI（最多 12 个）
     3) 系统会智能选择最优出行方式：
        - 步行≤30分钟：使用步行矩阵API
        - 步行>30分钟：对前3个POI使用公交lite API
        - 公交失败时：使用驾车时间×1.1估算
        - 全失败时：使用直线距离兜底
    注意：当路网矩阵失败时回退为直线距离估算
    """
    start_time = time.time()
    print(f"开始处理推荐请求，时间: {time.strftime('%H:%M:%S')}")
    
    if not BAIDU_MAPS_API_KEY:
        print(f"百度地图API密钥未配置，处理时间: {time.time() - start_time:.2f}秒")
        raise HTTPException(status_code=500, detail="BAIDU_MAPS_API_KEY 未配置，请在 .env 中设置。")

    # 获取坐标：优先使用school_ids，否则使用coords（向后兼容）
    cleaned_coords = []
    
    if req.school_ids and len(req.school_ids) > 0:
        print(f"使用school_ids获取坐标: {req.school_ids}")
        # 从数据库获取学校坐标
        try:
            schools = db.query(School).filter(School.id.in_(req.school_ids)).all()
            if not schools:
                print(f"未找到指定的学校，处理时间: {time.time() - start_time:.2f}秒")
                raise HTTPException(status_code=404, detail="未找到指定的学校")
            cleaned_coords = [(float(school.lat), float(school.lon)) for school in schools]
            print(f"成功获取{len(cleaned_coords)}个学校的坐标")
        except Exception as e:
            print(f"获取学校坐标失败: {e}，处理时间: {time.time() - start_time:.2f}秒")
            raise HTTPException(status_code=500, detail=f"获取学校坐标失败: {str(e)}")
    elif req.coords and len(req.coords) > 0:
        # 向后兼容：使用coords
        print(f"使用coords获取坐标: {req.coords}")
        for item in req.coords:
            if not (isinstance(item, (list, tuple)) and len(item) == 2):
                raise HTTPException(status_code=400, detail=f"coords 项目格式错误：{item}")
            try:
                lat = float(item[0]); lon = float(item[1])
                cleaned_coords.append((lat, lon))
            except Exception:
                raise HTTPException(status_code=400, detail=f"coords 项目无法转为浮点数：{item}")
    else:
        print(f"未提供school_ids或coords，处理时间: {time.time() - start_time:.2f}秒")
        raise HTTPException(status_code=400, detail="请提供 school_ids 或 coords")

    center = compute_center(cleaned_coords)
    print(f"计算得到地理中心: {center}")
    print(f"获取坐标和计算中心耗时: {time.time() - start_time:.2f}秒")

    # POI 搜索
    # 修复：确保如果cuisine是无效值（如"??"），也使用默认值"餐厅"
    query = req.cuisine if (req.cuisine and req.cuisine.strip() != "??") else "餐厅"
    params = {
        "query": query,
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
                "success": True,
                "data": {
                    "center": mock_center,
                    "candidates": mock_candidates,
                    "note": f"百度API调用失败: {error_msg}。返回模拟数据用于演示。",
                    "api_error_code": ps_json.get('status')
                }
            }
            return response_data
        # 返回明确编码的错误响应
        raise HTTPException(
            status_code=502,
            detail={"success": False, "message": f"百度POI错误: {error_msg}", "error_code": ps_json.get('status')}
        )

    raw_results = ps_json.get("results", [])[:12]
    if not raw_results:
        return {"success": True, "data": {"center": center, "candidates": []}}

    # 构造 origins / destinations
    origins = "|".join([f"{lat},{lon}" for lat, lon in cleaned_coords])
    destinations = "|".join([f"{float(item['location']['lat'])},{float(item['location']['lng'])}" for item in raw_results])

    # 首先使用步行方式获取时间
    initial_preference_mode = req.preference_mode or "walking"
    preference_mode = initial_preference_mode
    
    # 步行时间阈值（分钟）
    WALKING_TIME_THRESHOLD = 30.0
    
    # 定义获取最终步行时间的函数（专门用于展示给用户）
    async def get_final_walking_time(orig, dest):
        """
        获取从起点到终点的最终步行时间
        如果步行时间超过30分钟，自动切换到公交时间
        返回: (时间秒数, 交通模式, 原始步行时间)
        """
        try:
            orig_str = f"{orig[0]},{orig[1]}"
            dest_str = f"{dest[0]},{dest[1]}"
            
            # 1. 调用百度步行API
            async with httpx.AsyncClient(timeout=10) as client:
                walk_resp = await client.get(
                    DIRECTIONLITE_WALKING,
                    params={"origin": orig_str, "destination": dest_str, "ak": BAIDU_MAPS_API_KEY}
                )
                walk_data = walk_resp.json()
                walk_sec = walk_data["result"]["routes"][0]["duration"]
                
                # 2. 如果步行时间超过30分钟，切换到公交
                if walk_sec > 30 * 60:
                    transit_resp = await client.get(
                        DIRECTIONLITE_TRANSIT,
                        params={"origin": orig_str, "destination": dest_str, "ak": BAIDU_MAPS_API_KEY}
                    )
                    transit_data = transit_resp.json()
                    transit_sec = transit_data["result"]["routes"][0]["duration"]
                    return transit_sec, "transit", walk_sec
                else:
                    return walk_sec, "walking", walk_sec
        except Exception as e:
            print(f"获取最终步行时间失败: {e}")
            # 回退：使用直线距离估算
            distance = haversine_km(orig, dest)
            # 步行速度: 5 km/h => 0.083 km/min
            walk_sec = distance / 0.083 * 60
            if walk_sec > 30 * 60:
                # 公共交通速度: 20 km/h => 0.33 km/min
                transit_sec = distance / 0.33 * 60
                return transit_sec, "transit", walk_sec
            else:
                return walk_sec, "walking", walk_sec
    
    # 定义调用百度地图API的函数
    async def call_route_matrix_api(mode):
        """调用百度地图API并返回响应"""
        if mode in ["driving", "walking"]:
            # 使用原有的路网矩阵API
            if mode == "driving":
                matrix_url = ROUTEMATRIX_DRIVING
            else:
                matrix_url = ROUTEMATRIX_WALKING
            
            matrix_params = {
                "output": "json",
                "ak": BAIDU_MAPS_API_KEY,
                "origins": origins,
                "destinations": destinations,
            }

            # 调用路网矩阵 - 优化并发处理
            print(f"开始调用百度路网矩阵API（{mode}），origins: {origins}, destinations: {destinations}")
            
            # 并发请求限制优化：实现简单的延迟重试机制
            max_retries = 3
            retry_delay = 1  # 初始延迟时间（秒）
            matrix_resp = None
            
            for retry in range(max_retries):
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        matrix_resp = await client.get(matrix_url, params=matrix_params)
                        print(f"百度路网矩阵API返回状态码: {matrix_resp.status_code}")
                        
                        # 检查是否因并发限制导致请求失败
                        if matrix_resp.status_code == 429 or (matrix_resp.status_code == 200 and 
                           matrix_resp.json().get('status') == 429):
                            print(f"百度路网矩阵API并发限制，第{retry+1}次重试...")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                            continue
                        break
                except httpx.RequestError as e:
                    print(f"百度路网矩阵API请求异常（第{retry+1}次）: {str(e)}")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
            
            return matrix_resp
        elif mode == "transit":
            # 只对超过步行时间阈值的POI使用transit
            # 获取超过30分钟的POI索引
            top_pois = raw_results[:6]  # 最多处理前6个POI
            
            # 使用连接池复用client
            async with httpx.AsyncClient(timeout=10) as client:
                # 定义获取单个起点到POI的公交时间的函数
                async def fetch_transit_time(orig, poi):
                    """获取单个起点到POI的公交时间"""
                    orig_str = f"{orig[0]},{orig[1]}"
                    dest_str = f"{poi[0]},{poi[1]}"
                    
                    try:
                        resp = await client.get(
                            DIRECTIONLITE_TRANSIT,
                            params={"origin": orig_str, "destination": dest_str, "ak": BAIDU_MAPS_API_KEY}
                        )
                        
                        if resp.status_code != 200:
                            return None
                        
                        data = resp.json()
                        if data.get("status") != 0 or not data.get("result") or not data["result"].get("routes"):
                            return None
                        
                        # 获取导航时间（秒）
                        route = data["result"]["routes"][0]
                        return route.get("duration", 0)
                    except Exception as e:
                        print(f"获取公交时间失败 (orig: {orig}, poi: {poi}): {str(e)}")
                        return None
                
                # 定义处理单个POI的函数
                async def process_poi(poi):
                    """处理单个POI，获取平均公交时间"""
                    poi_coord = (float(poi['location']['lat']), float(poi['location']['lng']))
                    
                    # 并发获取所有起点到该POI的公交时间
                    tasks = [fetch_transit_time(orig, poi_coord) for orig in cleaned_coords]
                    results = await asyncio.gather(*tasks)
                    
                    # 过滤掉None结果
                    valid_results = [r for r in results if r is not None]
                    
                    if valid_results:
                        # 返回平均时间（秒）
                        return sum(valid_results) / len(valid_results)
                    else:
                        # 如果公交API调用失败，使用驾车时间×1.1估算
                        avg_distance = sum(haversine_km(orig, poi_coord) for orig in cleaned_coords) / len(cleaned_coords)
                        # 驾车速度估算: 30 km/h => 0.5 km/min
                        driving_time_est = avg_distance / 0.5 * 60  # 转换为秒
                        return driving_time_est * 1.1  # 公交比驾车慢10%
                
                # 并发处理所有需要公交时间的POI
                all_results = await asyncio.gather(*(process_poi(poi) for poi in top_pois))
            
            # 返回自定义的响应格式，包含所有POI的平均时间
            return {"poi_durations": all_results}
    
    # 定义解析路网矩阵响应的函数
    def parse_matrix_response(resp, mode, raw_results, cleaned_coords):
        """解析路网矩阵响应并返回平均时长"""
        # 步行时间阈值（分钟）
        WALKING_TIME_THRESHOLD = 30.0
        print(f"parse_matrix_response函数内的WALKING_TIME_THRESHOLD: {WALKING_TIME_THRESHOLD}分钟")
        
        # 1. 首先处理步行模式，确保使用ROUTEMATRIX_WALKING
        if mode == "walking" and not (isinstance(resp, dict) and "poi_durations" in resp):
            # 这是步行路网矩阵API的响应
            if resp is None or resp.status_code != 200:
                print("步行路网矩阵API调用失败，使用距离兜底")
                candidates = []
                for item in raw_results[:6]:
                    name = item.get('name')
                    addr = item.get('address', '')
                    lat = float(item['location']['lat']); lon = float(item['location']['lng'])
                    uid = item.get('uid', '')
                    baidu_map_url = f"https://api.map.baidu.com/place/detail?query={name}&region=上海&output=html"
                    
                    # 使用距离估算步行时间
                    avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
                    avg_travel_time_min = round(avg_km / 0.083, 1)  # 步行5km/h
                    
                    candidates.append(POI(name=name, addr=addr, lat=lat, lon=lon, avg_travel_time_min=avg_travel_time_min, url=baidu_map_url, uid=uid, raw=item))
                
                # 计算总体平均时间
                avg_travel_times = [c.avg_travel_time_min for c in candidates if c.avg_travel_time_min is not None]
                overall_avg_time = sum(avg_travel_times) / len(avg_travel_times) if avg_travel_times else None
                candidates.sort(key=lambda x: (x.avg_travel_time_min is None, x.avg_travel_time_min))
                return candidates, "步行路网矩阵API调用失败", "network_exception", True, overall_avg_time
            
            try:
                matrix_json = resp.json()
            except Exception as e:
                print(f"步行路网矩阵JSON解析失败: {str(e)}")
                candidates = []
                for item in raw_results[:6]:
                    name = item.get('name')
                    addr = item.get('address', '')
                    lat = float(item['location']['lat']); lon = float(item['location']['lng'])
                    uid = item.get('uid', '')
                    baidu_map_url = f"https://api.map.baidu.com/place/detail?query={name}&region=上海&output=html"
                    
                    # 使用距离估算步行时间
                    avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
                    avg_travel_time_min = round(avg_km / 0.083, 1)  # 步行5km/h
                    
                    candidates.append(POI(name=name, addr=addr, lat=lat, lon=lon, avg_travel_time_min=avg_travel_time_min, url=baidu_map_url, uid=uid, raw=item))
                
                # 计算总体平均时间
                avg_travel_times = [c.avg_travel_time_min for c in candidates if c.avg_travel_time_min is not None]
                overall_avg_time = sum(avg_travel_times) / len(avg_travel_times) if avg_travel_times else None
                candidates.sort(key=lambda x: (x.avg_travel_time_min is None, x.avg_travel_time_min))
                return candidates, "步行路网矩阵JSON解析失败", "json_parse_error", True, overall_avg_time
            
            # 解析步行路网矩阵响应
            if matrix_json.get('status') != 0 or not matrix_json.get('result'):
                print("步行路网矩阵API返回失败状态")
                candidates = []
                for item in raw_results[:6]:
                    name = item.get('name')
                    addr = item.get('address', '')
                    lat = float(item['location']['lat']); lon = float(item['location']['lng'])
                    uid = item.get('uid', '')
                    baidu_map_url = f"https://api.map.baidu.com/place/detail?query={name}&region=上海&output=html"
                    
                    # 使用距离估算步行时间
                    avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
                    avg_travel_time_min = round(avg_km / 0.083, 1)  # 步行5km/h
                    
                    candidates.append(POI(name=name, addr=addr, lat=lat, lon=lon, avg_travel_time_min=avg_travel_time_min, url=baidu_map_url, uid=uid, raw=item))
                
                # 计算总体平均时间
                avg_travel_times = [c.avg_travel_time_min for c in candidates if c.avg_travel_time_min is not None]
                overall_avg_time = sum(avg_travel_times) / len(avg_travel_times) if avg_travel_times else None
                candidates.sort(key=lambda x: (x.avg_travel_time_min is None, x.avg_travel_time_min))
                return candidates, "步行路网矩阵API返回失败状态", "api_error", True, overall_avg_time
            
            # 解析步行时间
            candidates = []
            avg_travel_times = []
            result = matrix_json.get('result', {})
            
            # 处理百度地图API返回的result可能是列表的情况
            if isinstance(result, list):
                # 如果result是列表，取第一个元素
                result = result[0] if result else {}
            
            elements = result.get('elements', [])
            
            for idx, item in enumerate(raw_results[:6]):
                name = item.get('name')
                addr = item.get('address', '')
                lat = float(item['location']['lat']); lon = float(item['location']['lng'])
                uid = item.get('uid', '')
                baidu_map_url = f"https://api.map.baidu.com/place/detail?query={name}&region=上海&output=html"
                
                # 计算平均步行时间
                total_duration = 0
                valid_count = 0
                
                for origin_idx in range(len(cleaned_coords)):
                    elem_idx = idx * len(cleaned_coords) + origin_idx
                    if elem_idx < len(elements):
                        element = elements[elem_idx]
                        if element.get('status') == 0 and 'duration' in element:
                            total_duration += element['duration']['value']
                            valid_count += 1
                
                if valid_count > 0:
                    avg_travel_time_min = round(total_duration / valid_count / 60, 1)
                else:
                    # 使用距离估算
                    avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
                    avg_travel_time_min = round(avg_km / 0.083, 1)  # 步行5km/h
                
                candidates.append(POI(name=name, addr=addr, lat=lat, lon=lon, avg_travel_time_min=avg_travel_time_min, url=baidu_map_url, uid=uid, raw=item))
                avg_travel_times.append(avg_travel_time_min)
            
            # 计算总体平均时间
            overall_avg_time = sum(avg_travel_times) / len(avg_travel_times) if avg_travel_times else None
            print(f"{mode}方式的总体平均出行时间: {overall_avg_time:.1f}分钟")
            
            # 按照平均时长排序
            candidates.sort(key=lambda x: (x.avg_travel_time_min is None, x.avg_travel_time_min))
            return candidates, None, None, False, overall_avg_time
        
        # 2. 处理公交模式的自定义响应
        if mode == "transit" and isinstance(resp, dict) and "poi_durations" in resp:
            candidates = []
            avg_travel_times = []
            # 只处理与poi_durations长度相同的POI数量
            processed_count = len(resp["poi_durations"])
            for idx, item in enumerate(raw_results[:processed_count]):
                name = item.get('name')
                addr = item.get('address', '')
                lat = float(item['location']['lat']); lon = float(item['location']['lng'])
                uid = item.get('uid', '')
                # 构造百度地图URL（可在微信中打开）
                baidu_map_url = f"https://api.map.baidu.com/place/detail?query={name}&region=上海&output=html"

                # 计算平均时长（分钟）
                avg_travel_time_min = round(resp["poi_durations"][idx] / 60, 1)
                candidates.append(POI(name=name, addr=addr, lat=lat, lon=lon, avg_travel_time_min=avg_travel_time_min, url=baidu_map_url, uid=uid, raw=item))
                avg_travel_times.append(avg_travel_time_min)

            # 计算总体平均时间
            overall_avg_time = None
            if avg_travel_times:
                overall_avg_time = sum(avg_travel_times) / len(avg_travel_times)
                print(f"{mode}方式的总体平均出行时间: {overall_avg_time:.1f}分钟")

            # 按照平均时长排序
            candidates.sort(key=lambda x: (x.avg_travel_time_min is None, x.avg_travel_time_min))
            return candidates, None, None, False, overall_avg_time
            
        if resp is None:
            # 所有重试都失败，回退到直线距离估算
            print("所有百度路网矩阵API请求尝试均失败，回退到直线距离估算")
            candidates = []
            for item in raw_results:
                lat = float(item['location']['lat']); lon = float(item['location']['lng'])
                avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
                # 估速：步行 5 km/h => 0.083 km/min，公共交通 20 km/h => 0.33 km/min
                if mode == "walking":
                    avg_min = avg_km / 0.083
                elif mode == "transit":
                    avg_min = avg_km / 0.33
                else:
                    avg_min = avg_km / 0.5  # 驾车
                candidates.append(POI(name=item.get('name'), addr=item.get('address',''), lat=lat, lon=lon, avg_travel_time_min=round(avg_min,1), raw=item))
            candidates.sort(key=lambda x: x.avg_travel_time_min)
            return candidates, f"路网矩阵请求失败，退回直线估算", "network_exception", True, None

        if resp.status_code != 200:
            # 记录HTTP错误状态码
            print(f"百度路网矩阵API返回HTTP错误状态码: {resp.status_code}")
            # 回退为直线估算
            candidates = []
            for item in raw_results:
                lat = float(item['location']['lat']); lon = float(item['location']['lng'])
                avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
                # 根据不同交通模式使用不同的估算速度
                if mode == "walking":
                    avg_min = avg_km / 0.083  # 步行: 5 km/h => 0.083 km/min
                elif mode == "transit":
                    avg_min = avg_km / 0.33  # 公共交通: 20 km/h => 0.33 km/min
                else:
                    avg_min = avg_km / 0.5  # 驾车: 30 km/h => 0.5 km/min
                candidates.append(POI(name=item.get('name'), addr=item.get('address',''), lat=lat, lon=lon, avg_travel_time_min=round(avg_min,1), raw=item))
            candidates.sort(key=lambda x: (x.avg_travel_time_min is None, x.avg_travel_time_min))
            return candidates, f"路网矩阵 HTTP {resp.status_code}, 已退回{mode}直线估算", "http_error", True, None

        try:
            matrix_json = resp.json()
            print(f"百度路网矩阵API返回JSON数据: {matrix_json}")
            # 输出更详细的响应结构
            print(f"响应结构: {list(matrix_json.keys())}")
            print(f"status字段值: {matrix_json.get('status')}, 类型: {type(matrix_json.get('status'))}")
            print(f"result字段值: {matrix_json.get('result')}, 类型: {type(matrix_json.get('result'))}")
        except Exception as e:
            # 记录JSON解析错误
            print(f"百度路网矩阵API返回数据JSON解析失败: {str(e)}")
            candidates = []
            for item in raw_results:
                lat = float(item['location']['lat']); lon = float(item['location']['lng'])
                avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
                # 根据不同交通模式使用不同的估算速度
                if mode == "walking":
                    avg_min = avg_km / 0.083  # 步行: 5 km/h => 0.083 km/min
                elif mode == "transit":
                    avg_min = avg_km / 0.33  # 公共交通: 20 km/h => 0.33 km/min
                else:
                    avg_min = avg_km / 0.5  # 驾车: 30 km/h => 0.5 km/min
                candidates.append(POI(name=item.get('name'), addr=item.get('address',''), lat=lat, lon=lon, avg_travel_time_min=round(avg_min,1), raw=item))
            candidates.sort(key=lambda x: (x.avg_travel_time_min is None, x.avg_travel_time_min))
            return candidates, f"路网矩阵返回非JSON，已退回{mode}直线估算", "json_parse_error", True, None

        # 百度地图API返回的status字段是字符串类型，需要转换为数字
        status = matrix_json.get("status")
        try:
            status_code = int(status)
            print(f"转换后status_code: {status_code}, 类型: {type(status_code)}")
        except (ValueError, TypeError) as e:
            status_code = -1
            print(f"status字段转换失败: {str(e)}, status值: {status}, 类型: {type(status)}")
        
        if status_code != 0:
            # 记录API错误信息
            error_msg = matrix_json.get('message', '未知错误')
            print(f"百度路网矩阵API返回错误状态码: {status}, 错误信息: {error_msg}")
            candidates = []
            for item in raw_results:
                lat = float(item['location']['lat']); lon = float(item['location']['lng'])
                avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
                # 根据不同交通模式使用不同的估算速度
                if mode == "walking":
                    avg_min = avg_km / 0.083  # 步行: 5 km/h => 0.083 km/min
                elif mode == "transit":
                    avg_min = avg_km / 0.33  # 公共交通: 20 km/h => 0.33 km/min
                else:
                    avg_min = avg_km / 0.5  # 驾车: 30 km/h => 0.5 km/min
                candidates.append(POI(name=item.get('name'), addr=item.get('address',''), lat=lat, lon=lon, avg_travel_time_min=round(avg_min,1), raw=item))
            candidates.sort(key=lambda x: (x.avg_travel_time_min is None, x.avg_travel_time_min))
            return candidates, f"路网矩阵返回错误: {error_msg}, 已退回{mode}直线估算", "api_error", True, None

        # 解析 matrix elements（origin 列表，每个 origin 包含 destination 列表）
        try:
            # 百度地图API返回的result是一个列表，每个元素对应一个起点
            elements = matrix_json.get('result', [])
            print(f"成功获取result字段，elements数量: {len(elements)}")
            print(f"elements内容: {elements}")
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
            return candidates, "路网矩阵响应格式不符，已退回直线估算", "format_error", True, None

        # 累加 duration（秒）并统计有效条数
        dest_count = len(raw_results)
        dest_durations = [0.0] * dest_count
        dest_valid_counts = [0] * dest_count

        # 检查elements的结构
        print(f"elements类型: {type(elements)}")
        if not isinstance(elements, list):
            print(f"elements不是列表类型，尝试直接作为结果处理")
            elements = [elements]

        for i, origin_elem in enumerate(elements):
            print(f"第{i}个origin_elem类型: {type(origin_elem)}, 内容: {origin_elem}")
            if not isinstance(origin_elem, list):
                # 如果不是列表，直接作为一个结果处理
                origin_elem = [origin_elem]
            
            for j, elem in enumerate(origin_elem):
                print(f"第{i}个origin的第{j}个elem类型: {type(elem)}, 内容: {elem}")
                if not isinstance(elem, dict):
                    continue
                
                # 检查duration字段
                duration = elem.get("duration")
                print(f"duration字段值: {duration}, 类型: {type(duration)}")
                
                if isinstance(duration, dict) and 'value' in duration:
                    try:
                        duration_seconds = float(duration['value'])
                        print(f"解析到有效时长: {duration_seconds}秒")
                        if j < dest_count:
                            dest_durations[j] += duration_seconds
                            dest_valid_counts[j] += 1
                            print(f"更新目的地{j}的总时长为{dest_durations[j]}秒，有效次数为{dest_valid_counts[j]}")
                    except Exception as e:
                        print(f"解析时长失败: {str(e)}")
                        continue

        candidates = []
        avg_travel_times = []
        for idx, item in enumerate(raw_results):
            name = item.get('name')
            addr = item.get('address', '')
            lat = float(item['location']['lat']); lon = float(item['location']['lng'])
            uid = item.get('uid', '')
            # 构造百度地图URL（可在微信中打开）
            baidu_map_url = f"https://api.map.baidu.com/place/detail?query={name}&region=上海&output=html"

            # 计算平均时长（分钟），避免除零错误
            # 注意：dest_durations是总时长，需要除以起点数量得到平均值
            if dest_valid_counts[idx] > 0:
                avg_travel_time_min = round(dest_durations[idx] / dest_valid_counts[idx] / 60, 1)
                print(f"POI {name} 的原始平均步行时间: {avg_travel_time_min:.1f}分钟")
                
                # 如果当前是步行模式，且某个POI的步行时间超过30分钟，自动切换为公交时间
                if mode == "walking" and avg_travel_time_min > WALKING_TIME_THRESHOLD:
                    print(f"POI {name} 的步行时间 {avg_travel_time_min:.1f}分钟超过阈值 {WALKING_TIME_THRESHOLD}分钟，自动切换为公共交通时间")
                    # 使用直线距离估算公共交通时间
                    avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
                    # 公共交通平均速度约20km/h（含换乘时间）
                    avg_travel_time_min = round(avg_km / 20.0 * 60, 1)
                    travel_mode = "transit"
                    print(f"POI {name} 的公共交通时间（估算）: {avg_travel_time_min:.1f}分钟")
                else:
                    travel_mode = "walking"
                    print(f"POI {name} 的最终交通时间: {avg_travel_time_min:.1f}分钟")
            else:
                # 如果没有有效时长数据，使用直线距离估算
                avg_km = sum(haversine_km(c, (lat, lon)) for c in cleaned_coords) / len(cleaned_coords)
                # 根据交通模式选择不同的速度估算时间
                if mode == "walking":
                    # 步行速度约5km/h
                    walk_time_min = round(avg_km / 5.0 * 60, 1)
                    # 如果步行时间超过30分钟，自动切换为公交时间
                    if walk_time_min > WALKING_TIME_THRESHOLD:
                        print(f"POI {name} 的步行时间（估算）{walk_time_min:.1f}分钟超过阈值 {WALKING_TIME_THRESHOLD}分钟，自动切换为公共交通时间")
                        # 公共交通平均速度约20km/h（含换乘时间）
                        avg_travel_time_min = round(avg_km / 20.0 * 60, 1)
                        travel_mode = "transit"
                    else:
                        avg_travel_time_min = walk_time_min
                        travel_mode = "walking"
                elif mode == "transit":
                    # 公共交通平均速度约20km/h（含换乘时间）
                    avg_travel_time_min = round(avg_km / 20.0 * 60, 1)
                    travel_mode = "transit"
                else:
                    # 其他模式默认使用步行速度
                    avg_travel_time_min = round(avg_km / 5.0 * 60, 1)
                    travel_mode = "walking"
            
            candidates.append(POI(name=name, addr=addr, lat=lat, lon=lon, avg_travel_time_min=avg_travel_time_min, travel_mode=travel_mode, url=baidu_map_url, uid=uid, raw=item))
            avg_travel_times.append(avg_travel_time_min)

        # 计算总体平均时间
        overall_avg_time = None
        if avg_travel_times:
            overall_avg_time = sum(avg_travel_times) / len(avg_travel_times)
            print(f"{mode}方式的总体平均出行时间: {overall_avg_time:.1f}分钟")

        # 按照平均时长排序，将None值放在列表末尾
        candidates.sort(key=lambda x: (x.avg_travel_time_min is None, x.avg_travel_time_min))
        
        return candidates, None, None, False, overall_avg_time
    
    # 实现统一策略：步行≤30分钟用ROUTEMATRIX_WALKING，步行>30分钟用TRANSIT(lite，仅前3个POI)
    
    # 步骤1：先使用步行矩阵API获取所有POI的真实步行时间
    matrix_resp = await call_route_matrix_api("walking")
    candidates, note, error_type, is_fallback, _ = parse_matrix_response(matrix_resp, "walking", raw_results, cleaned_coords)
    
    # 步骤2：检查每个POI，如果步行时间>30分钟，则对前3个POI使用公交lite API
    # 收集需要使用公交计算的POI索引
    transit_needed_indices = []
    for idx, poi in enumerate(candidates):
        if poi.avg_travel_time_min and poi.avg_travel_time_min > WALKING_TIME_THRESHOLD:
            transit_needed_indices.append(idx)
    
    # 只对前3个需要公交的POI进行公交计算
    transit_needed_indices = transit_needed_indices[:3]
    
    if transit_needed_indices:
        print(f"对前 {len(transit_needed_indices)} 个步行时间超过 {WALKING_TIME_THRESHOLD}分钟的POI使用公交lite API")
        
        # 获取需要公交计算的POI详情
        transit_pois = [raw_results[idx] for idx in transit_needed_indices]
        
        # 步骤3：对这些POI使用公交lite API获取真实公交时间
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 并发获取所有需要公交计算的POI的时间
            async def fetch_transit_time(poi_idx, poi):
                try:
                    # 获取POI坐标
                    poi_lat = float(poi['location']['lat'])
                    poi_lon = float(poi['location']['lng'])
                    poi_coord = f"{poi_lon},{poi_lat}"
                    
                    # 对每个起点计算公交时间
                    total_duration = 0
                    valid_count = 0
                    
                    for origin in cleaned_coords:
                        origin_coord = f"{origin[1]},{origin[0]}"
                        
                        # 调用公交lite API，设置超时时间
                        try:
                            resp = await client.get(DIRECTIONLITE_TRANSIT, params={
                                "origin": origin_coord,
                                "destination": poi_coord,
                                "ak": BAIDU_MAPS_API_KEY
                            }, timeout=10.0)
                          
                            if resp.status_code == 200:
                                json_data = resp.json()
                                if json_data.get('status') == 0 and json_data.get('result'):
                                    # 获取公交时间（秒）
                                    transit_duration = json_data['result'].get('duration', 0)
                                    total_duration += transit_duration
                                    valid_count += 1
                        except Exception as e:
                            print(f"计算起点到POI的公交时间失败: {str(e)}")
                            continue
                    
                    # 计算平均公交时间
                    if valid_count > 0:
                        avg_transit_time_min = round(total_duration / valid_count / 60, 1)
                        return poi_idx, avg_transit_time_min
                    else:
                        # 公交API失败，尝试使用driving×1.1
                        print(f"POI {poi['name']} 的公交API失败，尝试使用driving×1.1")
                        
                        # 调用driving矩阵API
                        driving_resp = await call_route_matrix_api("driving")
                        driving_candidates, _, _, _, _ = parse_matrix_response(driving_resp, "driving", raw_results, cleaned_coords)
                        
                        if driving_candidates[poi_idx].avg_travel_time_min:
                            # driving时间×1.1作为公交时间
                            return poi_idx, round(driving_candidates[poi_idx].avg_travel_time_min * 1.1, 1)
                        else:
                            return poi_idx, None
                except Exception as e:
                    print(f"处理POI {poi.get('name', '')} 公交时间失败: {str(e)}")
                    return poi_idx, None
            
            # 并发执行所有公交时间请求
            results = await asyncio.gather(*[fetch_transit_time(idx, poi) for idx, poi in zip(transit_needed_indices, transit_pois)])
            
            # 更新POI的平均时间和出行方式
            for poi_idx, transit_time in results:
                if transit_time:
                    candidates[poi_idx].avg_travel_time_min = transit_time
                    candidates[poi_idx].travel_mode = "transit"
                    print(f"更新POI {candidates[poi_idx].name} 的时间为公交时间: {transit_time:.1f}分钟，出行方式: 公交")
    
    # 重新计算总体平均时间
    avg_travel_times = [poi.avg_travel_time_min for poi in candidates if poi.avg_travel_time_min]
    overall_avg_time = None
    if avg_travel_times:
        overall_avg_time = sum(avg_travel_times) / len(avg_travel_times)
        print(f"最终总体平均出行时间: {overall_avg_time:.1f}分钟")
    
    # 系统会根据距离自动选择最优出行方式
    note = "系统已根据距离自动选择最优出行方式" if not note else note
    
    # 移除单独获取展示用时间的逻辑，直接使用已计算的平均时间
    # 限制返回的POI数量为6个以提高性能
    candidates = candidates[:6]
    
    # 构造返回结果
    result_data = {"center": center, "candidates": [c.dict() for c in candidates[:6]]}
    if note:
        result_data["note"] = note
    if error_type:
        result_data["api_error_type"] = error_type
    
    return {"success": True, "data": result_data}

