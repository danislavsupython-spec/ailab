"""
🚀 НАСТОЯЩИЙ ODT парсер - ЧИТАЕТ ВСЕ дни + ВСЕ уроки
DEBUG логи + правильная логика таблиц
"""
import re
from pathlib import Path
from typing import Dict, List, Optional
from odf.opendocument import load
from odf.table import Table, TableRow, TableCell
from odf.text import P

class OdtScheduleParser:
    def __init__(self, odt_path: str = "data/rasp.odt"):
        self.odt_path = Path(odt_path)
        self.schedule: Dict[str, Dict[str, List[str]]] = {}
        self._parse_file()
    
    def _parse_file(self):
        """Парсит ВСЕ таблицы."""
        if not self.odt_path.exists():
            print(f"❌ Файл не найден: {self.odt_path}")
            self._create_demo_data()
            return
        
        print(f"✅ Парсим: {self.odt_path}")
        doc = load(self.odt_path)
        tables = doc.getElementsByType(Table)
        print(f"📊 Найдено таблиц: {len(tables)}")
        
        for table_idx, table in enumerate(tables):
            print(f"\n📋 Таблица {table_idx + 1}")
            self._parse_table(table)
        
        print(f"\n✅ ИТОГО групп: {len(self.schedule)}")
        self._debug_groups()
    
    def _parse_table(self, table: Table):
        """УМНЫЙ парсер таблиц расписания."""
        rows = table.getElementsByType(TableRow)
        current_group = None
        current_day = None
        
        for row_idx, row in enumerate(rows):
            cells = row.getElementsByType(TableCell)
            if len(cells) < 2:
                continue
            
            cell_texts = [self._extract_text(cell) for cell in cells]
            row_text = ' | '.join([t for t in cell_texts if t.strip()])
            
            # 🎯 1. ГРУППЫ (415, 425, 435...)
            group_match = re.search(r'(\d{3}[АБ]?)', row_text)
            if group_match and len(group_match.group(1)) >= 3:
                current_group = group_match.group(1)
                if current_group not in self.schedule:
                    self.schedule[current_group] = {}
                print(f"  ✅ ГРУППА: {current_group}")
                continue
            
            # 🎯 2. ДНИ НЕДЕЛИ
            day_match = re.search(r'(Понедельник|Вторник|Среда|Четверг|Пятница|Суббота)', row_text)
            if day_match and current_group:
                current_day = day_match.group(1)
                if current_day not in self.schedule[current_group]:
                    self.schedule[current_group][current_day] = []
                print(f"  📅 ДЕНЬ: {current_day}")
                continue
            
            # 🎯 3. УРОКИ (1, 2, 3... | предмет | кабинет)
            if (current_group and current_day and len(cell_texts) >= 2 and 
                re.match(r'^\d+$', cell_texts[0].strip())):
                
                lesson_num = cell_texts[0].strip()
                lesson_parts = [t.strip() for t in cell_texts[1:] if t.strip()]
                lesson_text = ' | '.join(lesson_parts[:3])  # Предмет | учитель | кабинет
                
                if lesson_text:
                    self.schedule[current_group][current_day].append(f"{lesson_num}. {lesson_text}")
                    print(f"    📚 {lesson_num}. {lesson_text}")
    
    def _extract_text(self, cell: TableCell) -> str:
        """Извлекает текст из ячейки."""
        if not cell.childNodes:
            return ""
        texts = []
        for node in cell.childNodes:
            if hasattr(node, 'getTextContent'):
                text = node.getTextContent().strip()
                if text:
                    texts.append(text)
        return ' '.join(texts)
    
    def _create_demo_data(self):
        """Демо данные если нет файла."""
        self.schedule = {
            "415": {
                "Понедельник": ["1. Разговоры о важном | 317", "2. Индивидуальный проект | 317"],
                "Вторник": ["1. Геометрия | 317", "2. Геометрия | 317"]
            }
        }
    
    def _debug_groups(self):
        """DEBUG вывод."""
        for group in sorted(self.schedule.keys()):
            days = list(self.schedule[group].keys())
            lessons_count = sum(len(lessons) for lessons in self.schedule[group].values())
            print(f"  📋 {group}: {len(days)} дней, {lessons_count} уроков")
    
    def get_schedule(self, group: str, day: str = None) -> str:
        """✅ ПОЛНОЕ расписание."""
        group = group.upper().strip()
        
        if group not in self.schedule:
            groups = sorted(self.schedule.keys())
            return f"❌ Группа <b>{group}</b> не найдена!\n💡 <code>{', '.join(groups)}</code>"
        
        if day and day in self.schedule[group]:
            lessons = self.schedule[group][day]
            return f"<b>{day} ({group})</b>\n" + '\n'.join(f"  {l}" for l in lessons)
        
        # ✅ ВСЕ ДНИ
        result = f"<b>📅 {group} - Полная неделя</b>\n\n"
        for day_name, lessons in self.schedule[group].items():
            result += f"🗓️ <b>{day_name}</b>\n"
            for lesson in lessons:
                result += f"  {lesson}\n"
            result += "\n"
        return result
    
    def available_groups(self) -> List[str]:
        return sorted(self.schedule.keys())

