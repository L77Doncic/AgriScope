let map;
let adminLayer;
let gridLayer;
let gridVisible = false;

const state = {
  selectedAdmin: null,
  lastBbox: null,
  adminIndex: {},
  provinces: [],
  citiesByProvince: {},
  districtsByCity: {},
  provinceNames: {},
  cityNames: {},
  latestSensor: null,
  weather: null,
};

function initMap() {
  map = L.map("map", { zoomControl: false }).setView([35.8617, 104.1954], 4.5);
  L.control.zoom({ position: "bottomright" }).addTo(map);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "© OpenStreetMap",
  }).addTo(map);

  setSelectsEnabled(false);
  document.getElementById("mapInfo").innerText = "正在加载行政区数据...";
  fetch("/static/geo/china_admin_sample.geojson")
    .then((res) => res.json())
    .then((geo) => {
      adminLayer = L.featureGroup().addTo(map);
      addFeaturesInChunks(geo.features || [], 300, () => {
        map.fitBounds(adminLayer.getBounds(), { padding: [30, 30] });
        buildAdminHierarchy();
        populateProvinceSelect();
        setSelectsEnabled(true);
        document.getElementById("mapInfo").innerText = "选择一个市区县以查看数据";
      });
    })
    .catch(() => {
      document.getElementById("mapInfo").innerText = "未加载行政区 GeoJSON，请替换 static/geo/china_admin_sample.geojson";
      setSelectsEnabled(true);
    });
}

function selectAdmin(feature, layer) {
  const props = feature.properties || {};
  const name = props.name || "未知区域";
  const adminCode = props.adcode || "";
  state.selectedAdmin = adminCode;
  const bbox = layer.getBounds();
  state.lastBbox = [bbox.getWest(), bbox.getSouth(), bbox.getEast(), bbox.getNorth()];
  document.getElementById("mapInfo").innerText = `${name} (${adminCode})`;
  const cityCode = String(adminCode).slice(0, 4) + "00";
  const provCode = String(adminCode).slice(0, 2) + "0000";
  setSelectValue("provinceSelect", provCode);
  onProvinceChange();
  setSelectValue("citySelect", cityCode);
  onCityChange();
  setSelectValue("districtSelect", adminCode);
  refreshGrid();
  refreshSensors();
  refreshWeather();
}

function renderGrid(cells) {
  if (gridLayer) {
    gridLayer.remove();
  }
  gridLayer = L.layerGroup();
  cells.forEach((cell) => {
    const [minLon, minLat, maxLon, maxLat] = cell.bbox;
    const rect = L.rectangle(
      [
        [minLat, minLon],
        [maxLat, maxLon],
      ],
      { color: "#1f1b16", weight: 1, fillOpacity: 0.05 }
    );
    gridLayer.addLayer(rect);
  });
  if (gridVisible) {
    gridLayer.addTo(map);
  }
}

function refreshGrid() {
  if (!state.lastBbox) return;
  const res = document.getElementById("gridResolution").value || "1";
  const bboxStr = state.lastBbox.join(",");
  fetch(`/api/grid?bbox=${bboxStr}&resolution_km=${res}`)
    .then((res) => res.json())
    .then((data) => {
      renderGrid(data.grid || []);
    })
    .catch(() => {});
}

function refreshSensors() {
  const adminCode = document.getElementById("districtSelect").value || "";
  fetch(`/api/latest?admin_code=${adminCode}&limit=50`)
    .then((res) => res.json())
    .then((data) => {
      const rows = data.data || [];
      document.getElementById("deviceCount").innerText = `${rows.length}`;
      const table = document.getElementById("sensorTable");
      table.innerHTML = "";
      rows.slice(0, 6).forEach((row) => {
        const div = document.createElement("div");
        div.className = "table-row";
        div.innerHTML = `
          <div>${row.device_id || "-"}</div>
          <div>${row.payload?.soil_moisture ?? "-"}</div>
          <div>${row.payload?.temperature ?? "-"}</div>
          <div>${row.ts?.slice(0, 19) ?? "-"}</div>
        `;
        table.appendChild(div);
      });
      state.latestSensor = rows.length ? rows[0].payload || {} : null;
      document.getElementById("sensorSoil").innerText =
        state.latestSensor?.soil_moisture ?? "--";
      updateModelInputs();
      tryAutoPredict();
    })
    .catch(() => {});
}

