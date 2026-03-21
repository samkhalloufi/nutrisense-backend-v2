from fastapi import APIRouter, HTTPException, Depends, Query
from app.config import supabase
from app.auth.dependencies import get_current_user
from app.safety.guards import check_safety_flags
from typing import Optional
import json

router = APIRouter()

# ── Moteur de recommandation ─────────────────────────────────────────────────

def load_user_context(user_id: str) -> dict:
    """Charge toutes les données utiles de l'utilisateur"""
    profile = supabase.table("user_profile")\
        .select("*").eq("user_id", user_id).single().execute()
    health = supabase.table("health_profile")\
        .select("*").eq("user_id", user_id).single().execute()
    goals = supabase.table("user_goals")\
        .select("*").eq("user_id", user_id).eq("active", True).execute()
    feedback = supabase.table("feedback_events")\
        .select("recipe_id, signal")\
        .eq("user_id", user_id)\
        .execute()

    return {
        "profile": profile.data or {},
        "health":  health.data or {},
        "goals":   goals.data or [],
        "feedback": feedback.data or []
    }


def score_recipe(recipe: dict, ctx: dict) -> tuple[float, list[str]]:
    """
    Calcule un score 0.0–1.0 pour une recette selon le contexte utilisateur.
    Retourne (score, [raisons lisibles])
    """
    score = 0.5   # Score de base
    reasons = []
    nutrition = recipe.get("recipe_nutrition_facts") or {}
    tags = [t["tag"] for t in (recipe.get("recipe_tags") or [])]
    health = ctx["health"]
    goals = ctx["goals"]
    profile = ctx["profile"]

    # ── Niveau 1 : filtres et bonus profil ───────────────────────────────────
    # Allergens
    allergens = profile.get("allergens") or []
    ingredients_text = json.dumps(recipe.get("ingredients", [])).lower()
    for allergen in allergens:
        if allergen.lower() in ingredients_text:
            return -1.0, ["Contient un allergène"]  # Blocage dur

    # Temps de préparation
    max_prep = profile.get("max_prep_time_min") or 45
    total_time = (recipe.get("prep_time_min") or 0) + (recipe.get("cook_time_min") or 0)
    if total_time <= max_prep:
        score += 0.1
        reasons.append(f"Prêt en {total_time} min")

    # ── Niveau 2 : objectifs ─────────────────────────────────────────────────
    if goals:
        goal_type = goals[0].get("goal_type")
        kcal = nutrition.get("kcal") or 0
        carbs = nutrition.get("carbs_g") or 0
        protein = nutrition.get("protein_g") or 0
        gl = nutrition.get("glycemic_load") or 0

        if goal_type == "weight_loss":
            if kcal < 400:
                score += 0.2
                reasons.append("Faible en calories")
            if protein > 20:
                score += 0.1
                reasons.append("Riche en protéines")

        elif goal_type == "muscle_gain":
            if protein > 25:
                score += 0.3
                reasons.append("Excellente source de protéines")

        elif goal_type in ("glycemic_balance", "diabetes_management"):
            if gl < 10:
                score += 0.3
                reasons.append("Charge glycémique faible")
            if "low_carb" in tags:
                score += 0.1
            if "diabetic_friendly" in tags:
                score += 0.1
                reasons.append("Adapté à l'équilibre glycémique")

        elif goal_type == "healthier_eating":
            fiber = nutrition.get("fiber_g") or 0
            if fiber > 5:
                score += 0.2
                reasons.append("Riche en fibres")

    # ── Garde-fous diabète type 1 ────────────────────────────────────────────
    diabetes_type = health.get("diabetes_type")
    if diabetes_type == "type1":
        gl = nutrition.get("glycemic_load") or 0
        if gl > 20:
            score *= 0.3
            reasons.append("⚠️ Charge glycémique élevée — consultez votre équipe soignante")
        else:
            reasons.append("Compatible avec une alimentation à faible index glycémique")

    # ── Niveau 3 : feedback utilisateur ─────────────────────────────────────
    feedback = ctx["feedback"]
    liked_ids    = {f["recipe_id"] for f in feedback if f["signal"] == "liked"}
    disliked_ids = {f["recipe_id"] for f in feedback if f["signal"] == "disliked"}

    if recipe["id"] in disliked_ids:
        return -1.0, ["Recette non appréciée"]  # Blocage
    if recipe["id"] in liked_ids:
        score += 0.2
        reasons.append("Dans vos favoris")

    # Raison par défaut si aucune raison générée
    if not reasons:
        reasons.append("Correspond à votre profil")

    return min(score, 1.0), reasons


def recommend(user_id: str, n: int = 5) -> list:
    """Moteur principal : charge les recettes et retourne les n meilleures"""
    ctx = load_user_context(user_id)

    # Charger toutes les recettes publiées avec nutrition et tags
    recipes = supabase.table("recipes")\
        .select("*, recipe_nutrition_facts(*), recipe_tags(tag)")\
        .eq("is_published", True)\
        .execute().data

    scored = []
    for recipe in recipes:
        score, reasons = score_recipe(recipe, ctx)
        if score < 0:
            continue  # Recette bloquée (allergène, disliked)
        scored.append({
            "recipe":  recipe,
            "score":   round(score, 3),
            "reasons": reasons
        })

    # Trier par score décroissant, prendre les n premiers
    scored.sort(key=lambda x: -x["score"])
    top = scored[:n]

    # Déterminer le niveau du moteur utilisé
    has_goals    = len(ctx["goals"]) > 0
    has_feedback = len(ctx["feedback"]) > 0
    engine_level = 1
    if has_goals:    engine_level = 2
    if has_feedback: engine_level = 3

    # Logger l'événement de recommandation
    supabase.table("recommendation_events").insert({
        "user_id":      user_id,
        "engine_level": engine_level,
        "recipes":      [{"recipe_id": r["recipe"]["id"], "score": r["score"]} for r in top],
        "context":      {"goals": len(ctx["goals"]), "feedback": len(ctx["feedback"])},
        "trigger":      "manual"
    }).execute()

    return top


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("/")
def get_recommendations(
    n: int = Query(5, ge=1, le=10),
    user=Depends(get_current_user)
):
    """Obtenir les recommandations personnalisées du jour"""

    # Vérification sécurité avant toute recommandation
    safety = check_safety_flags(user.id)
    if safety.get("blocked"):
        return {
            "blocked": True,
            "message": safety["message"],
            "recommendations": []
        }

    results = recommend(user.id, n)

    return {
        "count": len(results),
        "recommendations": [
            {
                "recipe":  r["recipe"],
                "score":   r["score"],
                "reasons": r["reasons"]
            }
            for r in results
        ]
    }


@router.post("/refresh")
def refresh_recommendations(user=Depends(get_current_user)):
    """Forcer la mise à jour des recommandations"""
    results = recommend(user.id, 5)
    return {
        "message": "Recommandations mises à jour",
        "count": len(results),
        "recommendations": results
    }