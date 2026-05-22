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

<<<<<<< HEAD
## ⚠️ КРИТИЧЕСКИ ВАЖНО — ЧТО МОЖНО ПРОВЕРЯТЬ:
Ты должен проверять ТОЛЬКО визуальные параметры и внешний вид.
НИКОГДА не создавай замечания, связанные с:
- binds, input, monitor, exec-once, exec, env
- layerrule, windowrule, windowrulev2, workspace
- переменными, не относящимися к цветам/визуальному оформлению
- путями к скриптам, командам, программам
- горячими клавишами, раскладками клавиатуры, сенситивити мыши
- настройками аудио, сети, Bluetooth и т.д.
=======
## ГЛАВНАЯ ЗАДАЧА:
Внимательно рассмотри скриншот и проверь конфиги Waybar и Wofi на наличие и правильное расположение модулей.
>>>>>>> 19bba975c3ba1563a80f2431b927745f39e0d1e4

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

## 📝 ПРОВЕРКА ДРУГИХ КОНФИГОВ (ТОЛЬКО ВИЗУАЛЬНЫЕ ПАРАМЕТРЫ):

### Hyprland — можно проверять:
- gaps_in / gaps_out — отступы
- col.active_border — цвет активной рамки
- rounding — скругления углов
- active_opacity / inactive_opacity — прозрачность

### Hyprland — НЕЛЬЗЯ проверять и предлагать изменять:
- binds (любые горячие клавиши)
- input (раскладка, сенситивити, accel speed и т.д.)
- monitor (разрешение, частота, позиция)
- exec / exec-once / env
- layerrule / windowrule / windowrulev2 / workspace

### Kitty — можно проверять:
- foreground / background — цвета
- font_family / font_size — шрифт
<<<<<<< HEAD
- window_padding_width — отступы
- cursor / cursor_text_color

### Kitty — НЕЛЬЗЯ проверять:
- shell_integration
- scrollback_lines
- cursor_blink_interval
- enable_audio_bell
- map (горячие клавиши)
- любые другие функциональные параметры
=======
>>>>>>> 19bba975c3ba1563a80f2431b927745f39e0d1e4

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

## ⚠️ АБСОЛЮТНЫЙ ЗАПРЕТ — НИ ПРИ КАКОМ УСЛОВИИ НЕ МЕНЯЙ:
- **В Hyprland:**
  - ВСЕ binds (горячие клавиши, хоткеи, мышиные бинды)
  - input (раскладка клавиатуры, сенситивити мыши, accel speed и т.д.)
  - monitor (разрешение, частота, позиция, масштаб)
  - exec-once, exec, env
  - layerrule, windowrule, windowrulev2, workspace
  - любые переменные и пути к скриптам/программам
  - любые декларации, не относящиеся к визуальному оформлению

- **В Waybar:**
  - НЕ меняй формат вывода модулей (кроме CSS-стилей)
  - НЕ добавляй/удаляй настройки модулей, кроме их наличия в modules-left/center/right
  - НЕ меняй команды, интервалы опроса, пути к скриптам

- **В Kitty:**
  - НЕ меняй shell_integration
  - НЕ меняй scrollback_lines, cursor_blink_interval, enable_audio_bell
  - НЕ меняй map (любые горячие клавиши)
  - НЕ меняй функциональные параметры

## ✅ РАЗРЕШЁННЫЕ ИЗМЕНЕНИЯ (и НИЧЕГО БОЛЬШЕ):
- **Hyprland:** gaps_in, gaps_out, col.active_border, col.inactive_border, rounding, active_opacity, inactive_opacity, border_size, shadow.*, blur.*, decoration.*
- **Waybar:** modules-left, modules-center, modules-right, height, layer, position, а также ТОЛЬКО CSS-свойства (background, color, border-radius, padding, margin, font-family, font-size, opacity)
- **Kitty:** foreground, background, color0-15, selection_foreground, selection_background, cursor, cursor_text_color, window_padding_width, font_family, font_size

