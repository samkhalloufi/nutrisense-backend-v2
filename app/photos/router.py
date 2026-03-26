from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import base64
import os
import json
import re
import httpx
from app.auth.dependencies import get_current_user
from supabase import create_client
from app.config import SUPABASE_URL, SUPABASE_ANON_KEY

router = APIRouter()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

class PhotoAnalyzeRequest(BaseModel):
    image_base64: str
    meal_id: str

@router.post("/analyze")
def analyze_photo(body: PhotoAnalyzeRequest, request: Request, user=Depends(get_current_user)):
    try:
        prompt = """Analyse cette photo de repas et retourne UNIQUEMENT un JSON valide avec ce format exact:
{
  "detected_items": [
    {
      "name": "nom de l'aliment",
      "quantity_g": 150,
      "confidence": 0.85,
      "kcal": 200,
      "carbs_g": 20,
      "protein_g": 15,
      "fat_g": 8,
      "fiber_g": 2
    }
  ],
  "total_kcal": 500,
  "total_carbs_g": 45,
  "total_protein_g": 30,
  "total_fat_g": 15,
  "overall_success": 0.80,
  "warnings": []
}
Réponds UNIQUEMENT avec le JSON, sans texte supplémentaire."""

        payload = {
            "model": "llama-3.2-11b-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{body.image_base64}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.1
        }

        with httpx.Client(timeout=30) as client:
            response = client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            groq_data = response.json()

        print(f"GROQ STATUS: {response.status_code}")
        print(f"GROQ RESPONSE: {groq_data}")

        text = groq_data["choices"][0]["message"]["content"]

        # Nettoyer le JSON
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if not json_match:
            raise ValueError(f"Pas de JSON trouvé: {text[:200]}")
        result = json.loads(json_match.group())

        # Sauvegarder dans Supabase
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        token = auth_header.replace("Bearer ", "")
        client_db = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        client_db.postgrest.auth(token)

        client_db.table("meal_analysis_results").insert({
            "meal_id": body.meal_id,
            "ai_model": "llama-3.2-11b-vision-preview",
            "detected_items": result.get("detected_items", []),
            "confidence_score": result.get("overall_success", 0),
            "final_nutrition": result
        }).execute()

        return result

    except Exception as e:
        import traceback
        print(f"ERREUR: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models")
def list_models():
    import os
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    with httpx.Client(timeout=30) as client:
        response = client.get(
            f"https://generativelanguage.googleapis.com/v1/models?key={GEMINI_API_KEY}"
        )
        return response.json()
