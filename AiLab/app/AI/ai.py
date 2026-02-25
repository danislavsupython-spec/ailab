from datetime import datetime
from pathlib import Path
from typing import List, Any
import json
import logging
import ollama
from langchain_ollama import ChatOllama
from langchain_community.chat_message_histories import FileChatMessageHistory
from app.base.config import USER_FILES_PATH
import re

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 10
MODEL_NAME = "mistral:7b"


class ChatHistoryManager:
    """Управляет историей чата с сохранением в файл."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self._smart_history = None

    def _load_storage(self, context_file: str) -> FileChatMessageHistory:
        try:
            context_path = Path(context_file)
            context_path.parent.mkdir(parents=True, exist_ok=True)
            history = FileChatMessageHistory(file_path=str(context_path))

            messages = history.messages
            if len(messages) > MAX_HISTORY_MESSAGES:
                history.replace_messages(messages[-MAX_HISTORY_MESSAGES:])

            return history
        except Exception as e:
            logger.error("Ошибка загрузки истории %s: %s", context_file, e)
            return FileChatMessageHistory(file_path=str(context_file))

    def save_messages(
        self, context_file: str, human_message: str, ai_message: str
    ) -> None:
        try:
            history = self._load_storage(context_file)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            history.add_user_message(f"[{timestamp}] {human_message}")
            if ai_message:
                history.add_ai_message(f"[{timestamp}] {ai_message}")
        except Exception as e:
            logger.error("Ошибка сохранения в %s: %s", context_file, e)


class WishManager:
    """Управляет пожеланиями пользователей и администраторов."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.global_wish_path = base_path / "context" / "admin_wish.json"

    def _ensure_wish_file(self, file_path: Path) -> Path:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists():
            file_path.write_text("[]", encoding="utf-8")
        return file_path

    def add_user_wish(self, user_id: str, human_message: str, ai_message: str) -> None:
        try:
            wish_file = self._ensure_wish_file(
                self.base_path / "context" / user_id / "UserWish.json"
            )
            data = json.loads(wish_file.read_text(encoding="utf-8"))
            data.append(f"I: {human_message} AI: {ai_message}")
            wish_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8"
            )
        except Exception as e:
            logger.error("Ошибка добавления пожелания %s: %s", user_id, e)

    def get_user_wishes(self, user_id: str) -> str:
        try:
            wish_file = self._ensure_wish_file(
                self.base_path / "context" / user_id / "UserWish.json"
            )
            data = json.loads(wish_file.read_text(encoding="utf-8"))
            if not data:
                return ""
            return f"Советы пользователя (не упоминай): {'; '.join(data)}"
        except Exception as e:
            logger.error("Ошибка загрузки пожеланий %s: %s", user_id, e)
            return ""

    def add_admin_wish(self, wish_message: str) -> None:
        try:
            self._ensure_wish_file(self.global_wish_path)
            data = json.loads(self.global_wish_path.read_text(encoding="utf-8"))
            data.append(wish_message)
            self.global_wish_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8"
            )
        except Exception as e:
            logger.error("Ошибка глобального пожелания: %s", e)

    def get_admin_wishes(self) -> str:
        try:
            if not self.global_wish_path.exists():
                return ""
            data = json.loads(self.global_wish_path.read_text(encoding="utf-8"))
            if not data:
                return ""
            return f"Глобальные советы (не упоминай): {'; '.join(data)}"
        except Exception as e:
            logger.error("Ошибка глобальных пожеланий: %s", e)
            return ""


