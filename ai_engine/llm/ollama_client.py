import requests
import logging
import time

logger = logging.getLogger(__name__)

# Ollama local API endpoint
OLLAMA_URL = "http://localhost:11434/api/generate"


def ask_llm(prompt, model="llama3.2:3b", retries=3, timeout=300):
    """
    Send a prompt to the local Ollama LLM.

    Args:
        prompt (str): Prompt sent to the model
        model (str): Ollama model name (default: llama3.2:3b)
        retries (int): Number of retry attempts
        timeout (int): Request timeout in seconds

    Returns:
        str | None: Model response text or None if failed
    """

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Calling Ollama (attempt {attempt}/{retries})...")

            response = requests.post(
                OLLAMA_URL,
                json=payload,
                timeout=timeout
            )

            response.raise_for_status()

            data = response.json()

            if "response" in data:
                return data["response"].strip()

            logger.error("Unexpected Ollama response format")
            return None

        except requests.exceptions.Timeout:
            logger.warning(f"Ollama timeout (attempt {attempt}/{retries})")

            if attempt == retries:
                logger.error("All retries exhausted")
                return None

            time.sleep(3)

        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Ollama. Run: ollama serve")
            return None

        except Exception as e:
            logger.error(f"LLM error: {e}")
            return None