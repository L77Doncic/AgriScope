# 农业管理预测系统 (Flask + CatBoost)

## 启动

1. 训练模型 (可选)

```bash
python CatBoost.py
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 启动服务

```bash
set MODEL_PATH=output/best_catboost_model.cbm
set MODEL_FEATURES=soil_moisture,rainfall,nitrogen
set MQTT_ENABLE=false
python app.py
```

打开 `http://127.0.0.1:5000/`。

## MQTT 数据格式示例

发布到 `sensors/field1`：

```json
{
  "device_id": "dev-1",
  "admin_code": "110105",
  "lat": 39.95,
  "lon": 116.4,
  "soil_moisture": 0.32,
  "temperature": 18.4,
  "rainfall": 1.2,
  "nitrogen": 0.28
}
```

## 气象 API

默认使用 Open-Meteo；如需 ERA5 请在 `services/weather.py` 中替换 `_era5_placeholder`，并设置 `WEATHER_PROVIDER=era5`。

## 大模型建议（ERNIE-5.0）

使用环境变量启用：

```bash
set LLM_ENABLE=true
set LLM_API_KEY=你的密钥
set LLM_BASE_URL=https://aistudio.baidu.com/llm/lmapi/v3
set LLM_MODEL=ernie-5.0-thinking-preview
```

若未启用，将使用内置规则引擎作为回退。

## 中国行政区数据

请将真实行政区 GeoJSON 替换 `static/geo/china_admin_sample.geojson`。

## 性能优化建议

- 传感数据写入批处理或使用消息队列 (MQTT -> Redis -> Worker)。
- 预测接口缓存最近一段时间的结果，避免重复计算。
- 网格渲染采用请求窗口内裁剪，避免一次性加载全中国 1km 网格。
- 模型预加载并复用，避免重复加载。

## 本地开发板部署

- 使用 Python venv，预先编译 CatBoost 依赖。
- 通过 `MQTT_ENABLE=true` 订阅本地网关的传感数据。
- 可以在开发板上关闭 SHAP、训练流程，仅保留 `app.py` 服务。
- 若无公网，气象服务可替换为本地气象站或离线缓存。


## 行政区数据构建

推荐方案：使用阿里云 DataV 行政区 GeoJSON（含 adcode）并转换为 WGS84。

一次全量拉取：

```bash
python scripts\\build_admin_geojson.py --all
```

分批运行（便于断点续跑）：

```bash
python scripts\\build_admin_geojson.py --max-provinces 1
python scripts\\build_admin_geojson.py --finalize
```

说明：DataV 数据为 GCJ-02 坐标，脚本会转换为 WGS84 并输出到 static/geo/china_admin_sample.geojson。

如需更高精度或商业授权，请使用 geojson.cn 的县级数据（付费，WGS84 版本）。

