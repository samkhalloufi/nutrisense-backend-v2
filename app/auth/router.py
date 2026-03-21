from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
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
        response = supabase.auth.sign_up({
            "email": body.email,
            "password": body.password
        })
        user = response.user
        if not user:
            raise HTTPException(status_code=400, detail="Erreur lors de la création du compte")

        # Créer le profil vide associé
        supabase.table("user_profile").insert({
            "user_id": user.id,
            "display_name": body.display_name or body.email.split("@")[0]
        }).execute()

        # Créer le profil santé vide
        supabase.table("health_profile").insert({
            "user_id": user.id
        }).execute()

        return {
            "message": "Compte créé avec succès",
            "user_id": user.id,
            "email": user.email
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
def login(body: LoginRequest):
    """Se connecter et récupérer un token JWT"""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password
        })
        session = response.session
        if not session:
            raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")

        return {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "user_id": response.user.id,
            "email": response.user.email
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")


@router.post("/logout")
def logout():
    """Se déconnecter"""
    supabase.auth.sign_out()
    return {"message": "Déconnecté avec succès"}