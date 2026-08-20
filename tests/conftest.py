from __future__ import annotations

import pytest


@pytest.fixture
def rich_spec() -> dict:
    return {
        "metadata": {
            "title": "Операционный обзор",
            "subject": "Тест вертикального среза DOCX",
            "author": "Document System",
            "keywords": "docx, qa, test",
        },
        "language": "ru-RU",
        "page": {
            "size": "A4",
            "orientation": "portrait",
            "margin_top_mm": 20,
            "margin_right_mm": 19,
            "margin_bottom_mm": 20,
            "margin_left_mm": 22,
        },
        "theme": {
            "primary": "23465C",
            "secondary": "3D6B78",
            "accent": "C47A35",
            "text": "26343D",
            "muted": "687983",
            "light": "EDF3F5",
            "font": "DejaVu Sans",
            "heading_font": "DejaVu Sans",
        },
        "cover": {
            "eyebrow": "Внутренний отчёт",
            "title": "Операционный обзор",
            "subtitle": "Результаты и план улучшений",
            "organization": "Рабочая группа",
            "date": "20 августа 2026",
            "confidentiality": "Для внутреннего использования",
        },
        "header": {"left": "Операционный обзор", "right": "2026"},
        "footer": {"left": "Рабочая группа", "page_numbers": True, "page_number_label": "Страница "},
        "toc": {"title": "Содержание", "min_level": 1, "max_level": 3},
        "content": [
            {"type": "heading", "level": 1, "text": "Резюме"},
            {
                "type": "paragraph",
                "runs": [
                    {"text": "Главный вывод: ", "bold": True},
                    {"text": "цикл обработки сократился на 18%.", "color": "227447"},
                ],
                "align": "justify",
            },
            {
                "type": "callout",
                "runs": [
                    {"text": "Решение: ", "bold": True},
                    {"text": "масштабировать новый процесс на две команды."},
                ],
            },
            {"type": "heading", "level": 2, "text": "Ключевые показатели"},
            {
                "type": "table",
                "headers": ["Показатель", "Факт", "Цель"],
                "widths_pct": [50, 25, 25],
                "rows": [
                    ["Цикл обработки", "8 дней", {"text": "5 дней", "bold": True, "color": "227447"}],
                    ["Дефекты", 14, 5],
                    ["Удовлетворённость", "78%", "90%"],
                ],
                "caption": "Таблица 1. Ключевые показатели",
                "zebra": True,
            },
            {
                "type": "chart",
                "kind": "bar",
                "title": "Динамика по кварталам",
                "labels": ["I кв.", "II кв.", "III кв.", "IV кв."],
                "series": [
                    {"name": "Факт", "values": [12, 15, 18, 21]},
                    {"name": "План", "values": [13, 16, 19, 23]},
                ],
                "y_label": "млн ₽",
                "caption": "Рисунок 1. Поквартальная динамика",
            },
            {"type": "heading", "level": 1, "text": "План действий"},
            {
                "type": "numbered",
                "items": [
                    "Назначить владельцев показателей.",
                    "Включить еженедельный контроль качества.",
                    {"text": "Проверить результат через 30 дней.", "level": 1},
                ],
            },
            {
                "type": "paragraph",
                "runs": [
                    {"text": "Дополнительная информация: "},
                    {"text": "example.com", "link": "https://example.com"},
                ],
            },
        ],
    }
