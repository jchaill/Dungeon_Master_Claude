import httpx
from typing import AsyncGenerator, List, Optional
from ..config import settings
from ..utils.logger import logger


class OllamaClient:
    def __init__(self):
        self.host = settings.OLLAMA_HOST.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self.client = httpx.AsyncClient(timeout=120.0)

    async def test_connection(self) -> bool:
        try:
            resp = await self.client.get(f"{self.host}/api/tags")
            resp.raise_for_status()
            logger.info(f"Ollama connection successful: {self.host}")
            return True
        except Exception as e:
            logger.warning(f"Ollama connection failed: {e}")
            return False

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[dict]] = None,
        stream: bool = False,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }

        try:
            resp = await self.client.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama generate error: {e}")
            raise

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[dict]] = None,
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        import json as _json
        async with self.client.stream(
            "POST",
            f"{self.host}/api/chat",
            json=payload,
            timeout=120.0,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line:
                    try:
                        data = _json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]
                        if data.get("done"):
                            break
                    except _json.JSONDecodeError:
                        continue

    async def close(self):
        await self.client.aclose()


ollama_client = OllamaClient()


DM_SYSTEM_PROMPT = """You are an experienced Dungeon Master running a D&D 5e campaign.
You create immersive, engaging narratives while following the rules of D&D 5th Edition.

Guidelines:
- Describe scenes vividly but concisely (2-4 paragraphs max)
- React to player actions with appropriate consequences
- Keep the story moving and engaging
- Maintain consistency with established lore and world details
- Balance challenge with fun
- Use the player character names in your narration
- Track combat state and describe it clearly

Dice rolls:
- When a player action requires a dice roll, ask for it explicitly and tell the player what die to roll.
- Describe what different result ranges mean BEFORE the roll marker (e.g. "A result of 15 or higher succeeds, 10–14 is a partial success, 9 or below fails.").
- At the very end of the message, append a roll marker in this exact format: [ROLL: XdY] — for example [ROLL: 1d20] or [ROLL: 2d6].
- Only include one roll marker per message.
- If no dice roll is needed, do not include a roll marker.

Current campaign context will be provided in each message."""
