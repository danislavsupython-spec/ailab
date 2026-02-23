import json
import os
from datetime import datetime
from langchain_core.prompts import PromptTemplate

# from langchain_core.chat_message_histories import InMemoryChatMessageHistory
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_ollama import OllamaLLM
from app.AI.Tools import AITools
from pathlib import Path
from langchain_classic.agents import create_react_agent, AgentExecutor
from typing import List
from app.base.config import USER_FILES_PATH


class AI_BOT_V3:
    def __init__(self):
        self.base_path = Path(USER_FILES_PATH)
        self.global_wish_path = self.base_path / "context" / "admin_wish.json"
        self.tools = AITools().get_all_tools()
        self.tools_name = AITools().get_all_tools_name()

    def _load_storage(self, context_file: str) -> FileChatMessageHistory:
        """
        Загружает историю чата из файла и возвращает объект FileChatMessageHistory.

        Args:
            context_file (str): Путь к файлу с историей чата.

        Returns:
            FileChatMessageHistory: Объект памяти с историей чата.

        Raises:
            Exception: Если произошла ошибка при загрузке файла.
        """
        try:
            # Создаем директорию для файла, если она не существует
            context_path = Path(context_file)
            context_path.parent.mkdir(parents=True, exist_ok=True)

            # Инициализируем историю чата
            chat_memory = FileChatMessageHistory(file_path=str(context_path))

            # Создаем объект памяти
            return chat_memory
        except Exception as e:
            print(f"Ошибка при загрузке истории чата из {context_file}: {e}")
            # Возвращаем пустую память в случае ошибки
            return chat_memory

    def _save_storage(
        self, context_file: str, human_message: str, ai_message: str = ""
    ) -> None:
        """
        Сохраняет сообщения пользователя и AI в историю чата.

        Args:
            context_file (str): Путь к файлу с историей чата.
            human_message (str): Сообщение пользователя.
            ai_message (str): Ответ AI (опционально).

        Raises:
            Exception: Если произошла ошибка при сохранении файла.
        """
        try:
            # Создаем директорию для файла, если она не существует
            context_path = Path(context_file)
            context_path.parent.mkdir(parents=True, exist_ok=True)

            # Инициализируем историю чата
            chat_memory = FileChatMessageHistory(file_path=str(context_path))

            # Форматируем временную метку
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Добавляем сообщение пользователя
            if human_message:
                chat_memory.add_user_message(f"[{timestamp}] {human_message}")

            # Добавляем ответ AI, если он есть
            if ai_message:
                chat_memory.add_ai_message(f"[{timestamp}] {ai_message}")

        except Exception as e:
            print(f"Ошибка при сохранении истории чата в {context_file}: {e}")

    # Wish User and Admin---------------------------------------------------------------------------------------------->
    def _ensure_user_wish_file(self, user_id: str) -> Path:
        user_dir = self.base_path / "context" / user_id
        user_dir.mkdir(exist_ok=True)
        wish_file = user_dir / "UserWish.json"

        if not wish_file.exists():
            with wish_file.open("w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=4)

        return wish_file

    def add_wish(
        self, user_id: str = "0", human_message: str = "", ai_message: str = ""
    ) -> None:
        try:
            wish_file = self._ensure_user_wish_file(user_id)

            # Чтение существующих пожеланий
            with wish_file.open("r", encoding="utf-8") as f:
                data: List[str] = json.load(f)

            # Добавление нового пожелания
            data.append(f"I: {human_message} AI: {ai_message}")

            # Сохранение обновлённых пожеланий
            with wish_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

        except Exception as e:
            print(f"Ошибка при добавлении пожелания для пользователя {user_id}: {e}")

    def _load_wish(self, user_id: str) -> str:
        try:
            wish_file = self._ensure_user_wish_file(user_id)

            with wish_file.open("r", encoding="utf-8") as f:
                data: List[str] = json.load(f)

            if not data:
                return "Пожелания пользователя отсутствуют."

            return f"Советы по общению (учитывай, но не упоминай): {data}"

        except Exception as e:
            print(f"Ошибка при загрузке пожеланий для пользователя {user_id}: {e}")
            return "Ошибка при загрузке пожеланий."

    def add_admin_wish(self, wish_message: str) -> None:
        try:
            # Читаем существующие пожелания
            with open(self.global_wish_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            # Добавляем новое пожелание
            data.append(wish_message)

            # Сохраняем обновлённые пожелания
            with open(self.global_wish_path, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)

        except Exception as e:
            print(f"Ошибка при добавлении глобального пожелания: {e}")

    def _load_admin_wishes(self) -> str:
        try:
            # Создаём файл, если он не существует
            if not os.path.exists(self.global_wish_path):
                with open(self.global_wish_path, "w", encoding="utf-8") as file:
                    json.dump([], file, ensure_ascii=False, indent=4)

            with open(self.global_wish_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                if not data:
                    return "Глобальные пожелания отсутствуют."
                return (
                    f"Глобальные советы по общению (учитывай, но не упоминай): {data}"
                )
        except Exception as e:
            print(f"Ошибка при загрузке глобальных пожеланий: {e}")
            return "Ошибка при загрузке глобальных пожеланий."

    def ask(
        self, prompt: str, context_path: str, userid: str, file_context: list = []
    ) -> str:
        user_prompt = f"Вопрос: {prompt}, Используемые файлы: {str(file_context)}"
        result = {"output": ""}
        print(user_prompt)
        try:
            # Load user and admin wishes
            admin_wishes = self._load_admin_wishes()

            # Initialize model
            model = OllamaLLM(
                model="ministral-3:3b",
                temperature=0.1,
                tfs_z=0.95,  # Tail free sampling
                typical_p=0.95,  # Typical sampling
                repeat_penalty=1.1,  # Penalty за повторения
                top_p=0.7,
                frequency_penalty=0.3,
                timeout=60,
                # gpu_layers=40  # Количество слоёв для выгрузки на GPU (максимально возможное)
            )

            history = self._load_storage(context_path)
            react_prompt = PromptTemplate.from_template(
                """You are an AI assistant who processes requests: from writing code to finding information. Available tools:

                {tools}

                ### Instructions:
                - Read the request and decide if a tool is needed or if you can respond directly.
                - For code, use 'Work with code'. For photos, use 'Analyze photos' or 'Generate photos'.
                - If the request is simple or does not require tools, specify Action: None and give an answer.
                - If the tool returned an error or the result is sufficient, finish with Final Answer. Do not repeat actions unless necessary.
                - Maximum 1 tool call for simple requests to avoid loops.
                - Consider chat history, admin and user wishes, files if specified.
                - Always respond in the format: Thought, Action, Action Input, Observation, Final Answer.
                - Write only on Russian language, or user language
                """
                + f"""
                        """
                + """
                        ### Response Format:
                        Thought: [Request Analysis and Action Selection]
                        Action: [One of {tool_names} or "None"]
                        Action Input: [Tool Data or Empty]
                        Observation: [Tool Result or Empty]
                        Final Answer: [User Response]

                        """
                + """### Query:
                        {input}
                        Thought: {agent_scratchpad}
                        """
            )

            # Create agent
            agent = create_react_agent(model, self.tools, react_prompt)

            # Create agent executor
            agent_executor = AgentExecutor(
                agent=agent,
                # memory=history,
                tools=self.tools,
                verbose=True,
                handle_parsing_errors=True,  # Fixed typo: Fasle -> True
                max_iterations=20,
                max_execution_time=3000,
                tool_exception_handler=lambda e: f"Ошибка инструмента: {str(e)}",
                # memory_key="history",
            )

            # Выполняем запрос агента
            result = agent_executor.invoke({"input": prompt})
        except Exception as e:
            print(str(e))
            print(result["output"])

        # self._save_storage(
        #     context_file=context_path,
        #     human_message=user_prompt,
        #     ai_message=result["output"],
        # )
        del model
        print(result["output"])
        return result["output"]

