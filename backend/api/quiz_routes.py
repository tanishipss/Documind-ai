from fastapi import APIRouter
from backend.services.question_generation_service import generate_questions

router = APIRouter()


@router.post("/generate-quiz")
async def generate_quiz(data: dict):

    text = data.get("text")
    difficulty = data.get("difficulty", "Medium")

    questions = generate_questions(text, difficulty)

    return {
        "questions": questions
    }