function refreshWeather() {
  if (!state.lastBbox) return;
  const lat = (state.lastBbox[1] + state.lastBbox[3]) / 2;
  const lon = (state.lastBbox[0] + state.lastBbox[2]) / 2;
  fetch(`/api/weather?lat=${lat}&lon=${lon}`)
    .then((res) => res.json())
    .then((data) => {
      const payload = data.data || {};
      const weather = payload.data || {};
      const current = weather.current || {};
      const hourly = weather.hourly || {};
      const temp = current.temperature_2m ?? "--";
      const rain = current.precipitation ?? (hourly.precipitation ? hourly.precipitation[0] : "--");
      const radiation = hourly.shortwave_radiation ? hourly.shortwave_radiation[0] : "--";
      const humidity = current.relative_humidity_2m ?? "--";
      const wind = current.wind_speed_10m ?? "--";
      const cloud = current.cloud_cover ?? "--";
      const eto = current.et0_fao_evapotranspiration ?? "--";
      state.weather = { temp, rain, radiation, humidity, wind, cloud, eto };
      updateModelInputs();
      tryAutoPredict();
    })
    .catch(() => {});
}

function runPrediction() {
  const result = buildFeatureVector();
  if (!result.ok) {
    showToast(`预测缺少参数：${result.missing.join("、")}`);
    return;
  }
  const features = result.features;

  fetch("/api/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ features }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.error) {
        document.getElementById("latestPrediction").innerText = "--";
        document.getElementById("latestSuggestion").innerText = data.error;
        renderLlmSuggestion(null);
        return;
      }
      document.getElementById("latestPrediction").innerText = data.prediction.toFixed(3);
      document.getElementById("latestSuggestion").innerText = data.suggestion;
      document.getElementById("suggestionBox").innerText = data.suggestion;
      renderLlmSuggestion(data.suggestion);
    })
    .catch(() => {});
}

function bindUI() {
  document.getElementById("refreshBtn").addEventListener("click", () => {
    refreshSensors();
    refreshGrid();
    refreshWeather();
    centerToSelection();
  });
  document.getElementById("predictBtn").addEventListener("click", () => {
    runPrediction();
  });
  document.getElementById("toggleGridBtn").addEventListener("click", () => {
    gridVisible = !gridVisible;
    if (gridLayer) {
      if (gridVisible) {
        gridLayer.addTo(map);
      } else {
        gridLayer.remove();
      }
    }
  });

  document.getElementById("provinceSelect").addEventListener("change", onProvinceChange);
  document.getElementById("citySelect").addEventListener("change", onCityChange);
  document.getElementById("districtSelect").addEventListener("change", onDistrictChange);
  document.getElementById("districtSearch").addEventListener("input", onSearchInput);
  document.addEventListener("click", (e) => {
    const results = document.getElementById("searchResults");
    if (!results.contains(e.target) && e.target.id !== "districtSearch") {
      results.style.display = "none";
    }
  });
}

initMap();
bindUI();

function buildAdminHierarchy() {
  state.adminIndex = {};
  state.provinces = [];
  state.citiesByProvince = {};
  state.districtsByCity = {};
  state.provinceNames = {};
  state.cityNames = {};
  adminLayer.eachLayer((layer) => {
    const props = layer.feature?.properties || {};
    const code = String(props.adcode || "");
    const name = props.name || "未知区域";
    const provinceName =
      props.province_name || props.provinceName || props.province || props.PROVINCE || "";
    const cityName = props.city_name || props.cityName || props.city || props.CITY || "";
    if (!code) return;
    state.adminIndex[code] = layer;
    if (code.length === 6) {
      const provCode = code.slice(0, 2) + "0000";
      const cityCode = code.slice(0, 4) + "00";
      if (provinceName) state.provinceNames[provCode] = provinceName;
      if (cityName) state.cityNames[cityCode] = cityName;
      if (!state.districtsByCity[cityCode]) state.districtsByCity[cityCode] = [];
      state.districtsByCity[cityCode].push({ code, name });
      if (!state.citiesByProvince[provCode]) state.citiesByProvince[provCode] = [];
      if (!state.citiesByProvince[provCode].some((c) => c.code === cityCode)) {
        state.citiesByProvince[provCode].push({
          code: cityCode,
          name: cityName || cityCode,
        });
      }
      if (!state.provinces.some((p) => p.code === provCode)) {
        state.provinces.push({
          code: provCode,
          name: provinceName || provCode,
        });
      }
    }
  });
}

