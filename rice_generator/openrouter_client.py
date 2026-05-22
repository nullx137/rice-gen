"""Клиент для работы с OpenRouter API / CometAPI и мультимодальной моделью Gemini."""

import base64
import re
from pathlib import Path
from typing import Optional

import httpx

from .config import settings


class APIClient:
    """Унифицированный клиент для OpenRouter и CometAPI."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        """
        Инициализация клиента.

        Args:
            api_key: API ключ. Если не указан, берётся из конфига.
            model: Модель для использования. Если не указана, берётся из конфига.
            provider: Провайдер API (openrouter или cometapi).
        """
        self.provider = (provider or settings.API_PROVIDER).lower()

        if self.provider == "cometapi":
            self.api_key = api_key or settings.COMETAPI_API_KEY
            self.base_url = settings.COMETAPI_BASE_URL
        else:
            self.api_key = api_key or settings.OPENROUTER_API_KEY
            self.base_url = settings.OPENROUTER_BASE_URL

        if not self.api_key:
            raise ValueError(
                f"API ключ не указан. Передайте api_key или установите "
                f"{'COMETAPI' if self.provider == 'cometapi' else 'OPENROUTER'}_API_KEY"
            )

        self.model = model or settings.MODEL

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self.provider == "openrouter":
            headers["HTTP-Referer"] = settings.HTTP_REFERER
            headers["X-Title"] = settings.APP_TITLE

        self.client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=settings.REQUEST_TIMEOUT,
        )

    def _encode_image(self, image_path: str | Path) -> str:
        """
        Кодирует изображение в base64.

        Args:
            image_path: Путь к изображению.

        Returns:
            Base64 строка изображения.
        """
        with open(image_path, "rb") as f:
            image_data = f.read()
        return base64.b64encode(image_data).decode("utf-8")

    def analyze_screenshot(
        self,
        screenshot_path: str | Path,
        hyprland_template: str,
        waybar_template: str,
        kitty_template: str,
    ) -> str:
        """
        Отправляет скриншот и шаблоны на анализ нейросети.

        Args:
            screenshot_path: Путь к скриншоту.
            hyprland_template: Шаблон конфига Hyprland.
            waybar_template: Шаблон конфига Waybar.
            kitty_template: Шаблон конфига Kitty.

        Returns:
            Ответ нейросети с модифицированными конфигами.
        """
        image_base64 = self._encode_image(screenshot_path)

        prompt = self._build_prompt(hyprland_template, waybar_template, kitty_template)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 16384,
        }

        response = self.client.post("/chat/completions", json=payload)
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def analyze_image_with_prompt(
        self,
        screenshot_path: str | Path,
        prompt: str,
        max_tokens: int = 4096,
    ) -> str:
        """
        Отправляет скриншот с кастомным промптом.

        Args:
            screenshot_path: Путь к скриншоту.
            prompt: Текст промпта.
            max_tokens: Лимит токенов.

        Returns:
            Ответ нейросети.
        """
        image_base64 = self._encode_image(screenshot_path)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": max_tokens,
        }

        response = self.client.post("/chat/completions", json=payload)
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def generate_wallpaper_image(
        self,
        screenshot_path: str | Path,
        prompt_text: str,
    ) -> bytes:
        """
        Генерирует обои (PNG) на основе скриншота через image generation API.

        Для CometAPI использует Gemini image generation endpoint (v1beta).
        Для OpenRouter — стандартный chat completions с image generation моделью
        (извлекает base64 из markdown-ответа).

        Args:
            screenshot_path: Путь к скриншоту.
            prompt_text: Текстовый промпт для генерации.

        Returns:
            Байты PNG-изображения.

        Raises:
            ValueError: Если не удалось извлечь изображение из ответа API.
            httpx.HTTPStatusError: При ошибке API.
        """
        image_base64 = self._encode_image(screenshot_path)

        if self.provider == "cometapi":
            # CometAPI проксирует Google Generative Language API (Gemini)
            url = f"https://api.cometapi.com/v1beta/models/{self.model}:generateContent"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": image_base64,
                                }
                            },
                            {"text": prompt_text},
                        ]
                    }
                ],
                "generationConfig": {
                    "responseModalities": ["TEXT", "IMAGE"],
                    "imageConfig": {
                        "aspectRatio": "16:9",
                        "imageSize": "4K",
                    },
                },
            }
            # Gemini v1beta endpoint требует x-goog-api-key и НЕ принимает
            # Authorization: Bearer (который уже установлен в self.client).
            # Поэтому используем отдельный временный клиент.
            with httpx.Client(timeout=settings.REQUEST_TIMEOUT) as temp_client:
                response = temp_client.post(
                    url,
                    json=payload,
                    headers={
                        "x-goog-api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                )
            response.raise_for_status()
            data = response.json()

            for candidate in data.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    inline_data = part.get("inlineData")
                    if inline_data and inline_data.get("data"):
                        return base64.b64decode(inline_data["data"])

            raise ValueError(
                "Не удалось извлечь изображение из ответа CometAPI. "
                f"Ответ: {data}"
            )

        else:
            # OpenRouter fallback: через chat completions + image gen модель
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                },
                            },
                            {"type": "text", "text": prompt_text},
                        ],
                    }
                ],
                "max_tokens": 4096,
            }
            response = self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Ищем base64 в markdown ![...](data:image/png;base64,...)
            b64_match = re.search(
                r"data:image/png;base64,([A-Za-z0-9+/=]+)", content
            )
            if b64_match:
                return base64.b64decode(b64_match.group(1))

            # Или ищем голый base64 блок
            b64_match = re.search(r"```\n([A-Za-z0-9+/=\s]+)\n```", content)
            if b64_match:
                cleaned = b64_match.group(1).replace("\n", "").replace(" ", "")
                return base64.b64decode(cleaned)

            raise ValueError(
                "Не удалось извлечь изображение из ответа OpenRouter. "
                f"Ответ: {content[:500]}"
            )

    def _build_prompt(self, hyprland: str, waybar: str, kitty: str) -> str:
        """
        Формирует промпт для нейросети.

        Args:
            hyprland: Шаблон Hyprland.
            waybar: Шаблон Waybar.
            kitty: Шаблон Kitty.

        Returns:
            Текст промпта.
        """
        return f"""Ты эксперт по настройке Linux rice (кастомизации окружения). 
