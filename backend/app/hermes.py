from datetime import datetime, timezone

import httpx

from .config import settings


class HermesClient:
    def __init__(self) -> None:
        self.base_url = (settings.hermes_api_base_url or "").rstrip("/")
        self.api_key = settings.hermes_api_key
        self.model = settings.hermes_agent_model

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key)

    async def compliance_review(self, payload: dict) -> dict:
        if not self.enabled:
            return {
                "summary": "Hermes ist nicht konfiguriert. Der strukturierte Payload wurde serverseitig vorbereitet.",
                "risk_level": payload.get("priority", "medium"),
                "findings": ["HERMES_API_BASE_URL oder HERMES_API_KEY fehlt."],
                "recommended_actions": ["Hermes-ENV setzen und Anfrage erneut starten."],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        body = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Bewerte den folgenden Compliance-Datensatz fuer eine technische Niederlassung. "
                                "Antworte knapp als Management-Hinweis mit Risiken und konkreten Massnahmen.\n\n"
                                f"{payload}"
                            ),
                        }
                    ],
                }
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=settings.hermes_timeout_seconds) as client:
            response = await client.post(f"{self.base_url}/responses", json=body, headers=headers)
            response.raise_for_status()
            return response.json()
