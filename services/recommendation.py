class RecommendationEngine:
    def __init__(self):
        self.soil_moisture_low = 0.25
        self.soil_moisture_high = 0.45
        self.rainfall_high = 10.0
        self.nitrogen_low = 0.3

    def suggest(self, features, prediction):
        soil = float(features.get("soil_moisture", 0))
        rainfall = float(features.get("rainfall", 0))
        nitrogen = float(features.get("nitrogen", 0))

        if soil < self.soil_moisture_low and rainfall < self.rainfall_high:
            return "多浇水"
        if soil > self.soil_moisture_high or rainfall >= self.rainfall_high:
            return "少浇水"
        if nitrogen < self.nitrogen_low:
            return "多施肥"
        if prediction < 0.5:
            return "改良土壤并检查灌溉系统"
        return "保持当前管理措施"
