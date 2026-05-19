"""Генератор конфигов с раздельными запросами для каждого компонента."""

import json
import re
import httpx
from pathlib import Path
from typing import Optional

from .openrouter_client import OpenRouterClient
from .config import settings


class SeparateGenerator:
    """Генератор с раздельными запросами для Waybar и Kitty."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        wallpaper_model: Optional[str] = None,
    ):
        """
        Инициализация генератора.

        Args:
            api_key: API ключ.
            model: Модель для анализа.
            provider: API провайдер (openrouter или cometapi).
            wallpaper_model: Модель для генерации обоев.
        """
        self.provider = provider or settings.API_PROVIDER
        if self.provider == "cometapi":
            self.api_key = api_key or settings.COMETAPI_API_KEY
        else:
            self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.model = model or settings.MODEL
        self.wallpaper_model = wallpaper_model or settings.WALLPAPER_MODEL

    def load_template(self, template_name: str) -> str:
        """Загружает шаблон из директории templates."""
        template_path = Path(__file__).parent / "templates" / template_name
        if template_path.exists():
            return template_path.read_text()
        return ""

    def generate_hyprland(
        self,
        screenshot_path: str | Path,
        template: str,
    ) -> str:
        """
        Генерирует конфиг Hyprland на основе шаблона.

        Args:
            screenshot_path: Путь к скриншоту.
            template: Шаблон конфига.

        Returns:
            Сгенерированный конфиг Hyprland.
        """
        prompt = self._build_hyprland_prompt(template)

        with OpenRouterClient(self.api_key, self.model, self.provider) as client:
            response = client.analyze_image_with_prompt(
                screenshot_path=screenshot_path,
                prompt=prompt,
                max_tokens=None,  # Без ограничений
            )

        return self._extract_code_block(response, "hyprland")

    def generate_waybar(
        self,
        screenshot_path: str | Path,
        config_template: str,
        style_template: str,
    ) -> tuple[str, str]:
        """
        Генерирует конфиги Waybar (config + style).

        Args:
            screenshot_path: Путь к скриншоту.
            config_template: Шаблон config.json.
            style_template: Шаблон style.css.

        Returns:
            Кортеж (config.json, style.css).
        """
        prompt = self._build_waybar_prompt(config_template, style_template)

        with OpenRouterClient(self.api_key, self.model, self.provider) as client:
            response = client.analyze_image_with_prompt(
                screenshot_path=screenshot_path,
                prompt=prompt,
                max_tokens=None,  # Без ограничений
            )

        config = self._extract_json_config(response)
        style = self._extract_css_style(response)

        return config, style

    def generate_wofi(
        self,
        screenshot_path: str | Path,
        config_template: str,
        style_template: str,
    ) -> tuple[str, str]:
        """
        Генерирует конфиги Wofi (config + style).

        Args:
            screenshot_path: Путь к скриншоту.
            config_template: Шаблон wofi_config.
            style_template: Шаблон wofi_style.css.

        Returns:
            Кортеж (wofi_config, wofi_style.css).
        """
        prompt = self._build_wofi_prompt(config_template, style_template)

        with OpenRouterClient(self.api_key, self.model, self.provider) as client:
            response = client.analyze_image_with_prompt(
                screenshot_path=screenshot_path,
                prompt=prompt,
                max_tokens=None,  # Без ограничений
            )

        config = self._extract_wofi_config(response)
        style = self._extract_wofi_style(response)

        return config, style

    def generate_kitty(
        self,
        screenshot_path: str | Path,
        template: str,
    ) -> str:
        """
        Генерирует конфиг Kitty.

        Args:
            screenshot_path: Путь к скриншоту.
            template: Шаблон конфига.

        Returns:
            Сгенерированный конфиг Kitty.
        """
        prompt = self._build_kitty_prompt(template)

        with OpenRouterClient(self.api_key, self.model, self.provider) as client:
            response = client.analyze_image_with_prompt(
                screenshot_path=screenshot_path,
                prompt=prompt,
                max_tokens=None,  # Без ограничений
            )

        return self._extract_code_block(response, "kitty")

    def generate_wallpaper(
        self,
        screenshot_path: str | Path,
        output_path: str | Path,
    ) -> Path:
        """
        Анализирует скриншот и генерирует новые обои.

        Args:
            screenshot_path: Путь к скриншоту для анализа.
            output_path: Куда сохранить сгенерированные обои.

        Returns:
            Путь к сохраненному файлу обоев.
        """
        # 1. Генерируем промпт для картинки на основе скриншота
        analysis_prompt = """Analyze this Linux desktop screenshot. 
