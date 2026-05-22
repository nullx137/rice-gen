#!/usr/bin/env python3
"""CLI интерфейс для rice-generator."""

import argparse
import sys
from pathlib import Path

from .main import RiceGenerator
from .config import settings


def main():
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(
        prog="rice-generator",
        description="Генерация конфигов для Hyprland, Waybar и Kitty на основе скриншота",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s screenshot.png -o ./output
  %(prog)s ~/Pictures/rice.png --api-key your_key
  %(prog)s screenshot.png --wallpaper-model openai/dall-e-3

Переменные окружения:
  API_PROVIDER           Провайдер API: openrouter или cometapi (по умолчанию: openrouter)
  OPENROUTER_API_KEY     API ключ для OpenRouter
  RICE_MODEL            Модель для анализа (по умолчанию: google/gemini-3-flash-preview)
  WALLPAPER_MODEL       Модель для генерации обоев (по умолчанию: openai/dall-e-3)
        """,
    )

    parser.add_argument(
        "screenshot",
        type=str,
        help="Путь к скриншоту для анализа",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="./generated_configs",
        help="Директория для сохранения конфигов (по умолчанию: ./generated_configs)",
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API ключ (для OpenRouter или CometAPI)",
    )

    parser.add_argument(
        "--provider",
        type=str,
        choices=["openrouter", "cometapi"],
        default=None,
        help="API провайдер (по умолчанию: openrouter)",
    )

    parser.add_argument(
        "-m",
        "--model",
        type=str,
        default=None,
        help="Модель для анализа (по умолчанию: из конфига)",
    )

    parser.add_argument(
        "--wallpaper-model",
        type=str,
        default=None,
        help="Модель для генерации обоев (по умолчанию: из конфига)",
    )

    parser.add_argument(
        "-t",
        "--templates",
        type=str,
        default=None,
        help="Директория с шаблонами (по умолчанию: встроенные шаблоны)",
    )

    parser.add_argument(
        "-H",
        "--hyprland-config",
        type=str,
        default=None,
        help="Путь к вашему hyprland.conf (по умолчанию: встроенный шаблон)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Включить подробный вывод",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )

    args = parser.parse_args()

    try:
        provider = args.provider or settings.API_PROVIDER
        print("🚀 Rice Generator v0.1.0")
        print(f"📡 API: {provider}")
        print("=" * 40)

            generator = RiceGenerator(
                api_key=args.api_key,
                templates_dir=args.templates,
                model=args.model,
                hyprland_config=args.hyprland_config,
                provider=provider,
                wallpaper_model=args.wallpaper_model,
            )

        paths = generator.generate(
            screenshot_path=args.screenshot,
            output_dir=args.output,
        )

        # Проверка конфигов (обязательная)
        print("\n🔍 Запуск ИИ-проверки конфигов...")
        from .validator import AIValidator

        ai_validator = AIValidator(
            api_key=args.api_key,
            model=args.model,
            provider=provider,
        )
        results = ai_validator.validate_and_fix(
            screenshot_path=args.screenshot,
            output_dir=args.output,
            max_iterations=2,
        )
        if results:
            print(f"\n✅ Исправлено файлов: {len(results)}")
        else:
            print("\n✅ Все конфиги соответствуют скриншоту!")

        print("=" * 40)
        print("📁 Сгенерированные файлы:")
        for name, path in paths.items():
            print(f"   • {name}: {path}")

        print("\n▶️  Для применения конфигов выполните:")
        print(f"   cd {args.output}")
        print("   chmod +x installer.sh")
        print("   ./installer.sh")

        return 0

    except FileNotFoundError as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        return 1

    except ValueError as e:
        print(f"❌ Ошибка обработки: {e}", file=sys.stderr)
        return 2

    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        else:
            print(f"❌ Произошла ошибка: {e}", file=sys.stderr)
            print("   Используйте --verbose для подробностей", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