class AI_BOT_V3:
    """AIД Ассистент ТПУ/ЛТПУ - помощник по всем предметам лицея."""

    def __init__(self):
        self.base_path = Path(USER_FILES_PATH)
        self.history_manager = ChatHistoryManager(self.base_path)
        self.wish_manager = WishManager(self.base_path)
        self.user_groups: dict[str, str] = {}
        self._model: ChatOllama | None = None

    def _get_model(self) -> ChatOllama:
        if self._model is None:
            self._model = ChatOllama(
                model=MODEL_NAME,
                temperature=0.1,
                top_p=0.7,
                repeat_penalty=1.1,
                timeout=60,
                gpu_layers=35,
            )
        return self._model

    def ask(
        self,
        prompt: str,
        context_path: str,
        userid: str,
        file_context: List[str] | None = None,
    ) -> str:
        if file_context is None:
            file_context = []

        if not prompt.strip():
            logger.warning(f"Пустой запрос от {userid}")
            return "❓ Пожалуйста, напишите вопрос."

        # 1. РАСПИСАНИЕ ТПУ/ЛТПУ (ПРИОРИТЕТ №1)
        schedule_response = self._handle_schedule_request(prompt, userid)
        if schedule_response:
            logger.info(f"✅ Расписание для {userid}: {schedule_response[:50]}")

        # 2. СОХРАНЕНИЕ ГРУППЫ ЛТПУ (ПРИОРИТЕТ №2)
        group_saved = self._handle_group_save(prompt, userid)
        if group_saved:
            return group_saved

        # 3. AI АСИСТЕНТ ТПУ/ЛТПУ (ПРИОРИТЕТ №3)
        try:
            ai_response = self._ai_response(
                prompt, userid, schedule_response=schedule_response
            )
            logger.info(
                f"🤖 AIД Ассистент ТПУ для {userid} ({len(ai_response)} символов)"
            )
            return ai_response

        except Exception as e:
            logger.error(f"❌ AI ошибка для {userid}: {e}")
            return (
                "<b>🤖 AIД Ассистент ТПУ временно недоступен</b>\n\n"
                "• Проверьте `ollama serve`\n"
                "• Скачайте `ollama pull mistral:7b`\n"
                "• Спросите расписание: <code>расписание</code>"
            )

    def _ai_response(self, prompt: str, userid: str, schedule_response=None) -> str:
        """AIД Ассистент ТПУ/ЛТПУ - универсальная помощь по урокам."""
        try:
            # Определяем роль по предмету
            role = self._detect_role(prompt)

            # Инфо о группе и файлах
            group_info = f"Группа ЛТПУ: {self.user_groups.get(userid, 'не указана')}"

            # ✅ ОСНОВНОЙ ПРОМПТ AIД АСИСТЕНТА ТПУ/ЛТПУ
            full_prompt = f"""
 <b>AIД АСИСТЕНТ ТПУ | Лицей при ТПУ (ЛТПУ)</b>

 <b>Ты ассистент учащихся ЛТПУ по ВСЕМ предметам:</b>
• Математика, Физика, Информатика, Русский, Английский
• Химия, Биология, История, Обществознание, География
• Все профильные предметы лицея

{group_info}
{f"Рассписание ученика на неделю: {schedule_response}" if schedule_response else None}

<b>РОЛЬ:</b> {role}

<b>ВОПРОС ЛИЦЕИСТА:</b> {prompt}

---

🎯 <b>ПРАВИЛА ОТВЕТА:</b>
1. КРАТКО (3-5 предложений)
2. ПО-ШКОЛЬНОМУ (просто, понятно)
3. РУССКИЙ язык
4. Формулы в LaTeX: $x^2$
5. Код в <code>
6. Задачи → решение + объяснение
7. Если сложно → разбей на шаги

<b>Ответь как учитель ЛТПУ:</b>
"""

            response = ollama.chat(
                model="mistral:7b", messages=[{"role": "user", "content": full_prompt}]
            )
            return response["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama: {e}")
            return "🤖 Запусти: ollama serve && ollama pull mistral:7b"

    def _detect_role(self, prompt: str) -> str:
        """Определяет роль AIД Ассистента по предмету."""
        prompt_lower = prompt.lower()

        # 🧮 МАТЕМАТИКА
        math_keywords = {
            "математика",
            "уравнение",
            "функция",
            "производная",
            "интеграл",
            "геометрия",
            "тригонометрия",
            "алгебра",
            "угол",
            "круг",
            "площадь",
            "объем",
            "матрица",
        }

        # ⚛️ ФИЗИКА
        physics_keywords = {
            "физика",
            "сила",
            "ускорение",
            "скорость",
            "энергия",
            "импульс",
            "закон",
            "ньютон",
            "ом",
            "волна",
        }

        # 💻 ИНФОРМАТИКА
        code_keywords = {
            "код",
            "python",
            "алгоритм",
            "цикл",
            "массив",
            "функция",
            "класс",
            "переменная",
            "if",
            "for",
        }

        # 📖 ЯЗЫКИ
        lang_keywords = {
            "английский",
            "переведи",
            "русский",
            "грамматика",
            "слово",
            "предложение",
            "глагол",
            "существительное",
        }

        # 🧪 НАУКИ
        science_keywords = {
            "химия",
            "биология",
            "атом",
            "молекула",
            "клетка",
            "организм",
            "реакция",
            "элемент",
            "таблица менделеева",
        }

        # 📖 ГУМАНИТАРНЫЕ
        humanities_keywords = {
            "история",
            "обществознание",
            "география",
            "война",
            "дата",
            "страна",
            "конституция",
        }

        if any(kw in prompt_lower for kw in math_keywords):
            return "УЧИТЕЛЬ МАТЕМАТИКИ ЛТПУ (алгебра, геометрия, анализ)"
        elif any(kw in prompt_lower for kw in physics_keywords):
            return "УЧИТЕЛЬ ФИЗИКИ ЛТПУ (механика, электричество, оптика)"
        elif any(kw in prompt_lower for kw in code_keywords):
            return "УЧИТЕЛЬ ИНФОРМАТИКИ ЛТПУ (Python, алгоритмы)"
        elif any(kw in prompt_lower for kw in lang_keywords):
            return "УЧИТЕЛЬ АНГЛИЙСКОГО/РУССКОГО ЛТПУ"
        elif any(kw in prompt_lower for kw in science_keywords):
            return "УЧИТЕЛЬ ХИМИИ/БИОЛОГИИ ЛТПУ"
        elif any(kw in prompt_lower for kw in humanities_keywords):
            return "УЧИТЕЛЬ ИСТОРИИ/ОБЩЕСТВОЗНАНИЯ ЛТПУ"
        else:
            return "УНИВЕРСАЛЬНЫЙ АСИСТЕНТ ЛТПУ (все предметы лицея)"

    def _handle_group_save(self, prompt: str, userid: str) -> str | None:
        """Сохранение группы ЛТПУ (415, 425, ИТ-21-1 и т.д.)."""
        patterns = [
            r"(?:группа|group|гр|лтпу)[:\s]*([А-Яа-яЁё0-9\-]{3,20})",
            r"гр(?:уппа)?[:\s]*([А-Яа-яЁё0-9\-]{3,20})",
            r"([А-ЯЁ][А-Яа-яё]{2,4}\-\d{2}\-\d)",
            r"(?:лтпу|лицей)[:\s]*([А-Яа-яЁё0-9\-]{3,20})",
        ]

        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                group_name = match.group(1).upper()
                self.user_groups[userid] = group_name

                logger.info(f"✅ Сохранена группа ЛТПУ '{group_name}' для {userid}")
                return f"✅ <b>Группа ЛТПУ {group_name} сохранена!</b>\n\n📅 Теперь: <code>расписание</code>\n🎓 Или спрашивай по предметам!"

        return None

    def _handle_schedule_request(self, prompt: str, userid: str) -> str | None:
        """Расписание ЛТПУ/ТПУ."""
        schedule_keywords = {
            "расписание",
            "расп",
            "уроки",
            "пары",
            "schedule",
            "завтра",
            "сегодня",
            "лтпу",
            "лицей",
        }

        if not any(kw in prompt.lower() for kw in schedule_keywords):
            return None

        group_id = self.user_groups.get(userid)
        if not group_id:
            return (
                "📚 <b>Укажите группу!</b>\n\n"
                "💡 <code>моя группа 415</code>\n"
                "📋 Группы: 415-А, 415-А, 425-А, 425-Б, 435-А, 435-Б, 445-А, 445-Б, 455-А, 455-Б, 324-А, 324-Б, 334-А, 334-Б, 344-А, 344-Б, 355-А, 355-Б"
            )

        try:
            schedule_html = get_tpu_schedule(group_id)
            return f"📅 <b>Расписание ученика ЛТПУ:</b>\n\n{schedule_html}"
        except Exception as e:
            logger.error(f"Ошибка расписания {group_id}: {e}")
            return False

    # Остальные методы без изменений...
    def set_user_group(self, userid: str, group_name: str) -> None:
        self.user_groups[userid] = group_name.strip()
        logger.info(f"Группа {group_name} сохранена для {userid}")

    def add_user_wish(self, user_id: str, human_message: str, ai_message: str) -> None:
        self.wish_manager.add_user_wish(user_id, human_message, ai_message)

    def add_admin_wish(self, wish_message: str) -> None:
        self.wish_manager.add_admin_wish(wish_message)


