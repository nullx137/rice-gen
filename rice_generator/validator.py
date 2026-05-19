"""ИИ-валидатор конфигов на основе скриншота."""

import json
import re
from pathlib import Path
from typing import Optional

from .openrouter_client import OpenRouterClient
from .config import settings


class AIValidator:
    """Валидатор конфигов через ИИ — сравнивает со скриншотом и исправляет."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        """
        Инициализация валидатора.

        Args:
            api_key: API ключ.
            model: Модель для анализа.
            provider: API провайдер (openrouter или cometapi).
        """
        self.provider = provider or settings.API_PROVIDER
        if self.provider == "cometapi":
            self.api_key = api_key or settings.COMETAPI_API_KEY
        else:
            self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.model = model or settings.MODEL

    def validate_and_fix(
        self,
        screenshot_path: str | Path,
        output_dir: str | Path,
        max_iterations: int = 2,
    ) -> dict[str, bool]:
        """
        Проверяет конфиги со скриншотом и исправляет расхождения.

        Args:
            screenshot_path: Путь к скриншоту.
            output_dir: Директория с конфигами.
            max_iterations: Максимум итераций исправки.

        Returns:
            Словарь с результатами проверки по каждому файлу.
        """
        output_dir = Path(output_dir)
        results = {}

        print("🤖 ИИ-проверка конфигов...")

        # Загружаем конфиги
        configs = self._load_configs(output_dir)
        if not configs:
            print("⚠️  Нет конфигов для проверки")
            return results

        for iteration in range(max_iterations):
            print(f"\n📋 Итерация {iteration + 1}/{max_iterations}")

            # Отправляем скриншот + конфиги на анализ
            analysis = self._analyze_configs(
                screenshot_path=screenshot_path,
                configs=configs,
            )

            # Проверяем есть ли замечания
            if not analysis.get("issues"):
                print("✅ Все конфиги соответствуют скриншоту!")
                break

            print(f"⚠️  Найдено {len(analysis['issues'])} замечаний")
            for issue in analysis["issues"]:
                print(f"   • {issue['file']}: {issue['description']}")

            # Исправляем конфиги
            fixes = self._fix_configs(
                screenshot_path=screenshot_path,
                configs=configs,
                issues=analysis["issues"],
            )

            # Применяем исправления
            for file_key, new_content in fixes.items():
                filepath = self._get_filepath(output_dir, file_key)
                if filepath:
                    # Конвертируем dict в строку если нужно
                    if isinstance(new_content, dict):
                        new_content = json.dumps(
                            new_content, indent=2, ensure_ascii=False
                        )

                    filepath.write_text(new_content, encoding="utf-8")
                    print(f"✅ Исправлен: {file_key}")
                    configs[file_key] = new_content
                    results[file_key] = True

        return results

    def _load_configs(self, output_dir: Path) -> dict[str, str]:
        """Загружает все конфиги из директории."""
        configs = {}

        hyprland = output_dir / "hyprland.conf"
        if hyprland.exists():
            configs["hyprland"] = hyprland.read_text(encoding="utf-8")

        waybar_config = output_dir / "waybar_config.json"
        if waybar_config.exists():
            configs["waybar_config"] = waybar_config.read_text(encoding="utf-8")

        waybar_style = output_dir / "waybar_style.css"
        if waybar_style.exists():
            configs["waybar_style"] = waybar_style.read_text(encoding="utf-8")

        wofi_config = output_dir / "wofi_config"
        if wofi_config.exists():
            configs["wofi_config"] = wofi_config.read_text(encoding="utf-8")

        wofi_style = output_dir / "wofi_style.css"
        if wofi_style.exists():
            configs["wofi_style"] = wofi_style.read_text(encoding="utf-8")

        kitty = output_dir / "kitty.conf"
        if kitty.exists():
            configs["kitty"] = kitty.read_text(encoding="utf-8")

        return configs

    def _analyze_configs(
        self,
        screenshot_path: str | Path,
        configs: dict[str, str],
    ) -> dict:
        """
        Анализирует конфиги на соответствие скриншоту.

        Returns:
            Словарь с замечаниями.
        """
        prompt = self._build_analysis_prompt(configs)

        with OpenRouterClient(self.api_key, self.model, self.provider) as client:
            response = client.analyze_image_with_prompt(
                screenshot_path=screenshot_path,
                prompt=prompt,
                max_tokens=settings.VALIDATE_ANALYSIS_TOKENS,
            )

        # Извлекаем JSON с замечаниями
        return self._extract_analysis_json(response)

    def _fix_configs(
        self,
        screenshot_path: str | Path,
        configs: dict[str, str],
        issues: list[dict],
    ) -> dict[str, str]:
        """
        Исправляет конфиги на основе замечаний.

        Returns:
            Словарь с исправленными конфигами.
        """
        prompt = self._build_fix_prompt(configs, issues)

        with OpenRouterClient(self.api_key, self.model, self.provider) as client:
            response = client.analyze_image_with_prompt(
                screenshot_path=screenshot_path,
                prompt=prompt,
                max_tokens=settings.VALIDATE_FIX_TOKENS,
            )

        # Извлекаем исправленные конфиги
        return self._extract_fixed_configs(response)

    def _build_analysis_prompt(self, configs: dict[str, str]) -> str:
        """Создаёт промпт для анализа конфигов."""
        configs_text = "\n\n".join(
            f"### {key} ###\n{content}" for key, content in configs.items()
        )

        return f"""Ты эксперт по Linux rice. Проверь конфиги на соответствие скриншоту.