## 🛡️ ПРАВИЛО ОБРАБОТКИ ЗАМЕЧАНИЙ:
1. Если замечание требует изменить что-то из ЗАПРЕЩЁННОГО списка — **ПОЛНОСТЬЮ ИГНОРИРУЙ** это замечание.
2. НЕ включай файл в ответ, если для него остались только запрещённые замечания.
3. Верни ТОЛЬКО те файлы, где нужны РАЗРЕШЁННЫЕ изменения.
4. Всё остальное в файлах оставь БЕЗ ИЗМЕНЕНИЙ — не добавляй, не удаляй, не переформатируй.

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
        """Извлекает JSON с анализом из ответа ИИ."""
        if not text:
            return {"issues": [], "summary": "Пустой ответ от ИИ"}

        # Strategy 1: Extract from markdown code blocks
        patterns = [
            r"```json\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                content = match.group(1).strip()
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    if getattr(settings, 'VERBOSE', False):
                        print(f"   ⚠️  JSON parse error in analysis block: {e}")
                    continue

        # Strategy 2: Try to parse the whole stripped text
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find balanced JSON by brace depth
        data = self._extract_json_by_braces(text)
        if data and isinstance(data, dict):
            return data

        # Strategy 4: Try the old simple regex as last resort
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        preview = text[:200].replace('\n', ' ')
        print(f"   ⚠️  Не удалось извлечь JSON анализа (preview: {preview}...)")
        return {"issues": [], "summary": "Не удалось проанализировать"}

    def _extract_fixed_configs(self, text: str) -> dict[str, str]:
        """Извлекает исправленные конфиги из ответа ИИ."""
        if not text:
            print("   ⚠️  Пустой ответ от ИИ (извлечение конфигов)")
            return {}

        allowed_keys = ["hyprland", "waybar_config", "waybar_style", "wofi_config", "wofi_style", "kitty"]

        # Strategy 1: Extract full content from markdown code blocks
        # First try ```json ... ``` then ``` ... ```
        patterns = [
            r"```json\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                content = match.group(1).strip()
                try:
                    data = json.loads(content)
                    return {k: v for k, v in data.items() if k in allowed_keys}
                except json.JSONDecodeError as e:
                    if getattr(settings, 'VERBOSE', False):
                        print(f"   ⚠️  JSON parse error in code block: {e}")
                    continue

        # Strategy 2: Try to parse the whole stripped text as JSON
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                data = json.loads(stripped)
                return {k: v for k, v in data.items() if k in allowed_keys}
            except json.JSONDecodeError:
                pass

        # Strategy 3: Find balanced JSON object by tracking brace depth
        data = self._extract_json_by_braces(text)
        if data and isinstance(data, dict):
            return {k: v for k, v in data.items() if k in allowed_keys}

        # Strategy 4: Show partial response for debugging
        preview = text[:200].replace('\n', ' ')
        print(f"   ⚠️  Не удалось извлечь JSON из ответа ИИ (preview: {preview}...)")
        if getattr(settings, 'VERBOSE', False):
            print(f"   DEBUG raw response:\n{text[:1000]}")
        return {}

    def _extract_json_by_braces(self, text: str) -> Optional[dict]:
        """Извлекает JSON объект из текста, отслеживая баланс скобок."""
        start = text.find('{')
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape_next = False
        end = start

        for i, char in enumerate(text[start:], start):
            if escape_next:
                escape_next = False
                continue
            if char == '\\' and in_string:
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break

        if depth == 0:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                # Try simple fixes: remove trailing commas, fix single quotes
                fixed = self._quick_json_fix(text[start:end])
                if fixed:
                    try:
                        return json.loads(fixed)
                    except json.JSONDecodeError:
                        pass
        return None

    @staticmethod
    def _quick_json_fix(json_str: str) -> Optional[str]:
        """Пробует быстро исправить частые ошибки в JSON от ИИ."""
        # Remove trailing commas before } or ]
        fixed = re.sub(r',\s*(\}|\])', r'\1', json_str)
        # Replace unescaped newlines in strings (simple heuristic)
        # This is a best-effort attempt
        try:
            # Test if it parses now
            json.loads(fixed)
            return fixed
        except json.JSONDecodeError:
            pass
        return None

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
