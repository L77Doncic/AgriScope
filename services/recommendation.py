import json
import os
from typing import Any, Dict, Optional

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


SYSTEM_PROMPT = """\
你是农业管理预测系统的操作建议生成器。请基于输入数据与阈值给出可执行建议，输出必须是严格 JSON。
要求：
1) 仅输出 JSON，不要包含任何多余文本。
2) 数值单位遵循输入字段单位，不要臆造未提供的数据。
3) 结合预测结果与阈值给出明确行动建议。

业务阈值（可根据作物/地区后续调整）：
- soil_moisture_low = 0.25
- soil_moisture_high = 0.45
- rainfall_high = 10.0  (mm)
- nitrogen_low = 0.30
- prediction_low = 0.50

输出 JSON 格式：
{
  "summary": "一句话概述",
  "irrigation": "灌溉建议",
  "fertilization": "施肥建议",
  "soil": "土壤与设备建议",
  "risk": "风险提示",
  "actions": ["行动1", "行动2", "行动3"]
}
"""


class RecommendationEngine:
    def __init__(self):
        self.soil_moisture_low = 0.25
        self.soil_moisture_high = 0.45
        self.rainfall_high = 10.0
        self.nitrogen_low = 0.30
        self.prediction_low = 0.50

        self.llm_enable = os.getenv("LLM_ENABLE", "false").lower() == "true"
        self.llm_api_key = os.getenv("LLM_API_KEY", "")
        self.llm_base_url = os.getenv("LLM_BASE_URL", "https://aistudio.baidu.com/llm/lmapi/v3")
        self.llm_model = os.getenv("LLM_MODEL", "ernie-5.0-thinking-preview")

    def _rule_based(self, features: Dict[str, Any], prediction: float) -> str:
        soil = float(features.get("soil_moisture", 0))
        rainfall = float(features.get("rainfall", 0))
        nitrogen = float(features.get("nitrogen", 0))

        if soil < self.soil_moisture_low and rainfall < self.rainfall_high:
            return "多浇水"
        if soil > self.soil_moisture_high or rainfall >= self.rainfall_high:
            return "少浇水"
        if nitrogen < self.nitrogen_low:
            return "多施肥"
        if prediction < self.prediction_low:
            return "改良土壤并检查灌溉系统"
        return "保持当前管理措施"

    def _llm_suggest(self, features: Dict[str, Any], prediction: float) -> Optional[str]:
        if not self.llm_enable:
            return None
        if OpenAI is None:
            return None
        if not self.llm_api_key:
            return None

        client = OpenAI(api_key=self.llm_api_key, base_url=self.llm_base_url)
        payload = {
            "features": features,
            "prediction": prediction,
            "thresholds": {
                "soil_moisture_low": self.soil_moisture_low,
                "soil_moisture_high": self.soil_moisture_high,
                "rainfall_high": self.rainfall_high,
                "nitrogen_low": self.nitrogen_low,
                "prediction_low": self.prediction_low,
            },
        }
        resp = client.chat.completions.create(
            model=self.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            stream=False,
            extra_body={"web_search": {"enable": False}},
            max_completion_tokens=1024,
        )
        if not resp.choices:
            return None
        content = resp.choices[0].message.content
        return content.strip() if content else None

    def suggest(self, features, prediction):
        llm_result = self._llm_suggest(features, prediction)
        if llm_result:
            return llm_result
        return self._rule_based(features, prediction)
