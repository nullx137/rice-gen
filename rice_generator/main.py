"""Главный модуль для генерации райсов."""

import json
import sys
import time
from pathlib import Path
from typing import Optional

from .openrouter_client import OpenRouterClient
from .config_parser import ConfigParser, ConfigGenerator
from .separate_generator import SeparateGenerator
from .config import settings


# ANSI цвета
BLUE = "\033[94m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Анимация пульсирующей звёздочки
SPINNER_FRAMES = ["✦", "✧", "✦", "◇"]


class PulseSpinner:
    """Пульсирующий спиннер в стиле cloud code CLI."""

    def __init__(self):
        self._running = False
        self._thread = None

    def start(self, text: str, color: str = BLUE):
        """Запуск спиннера."""
        import threading

        self._running = True
        self._text = text
        self._color = color
        self._frame = 0

        def _spin():
            while self._running:
                frame = SPINNER_FRAMES[self._frame % len(SPINNER_FRAMES)]
                # Пульсация: яркий → тусклый
                if self._frame % 2 == 0:
                    print(f"\r{color}{BOLD}{frame}{RESET} {text}", end="", flush=True)
                else:
                    print(f"\r{color}{DIM}{frame}{RESET} {text}", end="", flush=True)
                self._frame += 1
                time.sleep(0.3)

        self._thread = threading.Thread(target=_spin, daemon=True)
        self._thread.start()

    def stop(self, success: bool = True):
        """Остановка спиннера."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        icon = "✦"
        if success:
            print(f"\r{GREEN}{BOLD}{icon}{RESET} {self._text} {GREEN}готово{RESET}")
        else:
            print(f"\r{RED}{BOLD}✗{RESET} {self._text} {RED}ошибка{RESET}")


# Глобальный спиннер
spinner = PulseSpinner()


class PulsePrinter:
    """Вывод с пульсирующими звёздочками в стиле cloud code CLI."""

    @staticmethod
    def pulse(text: str, color: str = BLUE):
        """Пульсирующий текст с анимацией."""
        print(f"{BOLD}{color}✦{RESET} {text}")

    @staticmethod
    def done(text: str):
        """Готово."""
        print(f"{BOLD}{GREEN}✦{RESET} {text}")

    @staticmethod
    def error(text: str):
        """Ошибка."""
        print(f"{BOLD}{RED}✗{RESET} {text}")


class RiceGenerator:
    """Основной класс для генерации конфигов на основе скриншота."""

    def __init__(
        self,
        api_key: str | None = None,
        templates_dir: str | Path | None = None,
        model: str | None = None,
        separate: bool = True,
        hyprland_config: str | Path | None = None,
        provider: str | None = None,
        wallpaper_model: str | None = None,
    ):
        """
        Инициализация генератора.

        Args:
            api_key: API ключ.
            templates_dir: Директория с шаблонами.
            model: Модель для анализа (по умолчанию из конфига).
            separate: Использовать раздельные запросы (рекомендуется).
            hyprland_config: Путь к пользовательскому hyprland.conf.
            provider: API провайдер (openrouter или cometapi).
            wallpaper_model: Модель для генерации обоев.
        """
        self.api_key = api_key
        self.templates_dir = Path(templates_dir) if templates_dir else None
        self.model = model or settings.MODEL
        self.separate = separate
        self.hyprland_config = Path(hyprland_config) if hyprland_config else None
        self.provider = provider or settings.API_PROVIDER
        self.wallpaper_model = wallpaper_model or settings.WALLPAPER_MODEL

        if self.templates_dir is None:
            self.templates_dir = Path(__file__).parent / "templates"

    def generate(
        self,
        screenshot_path: str | Path,
        output_dir: str | Path,
    ) -> dict[str, Path]:
        """
        Генерирует конфиги на основе скриншота.

        Args:
            screenshot_path: Путь к скриншоту.
            output_dir: Директория для сохранения результатов.

        Returns:
            Словарь с путями к сгенерированным файлам.
        """
        screenshot_path = Path(screenshot_path)
        output_dir = Path(output_dir)

        if not screenshot_path.exists():
            raise FileNotFoundError(f"Скриншот не найден: {screenshot_path}")

        # Загрузка шаблонов
        if self.hyprland_config and self.hyprland_config.exists():
            print(f"📄 Используем ваш hyprland.conf: {self.hyprland_config}")
            hyprland_template = self.hyprland_config.read_text()
        else:
            hyprland_template = (self.templates_dir / "hyprland.conf").read_text()

        waybar_template = (self.templates_dir / "waybar.json").read_text()
        waybar_style_template = (self.templates_dir / "waybar_style.css").read_text()
        wofi_template = (self.templates_dir / "wofi_config").read_text()
        wofi_style_template = (self.templates_dir / "wofi_style.css").read_text()
        kitty_template = (self.templates_dir / "kitty.conf").read_text()

        if self.separate:
            print("📸 Анализ скриншота...")
            print(f"🤖 Модель анализа: {self.model}")
            print(f"🎨 Модель обоев: {self.wallpaper_model}")
            print("=" * 40)

            # Используем раздельные запросы
            generator = SeparateGenerator(
                self.api_key, 
                self.model, 
                self.provider,
                wallpaper_model=self.wallpaper_model
            )

            # 1. Генерация Hyprland
            spinner.start("Генерация Hyprland...", BLUE)
            try:
                hyprland_conf = generator.generate_hyprland(
                    screenshot_path=screenshot_path,
                    template=hyprland_template,
                )
                spinner.stop(success=True)
            except Exception:
                spinner.stop(success=False)
                raise

            # Задержка между запросами
            if settings.REQUEST_DELAY > 0:
                print(f"{DIM}   ⏳ Ожидание {settings.REQUEST_DELAY}с...{RESET}")
                time.sleep(settings.REQUEST_DELAY)

            # 2. Генерация Waybar
            spinner.start("Генерация Waybar...", YELLOW)
            try:
                waybar_config, waybar_style = generator.generate_waybar(
                    screenshot_path=screenshot_path,
                    config_template=waybar_template,
                    style_template=waybar_style_template,
                )
                spinner.stop(success=True)
            except Exception:
                spinner.stop(success=False)
                raise

            # Задержка между запросами
            if settings.REQUEST_DELAY > 0:
                print(f"{DIM}   ⏳ Ожидание {settings.REQUEST_DELAY}с...{RESET}")
                time.sleep(settings.REQUEST_DELAY)

            # 3. Генерация Wofi
            spinner.start("Генерация Wofi...", MAGENTA)
            try:
                wofi_config, wofi_style = generator.generate_wofi(
                    screenshot_path=screenshot_path,
                    config_template=wofi_template,
                    style_template=wofi_style_template,
                )
                spinner.stop(success=True)
            except Exception:
                spinner.stop(success=False)
                raise

            # Задержка между запросами
            if settings.REQUEST_DELAY > 0:
                print(f"{DIM}   ⏳ Ожидание {settings.REQUEST_DELAY}с...{RESET}")
                time.sleep(settings.REQUEST_DELAY)

            # 4. Генерация Kitty
            spinner.start("Генерация Kitty...", GREEN)
            try:
                kitty_conf = generator.generate_kitty(
                    screenshot_path=screenshot_path,
                    template=kitty_template,
                )
                spinner.stop(success=True)
            except Exception:
                spinner.stop(success=False)
                raise

            # 5. Генерация обоев
            output_dir.mkdir(parents=True, exist_ok=True)
            wallpaper_path = output_dir / "wallpaper.png"
            spinner.start("Генерация обоев...", CYAN)
            try:
                generator.generate_wallpaper(
                    screenshot_path=screenshot_path,
                    output_path=wallpaper_path,
                )
                spinner.stop(success=True)
            except Exception:
                spinner.stop(success=False)
                wallpaper_path = None

            print("=" * 40)
            print("📝 Обработка результатов...")

            # Создаём GeneratedConfig из результатов
            from .config_parser import GeneratedConfig

            config = GeneratedConfig(
                hyprland_conf=hyprland_conf,
                waybar_conf=waybar_style,
                waybar_config=waybar_config,
                wofi_conf=wofi_style,
                wofi_config=wofi_config,
                kitty_conf=kitty_conf,
                color_scheme={},
                fonts={},
                gaps={},
                notes="Сгенерировано с раздельными запросами",
                wallpaper_path=wallpaper_path,
            )
        else:
            # Старый метод (единый запрос)
            print("📸 Анализ скриншота...")
            print(f"🤖 Модель: {self.model}")
            
            with OpenRouterClient(self.api_key, self.model, self.provider) as client:
                response = client.analyze_screenshot(
                    screenshot_path=screenshot_path,
                    hyprland_template=hyprland_template,
                    waybar_template=waybar_template,
                    kitty_template=kitty_template,
                )

            print("📝 Обработка ответа...")
            parser = ConfigParser(response)
            config = parser.parse()

        # Генерация файлов
        gen = ConfigGenerator(config, output_dir)
        paths = gen.generate_all()

        print(f"✅ Конфиги сгенерированы в: {output_dir.absolute()}")
        print(f"📄 Файлов создано: {len(paths)}")

        return paths
