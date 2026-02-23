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

    def _load_storage(self, context_file: str) -> FileChatMessageHistory:
        """
        Загружает историю чата из файла.

        Parameters
        ----------
        context_file : str
            Путь к файлу истории чата

        Returns
        -------
        FileChatMessageHistory
            История чата с ограничением по сообщениям
        """
        try:
            context_path = Path(context_file)
            context_path.parent.mkdir(parents=True, exist_ok=True)
            history = FileChatMessageHistory(file_path=str(context_path))
            
            # Ограничиваем историю
            messages = history.messages
            if len(messages) > MAX_HISTORY_MESSAGES:
                history.replace_messages(messages[-MAX_HISTORY_MESSAGES:])
                
            return history
        except Exception as e:
            logger.error("Ошибка загрузки истории %s: %s", context_file, e)
            return FileChatMessageHistory(file_path=str(context_file))

    def save_messages(
        self, 
        context_file: str, 
        human_message: str, 
        ai_message: str
    ) -> None:
        """
        Сохраняет сообщения в историю чата.

        Parameters
        ----------
        context_file : str
            Путь к файлу истории
        human_message : str
            Сообщение пользователя
        ai_message : str
            Ответ AI
        """
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
        """
        Создает файл пожеланий если не существует.

        Parameters
        ----------
        file_path : Path
            Путь к файлу пожеланий

        Returns
        -------
        Path
            Путь к готовому файлу
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists():
            file_path.write_text("[]", encoding="utf-8")
        return file_path

    def add_user_wish(self, user_id: str, human_message: str, ai_message: str) -> None:
        """
        Добавляет пожелание пользователя.

        Parameters
        ----------
        user_id : str
            ID пользователя
        human_message : str
            Сообщение пользователя
        ai_message : str
            Ответ AI
        """
        try:
            wish_file = self._ensure_wish_file(
                self.base_path / "context" / user_id / "UserWish.json"
            )
            data = json.loads(wish_file.read_text(encoding="utf-8"))
            data.append(f"I: {human_message} AI: {ai_message}")
            wish_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=4),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error("Ошибка добавления пожелания %s: %s", user_id, e)

    def get_user_wishes(self, user_id: str) -> str:
        """
        Получает пожелания пользователя.

        Parameters
        ----------
        user_id : str
            ID пользователя

        Returns
        -------
        str
            Текст пожеланий или сообщение об отсутствии
        """
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
        """
        Добавляет глобальное пожелание администратора.

        Parameters
        ----------
        wish_message : str
            Текст пожелания
        """
        try:
            self._ensure_wish_file(self.global_wish_path)
            data = json.loads(self.global_wish_path.read_text(encoding="utf-8"))
            data.append(wish_message)
            self.global_wish_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=4),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error("Ошибка глобального пожелания: %s", e)

    def get_admin_wishes(self) -> str:
        """
        Получает глобальные пожелания.

        Returns
        -------
        str
            Текст пожеланий или пустая строка
        """
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
    """Основной класс AI бота с простой цепочкой."""
    
    def __init__(self):
        self.base_path = Path(USER_FILES_PATH)
        self.history_manager = ChatHistoryManager(self.base_path)
        self.wish_manager = WishManager(self.base_path)
        self.user_groups: dict[str, str] = {}
        self._model: ChatOllama | None = None

    def _get_model(self) -> ChatOllama:
        """
        Создает и возвращает модель Ollama.

        Returns
        -------
        ChatOllama
            Инициализированная модель
        """
        if self._model is None:
            self._model = ChatOllama(
                model=MODEL_NAME,
                temperature=0.1,
                top_p=0.7,
                repeat_penalty=1.1,
                timeout=60,
                gpu_layers=35
            )
        return self._model
    
    def ask(
        self, 
        prompt: str, 
        context_path: str, 
        userid: str, 
        file_context: List[str] | None = None
    ) -> str:
        """
        Универсальный метод обработки запросов с приоритетами:
        1. Расписание ТПУ → 2. Сохранение группы → 3. AI ответ
        
        Parameters
        ----------
        prompt : str
            Текст запроса пользователя ("расписание", "привет")
        context_path : str
            Путь к истории чата ("data/user_12.json")
        userid : str
            Telegram/веб ID пользователя
        file_context : List[str], optional
            Список прикрепленных файлов
        
        Returns
        -------
        str
            Готовый ответ для чата (HTML/Markdown)
        
        Raises
        ------
        Exception
            Критические ошибки Ollama/парсера
        """
        # 1. Guard clause: нормализация входных данных
        if file_context is None:
            file_context = []
        
        if not prompt.strip():
            logger.warning(f"Пустой запрос от {userid}")
            return "❓ Пожалуйста, напишите вопрос."
        
        # 2. ПРОВЕРКА РАСПИСАНИЯ (ПРИОРИТЕТ №1)
        schedule_response = self._handle_schedule_request(prompt, userid)
        if schedule_response:
            logger.info(f"✅ Расписание для {userid}: {schedule_response[:50]}")
            return schedule_response
        
        # 3. ПРОВЕРКА СОХРАНЕНИЯ ГРУППЫ (ПРИОРИТЕТ №2)
        group_saved = self._handle_group_save(prompt, userid)
        if group_saved:
            return group_saved
        
        # 4. AI ОТВЕТ (ПРИОРИТЕТ №3)
        try:
            ai_response = self._ai_response(prompt, context_path, userid, file_context)
            logger.info(f"🤖 AI ответ для {userid} ({len(ai_response)} символов)")
            return ai_response
            
        except Exception as e:
            logger.error(f"❌ AI ошибка для {userid}: {e}")
            return (
                "🤖 <b>AI временно недоступен</b>\n\n"
                "• Проверьте `ollama serve`\n"
                "• Скачайте `ollama pull mistral:7b`\n"
                "• Или спросите расписание: <code>расписание</code>"
            )

    def _ai_response(self, prompt: str, context_path: str, userid: str, file_context: List[str]) -> str:
        """Ollama без langchain."""
        try:
            group_info = f"Группа: {self.user_groups.get(userid, 'не указана')}"
            full_prompt = (
                f"🧠 AI-помощник ТПУ\n{group_info}\nФайлы: {', '.join(file_context[:2])}\n\n"
                f"Вопрос: {prompt}\n\nКРАТКО, русский, код в <code>"
            )
            
            response = ollama.chat(
                model='mistral:7b',
                messages=[{'role': 'user', 'content': full_prompt}]
            )
            return response['message']['content']
        except Exception as e:
            logger.error(f"Ollama: {e}")
            return "🤖 ollama serve + ollama pull mistral:7b"

    def _handle_group_save(self, prompt: str, userid: str) -> str | None:
        """
        Автоматическое сохранение группы из сообщения.
        
        Parameters
        ----------
        prompt : str
            Текст ("моя группа ИТ-21-1")
        userid : str
            ID пользователя
            
        Returns
        -------
        str | None
            Подтверждение сохранения или None
        """
        # Паттерны для извлечения группы
        patterns = [
            r'(?:группа|group)[:\s]*([А-Яа-яЁё0-9\-]{3,20})',
            r'гр(?:уппа)?[:\s]*([А-Яа-яЁё0-9\-]{3,20})',
            r'([А-ЯЁ][А-Яа-яё]{2,4}\-\d{2}\-\d)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                group_name = match.group(1).upper()
                self.user_groups[userid] = group_name
                
                logger.info(f"✅ Сохранена группа '{group_name}' для {userid}")
                return f"✅ <b>Группа {group_name} сохранена!</b>\n\nТеперь пишите <code>расписание</code>"
        
        return None

    def _handle_schedule_request(self, prompt: str, userid: str) -> str | None:
        """Расписание ТПУ - ПОЛНАЯ НЕДЕЛЯ."""
        schedule_keywords = {
            'расписание', 'расп', 'уроки', 'пары', 'schedule', 'завтра', 'сегодня'
        }
        
        if not any(kw in prompt.lower() for kw in schedule_keywords):
            return None
        
        group_id = self.user_groups.get(userid)
        if not group_id:
            return (
                "📚 <b>Укажите группу!</b>\n\n"
                "💡 <code>моя группа 415</code>\n"
                "📋 Группы: 415,425,435,445,455,314,324,334,344,354"
            )
        
        # ✅ ВЫВОДИМ ПОЛНОЕ РАСПИСАНИЕ НА НЕДЕЛЮ
        try:
            schedule_html = get_tpu_schedule(group_id)
            return f"📅 <b>Полное расписание {group_id}</b>\n\n{schedule_html}"
        except Exception as e:
            logger.error(f"Ошибка расписания {group_id}: {e}")
            return f"❌ Ошибка загрузки <b>{group_id}</b>"
    
    def set_user_group(self, userid: str, group_name: str) -> None:
        """Сохраняет группу пользователя."""
        self.user_groups[userid] = group_name.strip()
        logger.info(f"Группа {group_name} сохранена для {userid}")
    
    @staticmethod
    def _parse_group_from_message(message: str) -> str | None:
        """Извлекает название группы из сообщения."""
        group_pattern = r'(?:группа|group)[:\s]*([А-Яа-яЁё0-9\-]+)'
        match = re.search(group_pattern, message, re.IGNORECASE)
        return match.group(1) if match else None

    def _smart_history(
        self, 
        messages: List[Any], 
        max_pairs: int = 8
    ) -> List[Any]:
        """
        Обрезает историю до ключевых пар вопрос-ответ.

        Parameters
        ----------
        messages : List[Any]
            Полная история сообщений
        max_pairs : int, optional
            Максимум пар Q&A (по умолчанию 8)

        Returns
        -------
        List[Any]
            Оптимизированная история
        """
        # Берём только последние сообщения, попарно (вопрос+ответ)
        recent_pairs = []
        for i in range(0, len(messages), 2):
            if len(recent_pairs) >= max_pairs:
                break
            if i + 1 < len(messages):
                recent_pairs.extend(messages[i:i+2])
        
        # Финальный срез (не больше 10 сообщений)
        return recent_pairs[-10:]


    def _detect_role(self, prompt: str) -> str:
        """
        Определяет роль AI по ключевым словам.

        Parameters
        ----------
        prompt : str
            Текст запроса

        Returns
        -------
        str
            Роль AI ("программист", "DevOps", "помощник")
        """
        prompt_lower = prompt.lower()
        
        code_keywords = {"код", "python", "функция", "класс", "def", "pip"}
        devops_keywords = {"установи", "docker", "linux", "pacman", "systemctl"}
        
        if any(kw in prompt_lower for kw in code_keywords):
            return "эксперт Python 3.12 (SOLID, типизация, чистый код)"
        elif any(kw in prompt_lower for kw in devops_keywords):
            return "DevOps инженер Linux EndeavourOS"
        else:
            return "технический помощник программиста"


    def _build_system_prompt(
        self,
        role: str,
        user_id: str,
        file_context: List[str],
        user_wishes: str,
        admin_wishes: str,
        history_len: int
    ) -> str:
        """
        Создаёт структурированный системный промпт.

        Parameters
        ----------
        role : str
            Роль AI
        user_id : str
            ID пользователя
        file_context : List[str]
            Файлы контекста
        user_wishes : str
            Пожелания пользователя
        admin_wishes : str
            Глобальные пожелания
        history_len : int
            Количество сообщений в истории

        Returns
        -------
        str
            Готовый системный промпт
        """
        files_str = ", ".join(file_context[:3])
        if len(file_context) > 3:
            files_str += "..."
        
        system_parts = [
            f"🧠 Ты {role} для пользователя {user_id}",
            f"📁 Контекст файлов: {files_str}",
            f"💾 История: {history_len} сообщений",
            "🎯 Правила ответа:",
            "   • КРАТКО (3-5 предложений, макс 200 слов)",
            "   • ТОЧНО по запросу",
            "   • Русский язык",
        ]
        
        if user_wishes:
            system_parts.append(f"👤 Пожелания пользователя: {user_wishes}")
        if admin_wishes:
            system_parts.append(f"🌐 Глобальные правила: {admin_wishes}")
        
        return "\n".join(system_parts)
 
    def add_user_wish(self, user_id: str, human_message: str, ai_message: str) -> None:
        """Добавляет пожелание пользователя."""
        self.wish_manager.add_user_wish(user_id, human_message, ai_message)
    
    def add_admin_wish(self, wish_message: str) -> None:
        """Добавляет глобальное пожелание."""
        self.wish_manager.add_admin_wish(wish_message)
def get_tpu_schedule(group_id: str) -> str:
    """✅ ПОЛНЫЕ расписания всех групп ТПУ (415-455)."""
    group_id = group_id.upper().strip()
    
    # Читаем data/rasp.json
    json_path = Path('AiLab/data/rasp.json')
    if not json_path.exists():
        return "❌ <b>data/rasp.json</b> не найден"
    
    try:
        with json_path.open('r', encoding='utf-8') as f:
            schedules = json.load(f)
    except:
        return "❌ Ошибка чтения data/rasp.json"
    
    if group_id not in schedules:
        groups = sorted([g for g in schedules.keys() if isinstance(g, str)])
        return f"""
        ❌ <b>Группа {group_id}</b> не найдена!<br>
        💡 Доступно: <code>{', '.join(groups[:5])}</code>
        """
    
    # ✅ КРАСИВАЯ HTML ТАБЛИЦА
    html = f"""
    <div class="schedule-container">
        <div class="schedule-header">
            📅 <b>РАСПИСАНИЕ {group_id}</b> | 3 четверть 2025-2026
        </div>
    """
    
    for day, lessons in schedules[group_id].items():
        html += f"""
        <div class="schedule-day">
            <h3>🗓️ {day}</h3>
            <table class="schedule-table">
        """
        
        for lesson in lessons:
            lesson = lesson.strip()
            if not lesson or lesson in ["", "-", "—"]:
                # ПУСТАЯ ячейка
                html += """
                <tr>
                    <td class="lesson-time">—</td>
                    <td class="lesson-content">Окно</td>
                </tr>
                """
            else:
                try:
                    # ✅ ТВОЙ парсинг: "1. Предмет | кабинет"
                    num, content = lesson.split('. ', 1)
                    html += f"""
                    <tr>
                        <td class="lesson-time">{num}</td>
                        <td class="lesson-content">{content}</td>
                    </tr>
                    """
                except ValueError:
                    # Без номера
                    html += f"""
                    <tr>
                        <td class="lesson-time">—</td>
                        <td class="lesson-content">{lesson}</td>
                    </tr>
                    """
        
        html += "</table></div>"
    
    html += "</div>"
    return html