Твоя задача — проанализировать скриншот и создать конфигурационные файлы, которые максимально 
точно воспроизводят визуальный стиль со скриншота.

## КРИТИЧЕСКИ ВАЖНО:
- Верни **ПОЛНЫЕ** конфиги без сокращений
- Не используй "..." или "// остальное без изменений"
- Каждый конфиг должен быть полным и готовым к использованию
- Если конфиг длинный — всё равно пиши его полностью

## Что нужно сделать:

1. **Проанализируй скриншот** и определи:
   - Цветовую схему (цвета фона, текста, акцентов)
   - Шрифты и их размеры
   - Расположение элементов (бар, отступы, gaps)
   - Прозрачность и blur эффекты
   - Иконки и символы

2. **Модифицируй предоставленные шаблоны** на основе анализа:
   - Обнови цвета в соответствии со скриншотом
   - Настрой отступы (gaps_in, gaps_out, padding)
   - Настрой шрифты и размеры
   - Сохрани функциональность, но адаптируй внешний вид

3. **Верни ответ в строгом формате JSON**:
```json
{{
  "hyprland_conf": "# полный конфиг hyprland.conf\\n# без сокращений\\nmonitor=,highrr,auto,1\\n...",
  "waybar_conf": "/* полный CSS для waybar */\\n* {{\\n  font-family: ...\\n}}...",
  "waybar_config": "{{\\n  \\"layer\\": \\"top\\",\\n  ...\\n}}",
  "kitty_conf": "# полный конфиг kitty.conf\\n# без сокращений\\nshell_integration no-rc\\n...",
  "color_scheme": {{
    "background": "#hex",
    "foreground": "#hex",
    "accent": "#hex",
    "colors": ["#hex", "#hex", "#hex", "#hex", "#hex", "#hex", "#hex", "#hex"]
  }},
  "fonts": {{
    "main": "название шрифта",
    "size": число
  }},
  "gaps": {{
    "inner": число,
    "outer": число
  }},
  "notes": "краткое описание изменений"
}}
```

## Шаблоны для модификации:

### Hyprland Template:
{hyprland}

### Waybar Template:
{waybar}

### Kitty Template:
{kitty}

**ВАЖНО:** 
1. Верни ТОЛЬКО JSON, без текста до или после
2. Все конфиги должны быть ПОЛНЫМИ, без сокращений
3. Экранируй кавычки и спецсимволы в JSON (используй \\" для кавычек, \\n для новых строк)
4. Убедись, что JSON валидный — проверь перед отправкой"""

    def close(self):
        """Закрывает HTTP клиент."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Alias for backwards compatibility
OpenRouterClient = APIClient
