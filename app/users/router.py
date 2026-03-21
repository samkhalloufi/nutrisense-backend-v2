from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from app.config import supabase
from app.auth.dependencies import get_current_user

router = APIRouter()

# ── Schémas ──────────────────────────────────────────────────────────────────

class UserProfileUpdate(BaseModel):
    display_name:          Optional[str]  = None
    birth_year:            Optional[int]  = None
    biological_sex:        Optional[str]  = None
    height_cm:             Optional[float] = None
    weight_kg:             Optional[float] = None
    activity_level:        Optional[str]  = None
    allergens:             Optional[List[str]] = None
    dietary_prefs:         Optional[List[str]] = None
    disliked_ingredients:  Optional[List[str]] = None
    budget_level:          Optional[str]  = None
    max_prep_time_min:     Optional[int]  = None

class HealthProfileUpdate(BaseModel):
    diabetes_type:      Optional[str]   = None
    has_cgm:            Optional[bool]  = None
    has_wearable:       Optional[bool]  = None
    target_glucose_min: Optional[float] = None
    target_glucose_max: Optional[float] = None
    glucose_unit:       Optional[str]   = None

class GoalCreate(BaseModel):
    goal_type:        str
    target_weight_kg: Optional[float] = None
    target_calories:  Optional[int]   = None
    target_carbs_g:   Optional[int]   = None
    target_protein_g: Optional[int]   = None
    target_fat_g:     Optional[int]   = None
    target_fiber_g:   Optional[int]   = 25

# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/me")
def get_my_profile(user=Depends(get_current_user)):
    """Récupérer son profil complet"""
    profile = supabase.table("user_profile")\
        .select("*")\
        .eq("user_id", user.id)\
        .single()\
        .execute()

    health = supabase.table("health_profile")\
        .select("*")\
        .eq("user_id", user.id)\
        .single()\
        .execute()

    goals = supabase.table("user_goals")\
        .select("*")\
        .eq("user_id", user.id)\
        .eq("active", True)\
        .execute()

    return {
        "user_id":      user.id,
        "email":        user.email,
        "profile":      profile.data,
        "health":       health.data,
        "goals":        goals.data
    }


@router.put("/me/profile")
def update_profile(body: UserProfileUpdate, user=Depends(get_current_user)):
    """Mettre à jour son profil"""
    data = {k: v for k, v in body.dict().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")

    result = supabase.table("user_profile")\
        .update(data)\
        .eq("user_id", user.id)\
        .execute()

    return {"message": "Profil mis à jour", "data": result.data}


@router.put("/me/health")
def update_health_profile(body: HealthProfileUpdate, user=Depends(get_current_user)):
    """Mettre à jour son profil santé"""
    data = {k: v for k, v in body.dict().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="Aucune donnée à mettre à jour")

    # Garde-fou : avertissement diabète type 1
    if data.get("diabetes_type") == "type1":
        data["_warning"] = "type1_restrictions_active"

    result = supabase.table("health_profile")\
        .update(data)\
        .eq("user_id", user.id)\
        .execute()

    response = {"message": "Profil santé mis à jour", "data": result.data}
    if data.get("diabetes_type") == "type1":
        response["safety_notice"] = "Les recommandations seront adaptées. Consultez votre équipe soignante pour tout ajustement alimentaire."

    return response


@router.post("/me/goals")
def create_goal(body: GoalCreate, user=Depends(get_current_user)):
    """Définir un objectif nutritionnel"""
    # Désactiver les anciens objectifs du même type
    supabase.table("user_goals")\
        .update({"active": False})\
        .eq("user_id", user.id)\
        .eq("goal_type", body.goal_type)\
        .execute()

    result = supabase.table("user_goals").insert({
        "user_id": user.id,
        **body.dict()
    }).execute()

    return {"message": "Objectif créé", "data": result.data}


@router.get("/me/goals")
def get_goals(user=Depends(get_current_user)):
    """Récupérer ses objectifs actifs"""
    result = supabase.table("user_goals")\
        .select("*")\
        .eq("user_id", user.id)\
        .eq("active", True)\
        .execute()
    return result.data


@router.delete("/me")
def delete_account(user=Depends(get_current_user)):
    """Supprimer son compte et toutes ses données (RGPD)"""
    uid = user.id
    # Suppression en cascade grâce aux FK ON DELETE CASCADE
    supabase.auth.admin.delete_user(uid)
    return {"message": "Compte et données supprimés définitivement"}