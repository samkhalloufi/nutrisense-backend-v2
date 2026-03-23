from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from supabase import create_client
from app.config import SUPABASE_URL, SUPABASE_ANON_KEY
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

def get_authed_client(request: Request):
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    token = auth_header.replace("Bearer ", "")
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    client.postgrest.auth(token)
    return client

@router.get("/")
def get_meals(request: Request, user=Depends(get_current_user)):
    client = get_authed_client(request)
    result = client.table("meals")\
        .select("*")\
        .eq("user_id", user.id)\
        .order("eaten_at", desc=True)\
        .limit(20)\
        .execute()
    return result.data

@router.post("/")
def create_meal(body: MealCreate, request: Request, user=Depends(get_current_user)):
    try:
        client = get_authed_client(request)
        data = {
            "user_id": user.id,
            "source": body.source or "photo",
            "eaten_at": body.eaten_at or datetime.now().isoformat(),
        }
        if body.meal_type: data["meal_type"] = body.meal_type
        if body.total_kcal: data["total_kcal"] = body.total_kcal
        if body.total_carbs_g: data["total_carbs_g"] = body.total_carbs_g
        if body.total_protein_g: data["total_protein_g"] = body.total_protein_g
        if body.total_fat_g: data["total_fat_g"] = body.total_fat_g
        if body.notes: data["notes"] = body.notes

        result = client.table("meals").insert(data).execute()
        return {"message": "Repas enregistré", "data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/week")
def get_week_stats(request: Request, user=Depends(get_current_user)):
    from datetime import timedelta
    client = get_authed_client(request)
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
    result = client.table("meals")\
        .select("eaten_at, total_kcal")\
        .eq("user_id", user.id)\
        .gte("eaten_at", seven_days_ago)\
        .execute()
    return {"meals": result.data, "count": len(result.data)}