Create a detailed prompt for an AI image generator (like Flux or DALL-E) 
to create perfect abstract 4k wallpaper that matches this interface's colors and mood.
Return ONLY the prompt text in English, no intro, no quotes."""

        with OpenRouterClient(self.api_key, self.model, self.provider) as client:
            image_prompt = client.analyze_image_with_prompt(
                screenshot_path=screenshot_path,
                prompt=analysis_prompt
            ).strip()

        print(f"🎨 Промпт для обоев: {image_prompt[:60]}...")
        
        # 2. Генерируем изображение через wallpaper_model
        with OpenRouterClient(self.api_key, self.wallpaper_model, self.provider) as client:
            gen_prompt = f"Generate a high-quality 4k wallpaper based on this description: {image_prompt}. Return ONLY the direct URL to the image."
            
            try:
                response_text = client.analyze_image_with_prompt(
                    screenshot_path=screenshot_path,
                    prompt=gen_prompt
                )
            except Exception as e:
                print(f"❌ Ошибка API при генерации обоев: {e}")
                return Path(output_path)
            
            # Извлечение URL из ответа
            image_url = None
            
            # Пробуем найти URL в JSON (если модель вернула JSON)
            try:
                data = json.loads(response_text)
                if isinstance(data, dict):
                    image_url = data.get("url") or data.get("image_url")
            except:
                pass
            
            # Пробуем найти URL через регулярку (включая markdown)
            if not image_url:
                url_match = re.search(r'(https?://\S+)', response_text)
                if url_match:
                    image_url = url_match.group(1).strip('()[]"\'')

            if image_url:
                print(f"📥 Загрузка изображения: {image_url}")
                try:
                    with httpx.Client(follow_redirects=True, timeout=60.0) as http_client:
                        img_response = http_client.get(image_url)
                        img_response.raise_for_status()
                        Path(output_path).write_bytes(img_response.content)
                        print(f"✅ Обои сохранены: {output_path}")
                except Exception as e:
                    print(f"❌ Ошибка при скачивании изображения: {e}")
            else:
                print(f"⚠️ URL не найден в ответе. Ответ модели: {response_text[:200]}")
                # Сохраняем текст ответа для отладки, если это не бинарные данные
                if len(response_text) < 1000:
                    Path(output_path).with_suffix('.txt').write_text(response_text)
            
        return Path(output_path)

    def _build_hyprland_prompt(self, template: str) -> str:
        """Создаёт промпт для Hyprland — только замена переменных."""
        return f"""Ты эксперт по Hyprland. Проанализируй скриншот и модифицируй шаблон.

## ⚠️ ВАЖНО — ВЕРНИ ТОЛЬКО КОД:

- Верни ТОЛЬКО код конфига, БЕЗ markdown разметки (НЕ используй ```hyprland, ``` и т.д.)
- НЕ добавляй пояснений, комментариев или описаний
- Верни чистый код конфигурации

## Твоя задача:
ТОЛЬКО заменить переменные в шаблоне на основе скриншота.
НЕ добавляй новый код, НЕ удаляй существующий, НЕ меняй структуру.

## Что нужно распознать со скриншота и заменить:

1. **Gaps (отступы):**
   - gaps_in — внутренние отступы между окнами
   - gaps_out — внешние отступы от краёв экрана