function addFeaturesInChunks(features, chunkSize, done) {
  let index = 0;
  const options = {
    style: {
      color: "#1a8a5b",
      weight: 2,
      fillColor: "#f3b24a",
      fillOpacity: 0.2,
    },
    onEachFeature: (feature, layer) => {
      layer.on("click", () => selectAdmin(feature, layer));
    },
  };

  function step() {
    const slice = features.slice(index, index + chunkSize);
    if (!slice.length) {
      done();
      return;
    }
    L.geoJSON({ type: "FeatureCollection", features: slice }, options).addTo(adminLayer);
    index += chunkSize;
    setTimeout(step, 0);
  }
  step();
}

function populateProvinceSelect() {
  const select = document.getElementById("provinceSelect");
  select.innerHTML = "<option value=\"\">请选择省</option>";
  state.provinces
    .map((p) => ({
      code: p.code,
      name: p.name || state.provinceNames[p.code] || "未知省",
    }))
    .sort((a, b) => a.name.localeCompare(b.name, "zh-Hans-CN"))
    .forEach((p) => {
      const opt = document.createElement("option");
      opt.value = p.code;
      opt.textContent = `${p.name} (${p.code})`;
      select.appendChild(opt);
    });
  if (select.options.length === 1) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "未加载行政区数据";
    select.appendChild(opt);
  }
}

function onProvinceChange() {
  const provCode = document.getElementById("provinceSelect").value;
  const citySelect = document.getElementById("citySelect");
  const districtSelect = document.getElementById("districtSelect");
  citySelect.disabled = !provCode;
  districtSelect.disabled = true;
  citySelect.innerHTML = "<option value=\"\">请选择市</option>";
  districtSelect.innerHTML = "<option value=\"\">请选择县/区</option>";
  if (!provCode) return;

  const cities = state.citiesByProvince[provCode] || [];
  cities
    .map((c) => ({ code: c.code, name: c.name || state.cityNames[c.code] || "未知市" }))
    .sort((a, b) => a.name.localeCompare(b.name, "zh-Hans-CN"))
    .forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.code;
      opt.textContent = `${c.name} (${c.code})`;
      citySelect.appendChild(opt);
    });
}

function onCityChange() {
  const cityCode = document.getElementById("citySelect").value;
  const districtSelect = document.getElementById("districtSelect");
  districtSelect.disabled = !cityCode;
  districtSelect.innerHTML = "<option value=\"\">请选择县/区</option>";
  if (!cityCode) return;
  const districts = state.districtsByCity[cityCode] || [];
  districts
    .sort((a, b) => a.name.localeCompare(b.name, "zh-Hans-CN"))
    .forEach((d) => {
      const opt = document.createElement("option");
      opt.value = d.code;
      opt.textContent = `${d.name} (${d.code})`;
      districtSelect.appendChild(opt);
    });
}

function onDistrictChange() {
  const code = document.getElementById("districtSelect").value;
  const layer = state.adminIndex[code];
  if (layer) {
    selectAdmin(layer.feature, layer);
    map.fitBounds(layer.getBounds(), { padding: [30, 30] });
  }
}

function onSearchInput(e) {
  const value = e.target.value.trim();
  const results = document.getElementById("searchResults");
  results.innerHTML = "";
  if (!value) {
    results.style.display = "none";
    return;
  }
  const matches = Object.keys(state.adminIndex)
    .filter((code) => {
      const name = state.adminIndex[code]?.feature?.properties?.name || "";
      return name.includes(value) || code.includes(value);
    })
    .slice(0, 12);
  matches.forEach((code) => {
    const name = state.adminIndex[code].feature.properties.name || "未知区域";
    const div = document.createElement("div");
    div.className = "search-item";
    div.textContent = `${name} (${code})`;
    div.addEventListener("click", () => {
      results.style.display = "none";
      pickByCode(code);
    });
    results.appendChild(div);
  });
  results.style.display = matches.length ? "block" : "none";
}

function pickByCode(code) {
  const layer = state.adminIndex[code];
  if (!layer) return;
  const props = layer.feature.properties || {};
  const cityCode = code.slice(0, 4) + "00";
  const provCode = code.slice(0, 2) + "0000";
  setSelectValue("provinceSelect", provCode);
  onProvinceChange();
  setSelectValue("citySelect", cityCode);
  onCityChange();
  setSelectValue("districtSelect", code);
  selectAdmin(layer.feature, layer);
  map.fitBounds(layer.getBounds(), { padding: [30, 30] });
}

