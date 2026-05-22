"""Парсер и генератор конфигов на основе ответа нейросети."""

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional



@dataclass
class GeneratedConfig:
    """Структура для хранения сгенерированных конфигов."""

    hyprland_conf: str
    waybar_conf: str
    waybar_config: str
    wofi_conf: str
    wofi_config: str
    kitty_conf: str
    color_scheme: dict
    fonts: dict
    gaps: dict
    notes: str
    wallpaper_path: Optional[Path] = None


class ConfigParser:
    """Парсер ответа нейросети и генератор конфигов."""

    def __init__(self, response: str):
        """
        Инициализация парсера.

        Args:
            response: Ответ нейросети.
        """
        self.response = response
        self.json_content: Optional[dict] = None

    def extract_json(self) -> dict:
        """
        Извлекает JSON из ответа нейросети.

        Returns:
            Словарь с данными конфигов.

        Raises:
            ValueError: Если JSON не найден или невалидный.
        """
        # Попытка найти JSON в ответе
        json_match = re.search(
            r"```(?:json)?\s*({.*?})\s*```", self.response, re.DOTALL
        )

        if json_match:
            json_str = json_match.group(1)
        else:
            # Если нет markdown блоков, пробуем найти JSON напрямую
            json_match = re.search(r"\{.*\}", self.response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                raise ValueError("Не удалось найти JSON в ответе нейросети")

        try:
            self.json_content = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Попытка исправить обрезанный JSON
            fixed_json = self._try_fix_json(json_str)
            if fixed_json:
                self.json_content = fixed_json
            else:
                raise ValueError(f"Невалидный JSON: {e}")

        return self.json_content

    def _try_fix_json(self, json_str: str) -> Optional[dict]:
        """
        Пытается исправить обрезанный JSON.

        Args:
            json_str: Строка JSON.

        Returns:
            Исправленный словарь или None.
        """
        # Добавляем закрывающие скобки если они обрезаны
        brackets = json_str.count('{') - json_str.count('}')
        braces = json_str.count('[') - json_str.count(']')
        quotes = json_str.count('"') % 2

        fixed = json_str
        if quotes:
            fixed += '"'
        while braces > 0:
            fixed += ']'
            braces -= 1
        while brackets > 0:
            fixed += '}'
            brackets -= 1

        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None

    def parse(self) -> GeneratedConfig:
        """
        Парсит ответ и создаёт объект GeneratedConfig.

        Returns:
            Объект GeneratedConfig с конфигурациями.

        Raises:
            ValueError: Если JSON не найден или отсутствуют обязательные поля.
        """
        if not self.json_content:
            self.extract_json()

        required_fields = [
            "hyprland_conf",
            "waybar_conf",
            "waybar_config",
            "kitty_conf",
        ]

        for field in required_fields:
            if field not in self.json_content:
                raise ValueError(f"Отсутствует обязательное поле: {field}")

        return GeneratedConfig(
            hyprland_conf=self.json_content["hyprland_conf"],
            waybar_conf=self.json_content["waybar_conf"],
            waybar_config=self.json_content["waybar_config"],
            wofi_conf=self.json_content.get("wofi_conf", ""),
            wofi_config=self.json_content.get("wofi_config", ""),
            kitty_conf=self.json_content["kitty_conf"],
            color_scheme=self.json_content.get("color_scheme", {}),
            fonts=self.json_content.get("fonts", {}),
            gaps=self.json_content.get("gaps", {}),
            notes=self.json_content.get("notes", ""),
        )


class ConfigGenerator:
    """Генератор файлов конфигов и скриптов установки."""

    def __init__(self, config: GeneratedConfig, output_dir: str | Path):
        """
        Инициализация генератора.

        Args:
            config: Объект GeneratedConfig с конфигурациями.
            output_dir: Директория для сохранения файлов.
        """
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_all(self) -> dict[str, Path]:
        """
        Генерирует все файлы конфигов.

        Returns:
            Словарь с путями к сгенерированным файлам.
        """
        paths = {}

        # Генерируем конфиги
        paths["hyprland"] = self._save_file(
            "hyprland.conf", self.config.hyprland_conf
        )
        paths["waybar_style"] = self._save_file(
            "waybar_style.css", self.config.waybar_conf
        )
        paths["waybar_config"] = self._save_file(
            "waybar_config.json", self.config.waybar_config
        )
        
        if self.config.wofi_conf:
            paths["wofi_style"] = self._save_file(
                "wofi_style.css", self.config.wofi_conf
            )
        if self.config.wofi_config:
            paths["wofi_config"] = self._save_file(
                "wofi_config", self.config.wofi_config
            )
            
        paths["kitty"] = self._save_file("kitty.conf", self.config.kitty_conf)

        # Копируем обои, если они есть
        if self.config.wallpaper_path and self.config.wallpaper_path.exists():
            dest = self.output_dir / "wallpaper.png"
            if self.config.wallpaper_path.resolve() != dest.resolve():
                shutil.copy(self.config.wallpaper_path, dest)
            paths["wallpaper"] = dest

        # Генерируем скрипты
        paths["installer"] = self._generate_installer()
        paths["uninstaller"] = self._generate_uninstaller()

        # Генерируем информацию о цветовой схеме
        paths["colors"] = self._save_file(
            "color_scheme.json",
            json.dumps(
                {
                    "color_scheme": self.config.color_scheme,
                    "fonts": self.config.fonts,
                    "gaps": self.config.gaps,
                    "notes": self.config.notes,
                },
                indent=2,
                ensure_ascii=False,
            ),
        )

        return paths

    def _save_file(self, filename: str, content: str) -> Path:
        """
        Сохраняет файл в директорию вывода.

        Args:
            filename: Имя файла.
            content: Содержимое файла.

        Returns:
            Путь к сохранённому файлу.
        """
        filepath = self.output_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return filepath

    def _generate_installer(self) -> Path:
        """
        Генерирует скрипт installer.sh.

        Returns:
            Путь к скрипту установщика.
        """
        wallpaper_install = ""
        if self.config.wallpaper_path:
            wallpaper_install = f'''
if [ -f "$SCRIPT_DIR/wallpaper.png" ]; then
    echo -e "${{YELLOW}}[5/5] Установка обоев (swaybg)...${{NC}}"
    mkdir -p "$HOME/.config/hypr"
    cp "$SCRIPT_DIR/wallpaper.png" "$HOME/.config/hypr/wallpaper.png"

    if ! command -v swaybg &> /dev/null; then
        echo -e "${{YELLOW}}  swaybg не найден, устанавливаем...${{NC}}"
        if command -v pacman &> /dev/null; then
            sudo pacman -S --needed --noconfirm swaybg || echo "  ⚠ Не удалось установить swaybg"
        elif command -v apt &> /dev/null; then
            sudo apt install -y swaybg || echo "  ⚠ Не удалось установить swaybg"
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y swaybg || echo "  ⚠ Не удалось установить swaybg"
        elif command -v zypper &> /dev/null; then
            sudo zypper install -y swaybg || echo "  ⚠ Не удалось установить swaybg"
        else
            echo "  ⚠ Не удалось определить пакетный менеджер. Установите swaybg вручную."
        fi
    fi
    # Убить предыдущий swaybg
    if pgrep -x "swaybg" > /dev/null; then
        killall swaybg
        sleep 1
    fi
    swaybg -i "$HOME/.config/hypr/wallpaper.png" -m fill &
    echo "  ✓ swaybg запущен"
fi
'''

        script = f'''#!/bin/bash
# Installer для rice конфига
# Сгенерировано rice-generator

set -e

echo "=== Rice Generator Installer ==="
echo ""

# Цвета для вывода
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# Проверка прав суперпользователя
if [ "$EUID" -eq 0 ]; then
    echo -e "${{RED}}Не запускайте скрипт от root!${{NC}}"
    exit 1
fi

# Директория со скриптом
SCRIPT_DIR="$( cd "$( dirname "${{BASH_SOURCE[0]}}" )" && pwd )"

# Бэкап текущих конфигов
BACKUP_DIR="$HOME/.config/rice_backups/backup_$(date +%Y%m%d_%H%M%S)"

echo -e "${{YELLOW}}[1/5] Создание бэкапа текущих конфигов...${{NC}}"
mkdir -p "$BACKUP_DIR"

# Бэкап Hyprland
if [ -d "$HOME/.config/hypr" ]; then
    cp -r "$HOME/.config/hypr" "$BACKUP_DIR/hypr"
    echo "  ✓ Hyprland конфиги сохранены"
fi

# Бэкап Waybar
if [ -d "$HOME/.config/waybar" ]; then
    cp -r "$HOME/.config/waybar" "$BACKUP_DIR/waybar"
    echo "  ✓ Waybar конфиги сохранены"
fi

# Бэкап Kitty
if [ -d "$HOME/.config/kitty" ]; then
    cp -r "$HOME/.config/kitty" "$BACKUP_DIR/kitty"
    echo "  ✓ Kitty конфиги сохранены"
fi

echo -e "${{GREEN}}Бэкап создан в: $BACKUP_DIR${{NC}}"
echo ""

# Установка новых конфигов
echo -e "${{YELLOW}}[2/5] Установка конфигов Hyprland...${{NC}}"
mkdir -p "$HOME/.config/hypr"
cp "$SCRIPT_DIR/hyprland.conf" "$HOME/.config/hypr/hyprland.conf"
echo "  ✓ Hyprland конфиг установлен"

echo -e "${{YELLOW}}[3/5] Установка конфигов Waybar...${{NC}}"
mkdir -p "$HOME/.config/waybar"
cp "$SCRIPT_DIR/waybar_config.json" "$HOME/.config/waybar/config"
cp "$SCRIPT_DIR/waybar_style.css" "$HOME/.config/waybar/style.css"
echo "  ✓ Waybar конфиги установлены"

echo -e "${{YELLOW}}[4/5] Установка конфигов Wofi...${{NC}}"
mkdir -p "$HOME/.config/wofi"
if [ -f "$SCRIPT_DIR/wofi_config" ]; then
    cp "$SCRIPT_DIR/wofi_config" "$HOME/.config/wofi/config"
fi
if [ -f "$SCRIPT_DIR/wofi_style.css" ]; then
    cp "$SCRIPT_DIR/wofi_style.css" "$HOME/.config/wofi/style.css"
fi
echo "  ✓ Wofi конфиги установлены"

echo -e "${{YELLOW}}[5/5] Установка конфигов Kitty...${{NC}}"
mkdir -p "$HOME/.config/kitty"
cp "$SCRIPT_DIR/kitty.conf" "$HOME/.config/kitty/kitty.conf"
echo "  ✓ Kitty конфиг установлен"

{wallpaper_install}

echo ""
echo -e "${{GREEN}}=== Установка завершена! ===${{NC}}"
echo ""
echo "Для отката изменений используйте:"
echo "  $BACKUP_DIR/restore.sh"
echo ""
echo "Или запустите uninstaller.sh из этой директории"
'''
        return self._save_file("installer.sh", script)

    def _generate_uninstaller(self) -> Path:
        """
        Генерирует скрипт uninstaller.sh.

        Returns:
            Путь к скрипту uninstaller.
        """
        script = '''#!/bin/bash
# Uninstaller для rice конфига
# Сгенерировано rice-generator

set -e

echo "=== Rice Generator Uninstaller ==="
echo ""

# Цвета для вывода
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
NC='\\033[0m' # No Color

# Директория со скриптом
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${YELLOW}Этот скрипт удалит установленные конфиги и восстановит оригинальные.${NC}"
echo ""
read -p "Продолжить? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Отмена."
    exit 0
fi

echo ""
echo -e "${YELLOW}[1/3] Удаление конфигов Hyprland...${NC}"
if [ -f "$HOME/.config/hypr/hyprland.conf" ]; then
    rm "$HOME/.config/hypr/hyprland.conf"
    echo "  ✓ hyprland.conf удалён"
fi

echo -e "${YELLOW}[2/4] Удаление конфигов Waybar...${NC}"
if [ -f "$HOME/.config/waybar/config" ]; then
    rm "$HOME/.config/waybar/config"
    echo "  ✓ waybar/config удалён"
fi
if [ -f "$HOME/.config/waybar/style.css" ]; then
    rm "$HOME/.config/waybar/style.css"
    echo "  ✓ waybar/style.css удалён"
fi

echo -e "${YELLOW}[3/4] Удаление конфигов Wofi...${NC}"
if [ -f "$HOME/.config/wofi/config" ]; then
    rm "$HOME/.config/wofi/config"
    echo "  ✓ wofi/config удалён"
fi
if [ -f "$HOME/.config/wofi/style.css" ]; then
    rm "$HOME/.config/wofi/style.css"
    echo "  ✓ wofi/style.css удалён"
fi

echo -e "${YELLOW}[4/4] Удаление конфигов Kitty...${NC}"
if [ -f "$HOME/.config/kitty/kitty.conf" ]; then
    rm "$HOME/.config/kitty/kitty.conf"
    echo "  ✓ kitty.conf удалён"
fi

echo ""
echo -e "${GREEN}Конфиги удалены!${NC}"
echo ""
echo -e "${YELLOW}Поиск доступных бэкапов...${NC}"

BACKUP_BASE="$HOME/.config/rice_backups"
if [ -d "$BACKUP_BASE" ]; then
    BACKUPS=($(ls -dt "$BACKUP_BASE"/backup_* 2>/dev/null))
    if [ ${#BACKUPS[@]} -gt 0 ]; then
        echo ""
        echo "Найдены следующие бэкапы:"
        for i in "${!BACKUPS[@]}"; do
            echo "  $((i+1))) ${BACKUPS[$i]}"
        done
        echo "  0) Не восстанавливать"
        echo ""
        read -p "Выберите бэкап для восстановления: " backup_choice

        if [ "$backup_choice" -gt 0 ] && [ "$backup_choice" -le "${#BACKUPS[@]}" ]; then
            SELECTED_BACKUP="${BACKUPS[$((backup_choice-1))]}"
            echo ""
            echo -e "${YELLOW}Восстановление из: $SELECTED_BACKUP${NC}"

            if [ -d "$SELECTED_BACKUP/hypr" ]; then
                mkdir -p "$HOME/.config/hypr"
                cp -r "$SELECTED_BACKUP/hypr"/* "$HOME/.config/hypr/"
                echo "  ✓ Hyprland восстановлен"
            fi

            if [ -d "$SELECTED_BACKUP/waybar" ]; then
                mkdir -p "$HOME/.config/waybar"
                cp -r "$SELECTED_BACKUP/waybar"/* "$HOME/.config/waybar/"
                echo "  ✓ Waybar восстановлен"
            fi

            if [ -d "$SELECTED_BACKUP/kitty" ]; then
                mkdir -p "$HOME/.config/kitty"
                cp -r "$SELECTED_BACKUP/kitty"/* "$HOME/.config/kitty/"
                echo "  ✓ Kitty восстановлен"
            fi

            # Перезапуск Waybar
            if pgrep -x "waybar" > /dev/null; then
                killall waybar
                sleep 1
            fi
            waybar &
            echo ""
            echo -e "${GREEN}Бэкап восстановлен!${NC}"
        else
            echo "Восстановление отменено."
        fi
    else
        echo "Бэкапы не найдены."
    fi
else
    echo "Директория с бэкапами не найдена."
fi

echo ""
echo -e "${GREEN}=== Uninstaller завершён! ===${NC}"
'''
        return self._save_file("uninstaller.sh", script)