2. **Цвета бордюров (borders):**
   - col.active_border — цвет активной рамки (rgba или #hex)
   - col.inactive_border — цвет неактивной рамки

3. **Прозрачность (opacity):**
   - active_opacity — прозрачность активного окна (0.0 - 1.0)
   - inactive_opacity — прозрачность неактивного окна

4. **Скругления (rounding):**
   - rounding — радиус скругления углов окон

5. **Тени (shadow):**
   - shadow.enabled — true/false
   - shadow.range — размер тени
   - shadow.color — цвет тени

6. **Блюр (blur):**
   - blur.enabled — true/false
   - blur.size — размер блюра
   - blur.passes — количество проходов

7. **Толщина бордюра:**
   - border_size — толщина рамок окон

## Шаблон для модификации:
{template}

## Формат ответа:
Верни ТОЛЬКО чистый код конфига БЕЗ markdown разметки (без ```hyprland, ``` и т.д.)

## ⚠️ ЗАПРЕЩЕНО:
- Добавлять новые секции
- Удалять существующие секции
- Менять binds (горячие клавиши)
- Менять input настройки
- Менять monitor настройки
- Добавлять комментарии

## ✅ РАЗРЕШЕНО:
- Заменить gaps_in, gaps_out
- Заменить col.active_border, col.inactive_border
- Заменить active_opacity, inactive_opacity
- Заменить rounding
- Заменить shadow параметры
- Заменить blur параметры
- Заменить border_size
"""

    def _build_waybar_prompt(self, config_template: str, style_template: str) -> str:
        """Создаёт промпт для Waybar."""
        return f"""Ты эксперт по Waybar. Проанализируй скриншот и создай два файла.

## КРИТИЧЕСКИ ВАЖНО - ВНИМАТЕЛЬНО ИЗУЧИ СКРИНШОТ:

### 1. ТИП WAYBAR (определи точно):
**Прозрачный или сплошной:**
- Если фон бара прозрачный/полупрозрачный → используй rgba с прозрачностью
- Если сплошной цвет → используй solid color

**Цельный или раздельный:**
- Цельный (единая полоса) → один window#waybar на весь экран
- Раздельный (модули отдельно) → каждый модуль в отдельном блоке с margin

### 2. РАСПОЛОЖЕНИЕ МОДУЛЕЙ (определи точно):
**Где какие модули находятся:**
- modules-left: какие модули СЛЕВА (workspaces, tray, и т.д.)
- modules-center: какие модули ПО ЦЕНТРУ (window, clock, media)
- modules-right: какие модули СПРАВА (pulseaudio, network, battery, clock)

**Визуально определи порядок:**
- Посмотри на скриншот слева направо
- Запиши модули в том порядке, в котором они видны

### 3. СТИЛЬ (распознай детали):
- Высота бара (обычно 30-40px)
- Закругления (border-radius)
- Отступы между модулями (margin, padding)
- Градиенты или сплошной цвет
- Тени у бара

## КРИТИЧЕСКИ ВАЖНО:
- Пиши ТОЛЬКО чистый код БЕЗ комментариев
- В JSON не используй // комментарии
- В CSS минимизируй комментарии
- Верни ПОЛНЫЕ файлы без сокращений

## 1. config.json (структура):
- layer: "top" или "bottom"
- position: "top" или "bottom"
- height: высота бара (обычно 30-40)
- modules-left: [список модулей слева]
- modules-center: [список модулей по центру]
- modules-right: [список модулей справа]
- Настройки каждого модуля

## 2. style.css (внешний вид):
- background: цвет/прозрачность фона
- color: цвет текста
- border-radius: скругления
- padding/margin: отступы
- font-family: шрифт (JetBrainsMono Nerd Font)
- font-size: размер шрифта

## Шаблоны:
### config.json:
{config_template}

### style.css:
{style_template}

## Формат ответа:
Верни ТОЛЬКО чистый JSON и CSS БЕЗ markdown разметки (без ```json, ```css и т.д.)

Сначала JSON конфиг, потом CSS стиль (разделённые пустой строкой).
"""

    def _build_kitty_prompt(self, template: str) -> str:
        """Создаёт промпт для Kitty."""
        return f"""Ты эксперт по Kitty. Проанализируй скриншот и создай конфиг.

## КРИТИЧЕСКИ ВАЖНО:
- Пиши ТОЛЬКО чистый код БЕЗ комментариев
- Не используй # комментарии в конфиге
- Верни ПОЛНЫЕ файлы без сокращений

## Распознай со скриншота:
- Цветовую схему (foreground, background, color0-15)
- Шрифт и размер
- Отступы (window_padding_width)
- Прозрачность (background_opacity)
- Стиль табов (если видны)

## Структура конфига:
- shell_integration
- font_family, font_size
- foreground, background
- color0 - color15
- selection_foreground, selection_background
- cursor, cursor_text_color
- window_padding_width
- tab_bar_style (если есть табы)
- map = (горячие клавиши - стандартные)

## Шаблон:
{template}

## Формат ответа:
Верни ТОЛЬКО код в блоке:
```kitty
shell_integration no-rc
font_family JetBrainsMono Nerd Font
font_size 12.0
foreground #c0caf5
background #1a1b26
color0 #15161e
color1 #f7768e
...
```
"""

    def _build_wofi_prompt(self, config_template: str, style_template: str) -> str:
        """Создаёт промпт для Wofi."""
        return f"""Ты эксперт по Wofi (launcher для Wayland). Проанализируй скриншот и создай два файла.

## КРИТИЧЕСКИ ВАЖНО — ВНИМАТЕЛЬНО ИЗУЧИ СКРИНШОТ:

### 1. РАЗМЕР И ПОЗИЦИЯ (определи точно):
- width — ширина окна (процент или px)
- height — высота окна (процент или px)
- location — позиция на экране (center, top, bottom, и т.д.)

### 2. ЦВЕТА (распознай со скриншота):
- background — цвет фона окна
- text color — цвет текста
- border color — цвет рамки
- selected background — цвет выделенного элемента
- selected text — цвет текста выделенного элемента

### 3. СТИЛЬ (распознай детали):
- border — толщина и стиль рамки (2px solid, и т.д.)
- font-family — шрифт
- border-radius — скругления углов
- padding — отступы внутри элементов
- margin — внешние отступы

### 4. ПАРАМЕТРЫ (определи визуально):
- allow_images — true/false (есть ли иконки у приложений)
- image_size — размер иконок
- show — режим (drun, run, window)
- prompt — текст подсказки

## ШАБЛОНЫ:
### wofi_config:
{config_template}

### wofi_style.css:
{style_template}

## Формат ответа:
Верни ТОЛЬКО чистый код БЕЗ markdown разметки (без ```config, ```css и т.д.)

Сначала wofi_config, потом wofi_style.css (разделённые пустой строкой).
"""

    def _extract_wofi_config(self, text: str) -> str:
        """Извлекает wofi_config из ответа."""
        match = re.search(r"```config\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Альтернативный поиск
        match = re.search(r"```wofi_config\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _extract_wofi_style(self, text: str) -> str:
        """Извлекает wofi_style.css из ответа."""
        match = re.search(r"```css\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _extract_code_block(self, text: str, lang: Optional[str] = None) -> str:
        """Извлекает код из markdown блока."""
        patterns = []
        if lang:
            patterns.append(rf"```{lang}\s*(.*?)\s*```")
        patterns.extend(
            [
                r"```hyprland\s*(.*?)\s*```",
                r"```kitty\s*(.*?)\s*```",
                r"```\s*(.*?)\s*```",
            ]
        )

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()

        # Если не найдено, возвращаем весь текст
        return text.strip()

    def _extract_json_config(self, text: str) -> str:
        """Извлекает JSON конфиг."""
        match = re.search(r"```(?:json)?\s*({.*?})\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _extract_css_style(self, text: str) -> str:
        """Извлекает CSS стиль."""
        match = re.search(r"```(?:css)?\s*(/\*.*?\*/.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Альтернативный паттерн
        match = re.search(r"```css\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()

        return text.strip()
