"""
Парсер ODT расписания → JSON/SQLite для бота
Поддержка: 415,425,435,445,455,314,324,334,344,354 группы
"""
import re
import json
from typing import Dict, List
from pathlib import Path
from odf.opendocument import load
from odf.table import Table, TableRow, TableCell
from odf.text import P

class OdtScheduleParser:
    """Парсит Raspisanie-3-chetvert.odt."""
    
    def __init__(self, odt_path: str = "data/Raspisanie-3-chetvert.odt"):
        self.odt_path = Path(odt_path)
        self.schedule: Dict[str, Dict[str, List[str]]] = {}  # {группа: {день: [уроки]}}
        self._parse()
    
    def _parse(self):
        """Парсит ODT файл."""
        if not self.odt_path.exists():
            self._create_dummy()
            return
        
        doc = load(self.odt_path)
        tables = doc.getElementsByType(Table)
        
        for table in tables:
            self._parse_table(table)
    
    def _parse_table(self, table: Table):
        """Парсит таблицу расписания."""
        rows = table.getElementsByType(TableRow)
        current_group = None
        current_day = None
        
        for row in rows:
            cells = row.getElementsByType(TableCell)
            cell_texts = [self._get_cell_text(cell) for cell in cells]
            
            # Группа (415,425,435...)
            if re.match(r'\d{3}[АБ]?', ' '.join(cell_texts)):
                current_group = cell_texts[0].strip()
                self.schedule[current_group] = {}
                continue
            
            # День недели
            day_match = re.search(r'(Понедельник|Вторник|Среда|Четверг|Пятница|Суббота)', ' '.join(cell_texts))
            if day_match:
                current_day = day_match.group(1)
                continue
            
            # Уроки (номер | предмет | учитель | кабинет)
            if current_group and current_day and len(cell_texts) >= 3:
                lesson_num = cell_texts[0].strip()
                if lesson_num.isdigit():
                    lesson = f"{lesson_num}. {' | '.join(cell_texts[1:])}".strip()
                    if current_day not in self.schedule[current_group]:
                        self.schedule[current_group][current_day] = []
                    self.schedule[current_group][current_day].append(lesson)
    
    def _get_cell_text(self, cell: TableCell) -> str:
        """Извлекает текст из ячейки."""
        text_parts = []
        for paragraph in cell.getElementsByType(P):
            text_parts.append(paragraph.getTextContent())
        return ' '.join(text_parts).strip()
    
    def _create_dummy(self):
        """Создает заглушку если нет файла."""
        self.schedule = {
            "415": {"Понедельник": ["1. Разговоры о важном 317", "2. Индивидуальный проект 317"]},
            "425": {"Понедельник": ["1. Разговоры о важном 301", "2. Физика 301"]},
            # ... остальные группы
        }
    
    def get_schedule(self, group: str, day: str = None) -> str:
        """
        Получает расписание группы.
        
        Parameters
        ----------
        group : str
            "415", "425", "435"
        day : str, optional
            "Понедельник"
            
        Returns
        -------
        str
            HTML для чата
        """
        group = group.upper()
        if group not in self.schedule:
            return f"❌ Группа <b>{group}</b> не найдена!\n💡 Доступно: {list(self.schedule.keys())}"
        
        if day and day in self.schedule[group]:
            lessons = self.schedule[group][day]
            return f"<b>{day} ({group})</b>\n" + "<br>".join(lessons)
        
        # Все дни
        html = f"<b>📅 {group}</b>\n\n"
        for day_name, lessons in self.schedule[group].items():
            html += f"<b>{day_name}</b>\n" + "<br>".join(lessons) + "\n\n"
        return html
    
    def save_json(self, json_path: str = "data/schedule.json"):
        """Сохраняет в JSON."""
        Path(json_path).parent.mkdir(exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self.schedule, f, ensure_ascii=False, indent=2)
    
    def available_groups(self) -> List[str]:
        """Список групп."""
        return sorted(self.schedule.keys())

# Глобальный парсер
SCHEDULE_PARSER = OdtScheduleParser()
