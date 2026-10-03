import requests
import json
import time
import config

class GeminiClient:
    def __init__(self, api_key=None):
        self.api_key = api_key or config.GEMINI_API_KEY
        # Fallback list of models
        self.models = ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-flash-latest"]
        
    def generate(self, prompt, system_instruction=None, max_retries=2):
        """Gemini 모델을 호출하여 분석 보고서를 생성합니다."""
        if not self.api_key or self.api_key == "YOUR_GEMINI_API_KEY_HERE":
            return "[Gemini AI] API 키가 설정되지 않았습니다. .env 또는 설정에서 키를 등록해주세요."

        headers = {"Content-Type": "application/json"}
        
        contents = []
        if system_instruction:
            contents.append({
                "role": "user",
                "parts": [{"text": f"[시스템 역할 및 행동 지침]\n{system_instruction}\n\n[사용자 요청 시작]"}]
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "지침을 숙지했습니다. 금융 전문 AI 에이전트로서 엄밀하고 통찰력 있는 분석을 제공하겠습니다."}]
            })
            
        contents.append({
            "role": "user",
            "parts": [{"text": prompt}]
        })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 2048
            }
        }

        for model_name in self.models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            for attempt in range(max_retries):
                try:
                    resp = requests.post(url, headers=headers, json=payload, timeout=25)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates and "content" in candidates[0]:
                            parts = candidates[0]["content"].get("parts", [])
                            if parts and "text" in parts[0]:
                                return parts[0]["text"]
                    elif resp.status_code in [500, 503]:
                        time.sleep(1)
                        continue
                    else:
                        break
                except Exception as e:
                    time.sleep(1)
                    continue

        return "[Gemini AI] 서버 통신 중 일시적인 지연이 발생했습니다. 잠시 후 다시 시도해주세요."
