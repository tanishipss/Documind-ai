import requests
import logging
import time

logger = logging.getLogger(__name__)
OLLAMA_URL = "http://localhost:11434/api/generate"


def ask_llm(prompt, model="llama3.2:3b", retries=2, timeout=600):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 5000,  # increased from 3000 to fit 25 questions
            "num_ctx": 4096       # increased from 2048 for larger context
        }
    }

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Ollama attempt {attempt}/{retries} | model={model}")
            response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json()["response"]

        except requests.exceptions.Timeout:
            logger.warning(f"Ollama timeout (attempt {attempt}/{retries})")
            if attempt == retries:
                return None
            time.sleep(3)

        except requests.exceptions.ConnectionError:
            logger.error("Ollama not running — run: ollama serve")
            return None

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return None