"""Конфигурация проекта."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv()


class Settings:
    """Настройки приложения."""

    # === API Provider ===
    API_PROVIDER: str = os.getenv("API_PROVIDER", "openrouter").lower()

    # === OpenRouter API ===
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # === CometAPI ===
    COMETAPI_API_KEY: str = os.getenv("COMETAPI_API_KEY", "")
    COMETAPI_BASE_URL: str = os.getenv(
        "COMETAPI_BASE_URL", "https://api.cometapi.com/v1"
    )

    # === Модели ===
    MODEL: str = os.getenv("RICE_MODEL", "google/gemini-3-flash-preview")
    WALLPAPER_MODEL: str = os.getenv("WALLPAPER_MODEL", "openai/dall-e-3")

    # === Инструменты ===
    WALLPAPER_TOOL: str = os.getenv("WALLPAPER_TOOL", "swaybg").lower()

    # === Таймауты ===
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "120"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))

    # === Wallpaper Generation ===
    WALLPAPER_ENABLED: bool = os.getenv("WALLPAPER_ENABLED", "true").lower() == "true"
    WALLPAPER_MODEL: str = os.getenv(
        "WALLPAPER_MODEL", "google/gemini-3-pro-image-preview"
    )

    # === Лимиты токенов ===
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "16384"))

    # Лимиты для генерации
    HYPRLAND_MAX_TOKENS: int = int(os.getenv("HYPRLAND_MAX_TOKENS", "8000"))
    WAYBAR_MAX_TOKENS: int = int(os.getenv("WAYBAR_MAX_TOKENS", "6000"))
    KITTY_MAX_TOKENS: int = int(os.getenv("KITTY_MAX_TOKENS", "3000"))

    # Лимиты для ИИ-валидации
    VALIDATE_ANALYSIS_TOKENS: int = int(os.getenv("VALIDATE_ANALYSIS_TOKENS", "4000"))
    VALIDATE_FIX_TOKENS: int = int(os.getenv("VALIDATE_FIX_TOKENS", "8000"))

    # Задержка между запросами (секунды)
    REQUEST_DELAY: int = int(os.getenv("REQUEST_DELAY", "10"))

    # === Пути ===
    BASE_DIR: Path = Path(__file__).parent.parent
    TEMPLATES_DIR: Path = BASE_DIR / "rice_generator" / "templates"
    DEFAULT_OUTPUT_DIR: Path = BASE_DIR / "generated_configs"

    # === Прочее ===
    # HTTP Referer для OpenRouter (требование API)
    HTTP_REFERER: str = os.getenv("HTTP_REFERER", "https://github.com/rice-generator")
    APP_TITLE: str = os.getenv("APP_TITLE", "Rice Generator")

    # Включить подробное логирование
    VERBOSE: bool = os.getenv("VERBOSE", "false").lower() == "true"

    @classmethod
    def validate(cls) -> None:
        """
        Проверяет наличие обязательных настроек.

        Raises:
            ValueError: Если API ключ не указан.
        """
        if cls.API_PROVIDER == "cometapi":
            if not cls.COMETAPI_API_KEY:
                raise ValueError(
                    "COMETAPI_API_KEY не указан. "
                    "Установите переменную окружения или создайте файл .env"
                )
        else:
            if not cls.OPENROUTER_API_KEY:
                raise ValueError(
                    "OPENROUTER_API_KEY не указан. "
                    "Установите переменную окружения или создайте файл .env"
                )


# Глобальный экземпляр настроек
settings = Settings()
