from fastapi import FastAPI
from backend.api.quiz_routes import router

app = FastAPI(title="DocuMind AI API")

app.include_router(router)

@app.get("/")
def home():
    return {"message": "DocuMind AI Backend Running"}