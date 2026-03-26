from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import httpx
import base64
import os
import json
import re
import traceback
from app.auth.dependencies import get_current_user
from supabase import create_client
from app.config import SUPABASE_URL, SUPABASE_ANON_KEY

router = APIRouter()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

class PhotoAnalyzeRequest(BaseModel):
    image_base64: str
    meal_id: str

@router.post("/analyze")
def analyze_photo(body: PhotoAnalyzeRequest, request: Request, user=Depends(get_current_user)):
    try:
        image_data = base64.b64decode(body.image_base64)
        image_b64 = base64.b64encode(image_data).decode()

        prompt = """
        Analyse cette photo de repas et retourne UNIQUEMENT un JSON valide avec ce format exact:
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
          "overall_confidence": 0.80,
          "warnings": []
        }
        Réponds UNIQUEMENT avec le JSON, sans texte supplémentaire.
        """

        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_b64
                        }
                    }
                ]
            }]
        }

        with httpx.Client(timeout=30) as client:
            gemini_response = client.post(GEMINI_URL, json=payload)
            gemini_data = gemini_response.json()

        print(f"STATUS: {gemini_response.status_code}")
        print(f"RESPONSE: {gemini_data}")
        print(f"GEMINI FULL RESPONSE: {gemini_data}")
        if "error" in gemini_data:
            raise ValueError(f"Erreur Gemini: {gemini_data['error']}")
        if "candidates" not in gemini_data:
            raise ValueError(f"Pas de candidates: {gemini_data}")
        text = gemini_data["candidates"][0]["content"]["parts"][0]["text"]
        print(f"GEMINI RAW TEXT: {repr(text[:500])}")
        print(f"GEMINI RESPONSE: {text[:500]}")

        # Nettoyer les backticks markdown
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()

        # Extraire le JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if not json_match:
            raise ValueError(f"Pas de JSON: {text[:200]}")
        result = json.loads(json_match.group())

        # Sauvegarder l'analyse dans Supabase
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        token = auth_header.replace("Bearer ", "")
        supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        supabase_client.postgrest.auth(token)

        supabase_client.table("meal_analysis_results").insert({
            "meal_id": body.meal_id,
            "ai_model": "gemini-1.5-flash",
            "detected_items": result.get("detected_items", []),
            "confidence_score": result.get("overall_confidence", 0),
            "final_nutrition": result
        }).execute()

        return result

    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"ERREUR ANALYSE: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))
