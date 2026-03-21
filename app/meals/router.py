from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.config import supabase

router = APIRouter()

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/register")
def register(body: RegisterRequest):
    """Créer un nouveau compte utilisateur"""
    try:
        response = supabase.auth.sign_up(
            email=body.email,
            password=body.password
        )

        if not response.user:
            raise HTTPException(status_code=400, detail="Erreur lors de la création du compte")

        user = response.user

        supabase.table("user_profile").insert({
            "user_id": user.id,
            "display_name": body.display_name or body.email.split("@")[0]
        }).execute()

        supabase.table("health_profile").insert({
            "user_id": user.id
        }).execute()

        return {
            "message": "Compte créé avec succès",
            "user_id": user.id,
            "email": user.email
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
def login(body: LoginRequest):
    """Se connecter et récupérer un token JWT"""
    try:
        response = supabase.auth.sign_in(
            email=body.email,
            password=body.password
        )

        if not response.user:
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user_id": response.user.id,
            "email": response.user.email
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")


@router.post("/logout")
def logout():
    """Se déconnecter"""
    try:
        supabase.auth.sign_out()
    except:
        pass
    return {"message": "Déconnecté avec succès"}