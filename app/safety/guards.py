from app.config import supabase

def check_safety_flags(user_id: str) -> dict:
    """
    Vérifie les garde-fous de sécurité avant d'envoyer des recommandations.
    Retourne {"blocked": False} si tout va bien,
    ou {"blocked": True, "message": "..."} si une situation critique est détectée.
    """

    # Récupérer le profil santé
    health = supabase.table("health_profile")\
        .select("diabetes_type, target_glucose_min")\
        .eq("user_id", user_id)\
        .single()\
        .execute()

    if not health.data:
        return {"blocked": False}

    h = health.data

    # Récupérer les objectifs actifs
    goals = supabase.table("user_goals")\
        .select("target_calories")\
        .eq("user_id", user_id)\
        .eq("active", True)\
        .execute()

    # Vérification : objectif calorique trop bas
    for goal in (goals.data or []):
        target = goal.get("target_calories")
        if target and target < 1200:
            # Logger le flag
            supabase.table("safety_flags").insert({
                "user_id":  user_id,
                "flag_type": "extreme_caloric_restriction",
                "severity":  "warning",
                "context":   {"target_calories": target}
            }).execute()
            return {
                "blocked": True,
                "message": (
                    "Votre objectif calorique semble très bas (< 1200 kcal). "
                    "Pour votre sécurité, nous vous recommandons de consulter "
                    "un diététicien avant de continuer."
                )
            }

    return {"blocked": False}


# ── Messages de sécurité selon le profil ─────────────────────────────────────

SAFETY_NOTICES = {
    "type1": (
        "NutriSense vous propose des repères nutritionnels généraux. "
        "Pour tout ajustement de traitement, consultez votre endocrinologue ou diabétologue."
    ),
    "gestational": (
        "Votre grossesse nécessite un suivi médical spécifique. "
        "Ces recommandations sont indicatives — suivez les conseils de votre équipe médicale."
    ),
    "type2": (
        "Ces recommandations visent à soutenir votre équilibre glycémique. "
        "Elles ne remplacent pas l'avis de votre médecin ou diététicien."
    ),
}

def get_safety_notice(diabetes_type: str) -> str | None:
    return SAFETY_NOTICES.get(diabetes_type)