def get_tpu_schedule(group_id: str) -> str:
    """Расписания ЛТПУ/ТПУ в чистом текстовом формате."""
    group_id = group_id.upper().strip()

    json_path = Path("AiLab/data/rasp.json")
    if not json_path.exists():
        return "❌ AiLab/data/rasp.json не найден"

    try:
        with json_path.open("r", encoding="utf-8") as f:
            schedules = json.load(f)
    except Exception as e:  # Явный except вместо голого
        return f"❌ Ошибка чтения rasp.json: {e}"

    if group_id not in schedules:
        groups = sorted([g for g in schedules.keys() if isinstance(g, str)])
        return (
            f"❌ Группа ЛТПУ {group_id} не найдена!\n"
            f"💡 Доступно: {', '.join(groups[:8])}"
        )

    result = []

    for day, lessons in schedules[group_id].items():
        result.append(f"🗓️ {day}")
        result.append("-" * 40)

        for lesson in lessons:
            lesson = lesson.strip()
            if not lesson or lesson in ["", "-", "—"]:
                result.append("🆓 Окно")
            else:
                try:
                    num, content = lesson.split(". ", 1)
                    result.append(f"{num}. {content}")
                except ValueError:
                    result.append(lesson)

        result.append("")  # Пустая строка между днями

    return "\n".join(result)