## ГЛАВНАЯ ЗАДАЧА:
Внимательно рассмотри скриншот и проверь конфиги Waybar и Wofi на наличие и правильное расположение модулей.

## 🔍 ПРОВЕРКА WAYBAR — МОДУЛИ (ПРИОРИТЕТ #1):

### 1. Наличие модулей:
- Посмотри на скриншот слева направо
- Определи КАЖДЫЙ видимый элемент на баре
- Сравни с modules-left, modules-center, modules-right
- Отметь отсутствующие модули
- Отметь лишние модули (есть в конфиге, но нет на скриншоте)

### 2. Расположение модулей:
- Какие модули СЛЕВА? (обычно: workspaces, tray)
- Какие модули ПО ЦЕНТРУ? (обычно: window, media)
- Какие модули СПРАВА? (обычно: audio, network, battery, clock)

## 🔍 ПРОВЕРКА WOFI (если есть):
- Соответствуют ли цвета фона и текста скриншоту?
- Правильный ли размер окна (width, height)?
- Есть ли иконки (allow_images)?

## 📝 ПРОВЕРКА ДРУГИХ КОНФИГОВ:

### Hyprland (если есть):
- gaps_in / gaps_out — совпадают ли отступы
- col.active_border — цвет активной рамки
- rounding — скругления углов
- active_opacity / inactive_opacity — прозрачность

### Kitty (если есть):
- foreground / background — цвета
- font_family / font_size — шрифт

## Конфигурационные файлы:
{configs_text}

## Формат ответа:
Верни ТОЛЬКО JSON:
```json
{{
  "issues": [
    {{
      "file": "waybar_config",
      "description": "Отсутствует модуль clock в modules-right",
      "severity": "error",
      "suggestion": "Добавь 'custom/clock' в modules-right"
    }},
    {{
      "file": "wofi_style",
      "description": "Цвет фона слишком темный",
      "severity": "warning",
      "suggestion": "Измени background-color на #..."
    }}
  ],
  "summary": "Найдено X замечаний"
}}
```
"""

    def _build_fix_prompt(self, configs: dict[str, str], issues: list[dict]) -> str:
        """Создаёт промпт для исправления конфигов."""
        configs_text = "\n\n".join(
            f"### {key} ###\n{content}" for key, content in configs.items()
        )

        issues_text = "\n".join(
            f"- [{issue['severity']}] {issue['file']}: {issue['description']}"
            for issue in issues
        )

        return f"""Ты эксперт по Linux rice. Исправь конфиги на основе замечаний.

## ЗАДАЧА:
Исправь найденные расхождения между конфигами и скриншотом.
Измени ТОЛЬКО проблемные параметры, остальное оставь без изменений.

## Найденные замечания:
{issues_text}

## Текущие конфиги:
{configs_text}

## Формат ответа:
Верни ТОЛЬКО JSON с исправленными конфигами:
```json
{{
  "hyprland": "# исправленный конфиг hyprland",
  "waybar_config": "{{ ... }}",
  "waybar_style": "/* исправленный CSS */",
  "wofi_config": "mode=drun...",
  "wofi_style": "/* исправленный CSS */",
  "kitty": "# исправленный конфиг kitty"
}}
```

Включи только те конфиги, которые нужно исправить.
"""

    def _extract_analysis_json(self, text: str) -> dict:
        """Извлекает JSON с анализом из ответа."""
        if not text:
            return {"issues": [], "summary": "Пустой ответ от ИИ"}

        match = re.search(r"```(?:json)?\s*({.*?})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Пробуем найти JSON без блока
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return {"issues": [], "summary": "Не удалось проанализировать"}

    def _extract_fixed_configs(self, text: str) -> dict[str, str]:
        """Извлекает исправленные конфиги из ответа."""
        if not text:
            return {}

        match = re.search(r"```(?:json)?\s*({.*?})\s*```", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                allowed_keys = ["hyprland", "waybar_config", "waybar_style", "wofi_config", "wofi_style", "kitty"]
                return {
                    key: value
                    for key, value in data.items()
                    if key in allowed_keys
                }
            except json.JSONDecodeError:
                pass

        return {}

    def _get_filepath(self, output_dir: Path, file_key: str) -> Optional[Path]:
        """Возвращает путь к файлу по ключу."""
        mapping = {
            "hyprland": "hyprland.conf",
            "waybar_config": "waybar_config.json",
            "waybar_style": "waybar_style.css",
            "wofi_config": "wofi_config",
            "wofi_style": "wofi_style.css",
            "kitty": "kitty.conf",
        }

        filename = mapping.get(file_key)
        if filename:
            return output_dir / filename
        return None
