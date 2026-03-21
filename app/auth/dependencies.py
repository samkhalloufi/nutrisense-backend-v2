from fastapi import HTTPException, Request
from app.config import supabase

async def get_current_user(request: Request):
    """
    Vérifie le token JWT dans le header Authorization.
    Utilisation : def ma_route(user = Depends(get_current_user))
    """
    authorization = request.headers.get("authorization") or request.headers.get("Authorization")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant ou invalide")

    token = authorization.replace("Bearer ", "")
    try:
        response = supabase.auth.get_user(token)
        if not response.user:
            raise HTTPException(status_code=401, detail="Token invalide")
        return response.user
    except Exception:
        raise HTTPException(status_code=401, detail="Token expiré ou invalide")