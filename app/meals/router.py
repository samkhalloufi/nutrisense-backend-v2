from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.config import supabase
from app.auth.dependencies import get_current_user

router = APIRouter()

class MealCreate(BaseModel):
    meal_type: Optional[str] = None
    eaten_at: Optional[str] = None
    total_kcal: Optional[float] = None
    total_carbs_g: Optional[float] = None
    total_protein_g: Optional[float] = None
    total_fat_g: Optional[float] = None
    notes: Optional[str] = None
    source: str = "manual"

@router.get("/")
def get_meals(user=Depends(get_current_user)):
    result = supabase.table("meals")\
        .select("*")\
        .eq("user_id", user.id)\
        .order("eaten_at", desc=True)\
        .limit(20)\
        .execute()
    return result.data

@router.post("/")
def create_meal(body: MealCreate, user=Depends(get_current_user), request: Request = None):
    try:
        from app.config import SUPABASE_URL, SUPABASE_ANON_KEY
        from supabase import create_client

        # Récupérer le token depuis le header
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        token = auth_header.replace("Bearer ", "")

        # Créer un client Supabase authentifié avec le token utilisateur
        authed_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        authed_client.postgrest.auth(token)

        result = authed_client.table("meals").insert({
            "user_id": user.id,
            **{k: v for k, v in body.dict().items() if v is not None}
        }).execute()
        return {"message": "Repas enregistré", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/week")
def get_week_stats(user=Depends(get_current_user)):
    from datetime import timedelta
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
    result = supabase.table("meals")\
        .select("eaten_at, total_kcal")\
        .eq("user_id", user.id)\
        .gte("eaten_at", seven_days_ago)\
        .execute()
    return {"meals": result.data, "count": len(result.data)}
