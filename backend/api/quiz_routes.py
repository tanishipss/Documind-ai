import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, validator
from backend.services.question_generation_service import generate_questions

logger = logging.getLogger(__name__)
router = APIRouter()


class QuizRequest(BaseModel):
    text: str
    difficulty: str = "Medium"

    @validator("text")
    def text_must_not_be_empty(cls, v):
        if not v or len(v.strip()) < 50:
            raise ValueError("Text too short to generate questions")
        return v

    @validator("difficulty")
    def difficulty_must_be_valid(cls, v):
        if v not in ("Easy", "Medium", "Hard"):
            raise ValueError("Difficulty must be Easy, Medium, or Hard")
        return v


@router.post("/generate-quiz")
async def generate_quiz(request: QuizRequest):
    try:
        logger.info(
            f"Generating quiz | difficulty={request.difficulty} "
            f"| text_length={len(request.text)}"
        )

        questions = generate_questions(request.text, request.difficulty)

        if not questions:
            raise HTTPException(
                status_code=500,
                detail="LLM returned no questions. Is Ollama running?"
            )

        logger.info(f"Returning {len(questions)} questions")
        return {"questions": questions}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quiz generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))