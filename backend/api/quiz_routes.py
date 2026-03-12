# FIX — use Pydantic model for validation
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator
from backend.services.question_generation_service import generate_questions

router = APIRouter()

class QuizRequest(BaseModel):
    text: str
    difficulty: str = "Medium"

    @validator("text")
    def text_must_not_be_empty(cls, v):
        if not v or len(v.strip()) < 50:
            raise ValueError("Text too short to generate meaningful questions")
        return v

    @validator("difficulty")
    def difficulty_must_be_valid(cls, v):
        if v not in ("Easy", "Medium", "Hard"):
            raise ValueError("Difficulty must be Easy, Medium, or Hard")
        return v

@router.post("/generate-quiz")
async def generate_quiz(request: QuizRequest):
    try:
        questions = generate_questions(request.text, request.difficulty)
        if not questions:
            raise HTTPException(500, "Failed to generate questions")
        return {"questions": questions}
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {str(e)}")