from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from app.config import supabase
from app.auth.dependencies import get_current_user

router = APIRouter()

@router.get("/")
def get_recipes(
    tag:      Optional[str] = Query(None, description="Filtrer par tag ex: low_carb"),
    max_kcal: Optional[int] = Query(None, description="Calories max par portion"),
    max_prep: Optional[int] = Query(None, description="Temps de préparation max (min)"),
    limit:    int = Query(20, le=50),
    offset:   int = Query(0),
    user=Depends(get_current_user)
):
    """Récupérer la liste des recettes avec filtres optionnels"""

    # Récupérer les IDs filtrés par tag si demandé
    recipe_ids = None
    if tag:
        tag_result = supabase.table("recipe_tags")\
            .select("recipe_id")\
            .eq("tag", tag)\
            .execute()
        recipe_ids = [r["recipe_id"] for r in tag_result.data]
        if not recipe_ids:
            return []

    # Requête principale
    query = supabase.table("recipes")\
        .select("*, recipe_nutrition_facts(*), recipe_tags(tag)")\
        .eq("is_published", True)

    if recipe_ids:
        query = query.in_("id", recipe_ids)

    if max_prep:
        query = query.lte("prep_time_min", max_prep)

    result = query.range(offset, offset + limit - 1).execute()

    # Filtrage kcal côté Python (Supabase ne supporte pas le filtre sur table jointe)
    recipes = result.data
    if max_kcal:
        recipes = [
            r for r in recipes
            if r.get("recipe_nutrition_facts")
            and r["recipe_nutrition_facts"].get("kcal", 9999) <= max_kcal
        ]

    return recipes


@router.get("/{recipe_id}")
def get_recipe(recipe_id: str, user=Depends(get_current_user)):
    """Récupérer le détail d'une recette"""
    result = supabase.table("recipes")\
        .select("*, recipe_nutrition_facts(*), recipe_tags(tag)")\
        .eq("id", recipe_id)\
        .single()\
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Recette introuvable")

    return result.data


@router.post("/{recipe_id}/feedback")
def give_feedback(
    recipe_id: str,
    signal: str = Query(..., description="liked | disliked | cooked | saved | skipped"),
    rating: Optional[int] = Query(None, ge=1, le=5),
    user=Depends(get_current_user)
):
    """Enregistrer un feedback sur une recette"""
    valid_signals = ["liked", "disliked", "cooked", "saved", "skipped"]
    if signal not in valid_signals:
        raise HTTPException(status_code=400, detail=f"Signal invalide. Valeurs: {valid_signals}")

    result = supabase.table("feedback_events").insert({
        "user_id":   user.id,
        "recipe_id": recipe_id,
        "signal":    signal,
        "rating":    rating
    }).execute()

    return {"message": "Feedback enregistré", "data": result.data}