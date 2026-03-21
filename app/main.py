from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.recipes.router import router as recipes_router
from app.meals.router import router as meals_router
from app.recommendations.router import router as reco_router
 
app = FastAPI(
    title="NutriSense AI",
    description="Backend API pour l'application de nutrition personnalisée",
    version="1.0.0"
)
 
# CORS — permet à l'app mobile de communiquer avec le backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En prod : remplacer par l'URL de l'app
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
# Routes
app.include_router(auth_router,    prefix="/auth",            tags=["Auth"])
app.include_router(users_router,   prefix="/users",           tags=["Utilisateurs"])
app.include_router(recipes_router, prefix="/recipes",         tags=["Recettes"])
app.include_router(meals_router,   prefix="/meals",           tags=["Repas"])
app.include_router(reco_router,    prefix="/recommendations", tags=["Recommandations"])
 
@app.get("/")
def health_check():
    return {"status": "ok", "app": "NutriSense AI", "version": "1.0.0"}