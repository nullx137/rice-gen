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

## ⚠️ КРИТИЧЕСКИ ВАЖНО — ЧТО МОЖНО ПРОВЕРЯТЬ:
Ты должен проверять ТОЛЬКО визуальные параметры и внешний вид.
НИКОГДА не создавай замечания, связанные с:
- binds, input, monitor, exec-once, exec, env
- layerrule, windowrule, windowrulev2, workspace
- переменными, не относящимися к цветам/визуальному оформлению
- путями к скриптам, командам, программам
- горячими клавишами, раскладками клавиатуры, сенситивити мыши
- настройками аудио, сети, Bluetooth и т.д.

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
- Правильный ли порядок?

### 3. Внешний вид модулей:
- Есть ли иконки у модулей? (🔊, 📶, 🔋, 🕐)
- Правильный ли формат вывода?
- Видны ли все модули или какие-то скрыты?
- Нет ли "квадратов" вместо иконок?

### 4. Структура бара:
- Цельный бар (сплошная полоса) или раздельный (модули отдельно)?
- Прозрачный или сплошной фон?
- Высота бара соответствует скриншоту?

## 📝 ПРОВЕРКА ДРУГИХ КОНФИГОВ (ТОЛЬКО ВИЗУАЛЬНЫЕ ПАРАМЕТРЫ):

### Hyprland — можно проверять:
- gaps_in / gaps_out — отступы
- col.active_border — цвет активной рамки
- col.inactive_border — цвет неактивной рамки
- rounding — скругления углов
- active_opacity / inactive_opacity — прозрачность
- border_size — толщина рамок
- shadow.enabled, shadow.range — тени
- blur.enabled, blur.size — блюр

### Hyprland — НЕЛЬЗЯ проверять и предлагать изменять:
- binds (любые горячие клавиши)
- input (раскладка, сенситивити, accel speed и т.д.)
- monitor (разрешение, частота, позиция)
- exec / exec-once / env
- layerrule / windowrule / windowrulev2 / workspace

### Kitty — можно проверять:
- foreground / background — цвета
- color0-15 — палитра
- font_family / font_size — шрифт
- window_padding_width — отступы
- cursor / cursor_text_color

### Kitty — НЕЛЬЗЯ проверять:
- shell_integration
- scrollback_lines
- cursor_blink_interval
- enable_audio_bell
- map (горячие клавиши)
- любые другие функциональные параметры

## Конфигурационные файлы:
{configs_text}

## Формат ответа:
Верни ТОЛЬКО JSON:
```json
{{
  "issues": [
    {{
      "file": "waybar_config",
      "description": "Отсутствует модуль clock в modules-right — на скриншоте видно часы справа",
      "severity": "error",
      "suggestion": "Добавь 'custom/clock' в modules-right"
    }},
    {{
      "file": "waybar_config",
      "description": "Модуль battery есть в конфиге, но на скриншоте его нет",
      "severity": "warning",
      "suggestion": "Удали 'battery' из modules-right"
    }},
    {{
      "file": "hyprland",
      "description": "gaps_in = 5, но на скриншоте отступы больше (~10)",
      "severity": "error",
      "suggestion": "Измени gaps_in на 10"
    }}
  ],
  "summary": "Найдено 3 замечания"
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
                return {
                    key: value
                    for key, value in data.items()
                    if key in ["hyprland", "waybar_config", "waybar_style", "kitty"]
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
            "kitty": "kitty.conf",
        }

        filename = mapping.get(file_key)
        if filename:
            return output_dir / filename
        return None