function setSelectValue(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  el.value = value;
}

function setSelectsEnabled(enabled) {
  const prov = document.getElementById("provinceSelect");
  const city = document.getElementById("citySelect");
  const dist = document.getElementById("districtSelect");
  if (prov) prov.disabled = !enabled;
  if (city) city.disabled = !enabled;
  if (dist) dist.disabled = !enabled;
}

function centerToSelection() {
  const districtCode = document.getElementById("districtSelect").value;
  const cityCode = document.getElementById("citySelect").value;
  const provCode = document.getElementById("provinceSelect").value;
  if (districtCode && state.adminIndex[districtCode]) {
    map.fitBounds(state.adminIndex[districtCode].getBounds(), { padding: [30, 30] });
    return;
  }
  const bounds = L.latLngBounds();
  let hasBounds = false;
  const prefix = districtCode || cityCode || provCode;
  if (!prefix) return;
  adminLayer.eachLayer((layer) => {
    const code = String(layer.feature?.properties?.adcode || "");
    if (!code) return;
    if (prefix.length === 6 && code === prefix) {
      bounds.extend(layer.getBounds());
      hasBounds = true;
    } else if (prefix.length === 4 && code.startsWith(prefix.slice(0, 4))) {
      bounds.extend(layer.getBounds());
      hasBounds = true;
    } else if (prefix.length === 2 && code.startsWith(prefix.slice(0, 2))) {
      bounds.extend(layer.getBounds());
      hasBounds = true;
    }
  });
  if (hasBounds) {
    map.fitBounds(bounds, { padding: [30, 30] });
  }
}

function renderLlmSuggestion(raw) {
  const container = document.getElementById("llmContent");
  if (!container) return;
  if (!raw) {
    container.textContent = "等待预测结果...";
    return;
  }
  let payload = null;
  try {
    payload = JSON.parse(raw);
  } catch {
    container.textContent = raw;
    return;
  }
  const rows = [];
  if (payload.summary) rows.push(["概述", payload.summary]);
  if (payload.irrigation) rows.push(["灌溉", payload.irrigation]);
  if (payload.fertilization) rows.push(["施肥", payload.fertilization]);
  if (payload.soil) rows.push(["土壤", payload.soil]);
  if (payload.risk) rows.push(["风险", payload.risk]);
  container.innerHTML = "";
  rows.forEach(([label, text]) => {
    const div = document.createElement("div");
    div.className = "llm-item";
    div.innerHTML = `<div class="llm-label">${label}</div><div>${text}</div>`;
    container.appendChild(div);
  });
  if (Array.isArray(payload.actions) && payload.actions.length) {
    const div = document.createElement("div");
    div.className = "llm-item";
    div.innerHTML = `<div class="llm-label">行动</div><div>${payload.actions.join("；")}</div>`;
    container.appendChild(div);
  }
  if (!rows.length && !payload.actions) {
    container.textContent = raw;
  }
}

let toastTimer = null;
function showToast(message) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.remove("show");
  }, 2400);
}

function updateModelInputs() {
  const rain = state.weather?.rain;
  const temp = state.weather?.temp;
  const radiation = state.weather?.radiation;
  const humidity = state.weather?.humidity;
  const wind = state.weather?.wind;
  const cloud = state.weather?.cloud;
  const eto = state.weather?.eto;
  document.getElementById("inputRainfall").innerText = rain ?? "--";
  document.getElementById("inputTemp").innerText = temp ?? "--";
  document.getElementById("inputRadiation").innerText = radiation ?? "--";
  document.getElementById("inputHumidity").innerText = humidity ?? "--";
  document.getElementById("inputWind").innerText = wind ?? "--";
  document.getElementById("inputCloud").innerText = cloud ?? "--";
  document.getElementById("inputEto").innerText = eto ?? "--";
}

function buildFeatureVector() {
  const soil = state.latestSensor?.soil_moisture;
  const rain = state.weather?.rain;
  const missing = [];
  if (soil == null) missing.push("土壤湿度");
  if (rain == null || rain === "--") missing.push("降雨量");
  if (missing.length) {
    return { ok: false, missing };
  }
  return {
    ok: true,
    features: {
      soil_moisture: Number(soil),
      rainfall: Number(rain),
    },
  };
}

function tryAutoPredict() {
  const result = buildFeatureVector();
  if (!result.ok) return;
  runPrediction();
}




