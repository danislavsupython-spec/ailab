import json
import os
from typing import Dict

from langchain_ollama import OllamaLLM
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    TextLoader,
    UnstructuredFileLoader,
    UnstructuredRTFLoader,
    UnstructuredExcelLoader,
    UnstructuredPowerPointLoader,
    CSVLoader,
    UnstructuredHTMLLoader,
    UnstructuredEPubLoader,
    UnstructuredMarkdownLoader,
    UnstructuredEmailLoader,
)
from langchain_classic.chains import LLMChain
from langchain_core.prompts import PromptTemplate
from diffusers import StableDiffusionXLPipeline
from ollama import Client
from PIL import Image
import base64
import io
import torch
from googlesearch import search
from pydantic import BaseModel
from pydantic.v1 import root_validator


class CurrencyConverter:
    def __init__(self):
        pass

    def load_file(self, file_path: str) -> str:
        # Загружает содержимое файла в зависимости от его формата
        try:
            if not os.path.exists(file_path):
                return "Ошибка: Файл не найден"

            file_path = file_path.strip().lower()

            if file_path.endswith(".pdf"):
                loader = PyPDFLoader(file_path)
            elif file_path.endswith(".docx") or file_path.endswith(".doc"):
                loader = Docx2txtLoader(file_path)
            elif file_path.endswith(".txt"):
                loader = TextLoader(file_path)
            elif file_path.endswith(".rtf"):
                loader = UnstructuredRTFLoader(file_path)
            elif file_path.endswith(".xlsx") or file_path.endswith(".xls"):
                loader = UnstructuredExcelLoader(file_path)
            elif file_path.endswith(".pptx") or file_path.endswith(".ppt"):
                loader = UnstructuredPowerPointLoader(file_path)
            elif file_path.endswith(".csv"):
                loader = CSVLoader(file_path)
            elif file_path.endswith(".html") or file_path.endswith(".htm"):
                loader = UnstructuredHTMLLoader(file_path)
            elif file_path.endswith(".epub"):
                loader = UnstructuredEPubLoader(file_path)
            elif file_path.endswith(".md"):
                loader = UnstructuredMarkdownLoader(file_path)
            elif file_path.endswith(".eml") or file_path.endswith(".msg"):
                loader = UnstructuredEmailLoader(file_path)
            else:
                loader = UnstructuredFileLoader(file_path)

            documents = loader.load()
            return "\n".join([doc.page_content for doc in documents])
        except Exception as e:
            return f"Ошибка обработки файла: {str(e)}"


class Code:
    def __init__(self, code_llm="deepseek-coder-v2:16b"):
        # Инициализация модели для генерации кода
        self.code_llm = OllamaLLM(model=code_llm, num_gpu=63)
        self.currency_converter = CurrencyConverter()

    def ask_code(self, prompt: Dict) -> str:
        question: str = prompt["question"]
        file_context: str = str(prompt["file_context"])
        file_text: str = prompt["file_text"]

        cleaned = (
            file_context.replace("[", "")
            .replace("]", "")
            .replace("'", "")
            .replace('"', "")
        )
        file_context = cleaned.split(",")
        file_ctx = ""
        if file_context and file_context != [""]:
            for file in file_context:
                file = file.strip()
                if file:
                    file_ctx += f"Название файла {file} : Информация из файла {self.currency_converter.load_file(file)}\n"
        else:
            file_ctx = ""

        prompt_template = PromptTemplate.from_template(
            """### Инструкции:
Ты должен создать код по запросу пользователя.
Делай всё в малейших деталях.

### Контекст:
- Код из файлов: {file_ctx}
- {file_text}

### Запрос пользователя:
{question}

### Ответ:
"""
        )
        conversation = LLMChain(llm=self.code_llm, prompt=prompt_template)
        response = conversation.predict(file_ctx=file_ctx, file_text=file_text, question=question)
        return f"Готовый код: {response}"


class GenerationPhoto:
    def __init__(self):
        pass

    def gen_img(self, prompt: str) -> str:
        # Генерация изображения с помощью Stable Diffusion
        try:
            model_id = "stabilityai/stable-diffusion-xl-base-1.0"
            pipe = StableDiffusionXLPipeline.from_pretrained(
                model_id, torch_dtype=torch.float16, variant="fp16"
            )
            pipe = pipe.to("cuda")

            image = pipe(prompt).images[0]

            # Сохраняем изображение в текущей директории
            output_dir = os.path.join(os.getcwd(), "generated_images")
            os.makedirs(output_dir, exist_ok=True)
            save_path = os.path.join(
                output_dir,
                f"generated_image_{int(torch.randint(0, 1000000, (1,)).item())}.png",
            )
            image.save(save_path)
            return f"Файл создан: {save_path}"
        except Exception as e:
            return f"Ошибка: {str(e)}"


class AnalysisPhoto:
    def __init__(self):
        # Проверка доступности CUDA и инициализация клиента ollama
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        try:
            self.client = Client(host="http://localhost:11434")
            self.client.generate(model="llava", prompt="test", stream=False)
        except Exception as e:
            print(f"Ошибка подключения к серверу ollama: {str(e)}")
            raise

    def _image_to_base64(self, img: Image.Image) -> str:
        # Преобразование изображения в строку base64
        buffered = io.BytesIO()
        if img.mode == "RGBA":
            img = img.convert("RGB")
        img.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def ask_llava(self, image_path, question) -> str:
        try:
            print(f"Attempting to open image: {image_path}")
            img = Image.open(image_path)
            base64_img = self._image_to_base64(img)
            print("Image loaded successfully, sending to llava")
            response = self.client.generate(
                model="llava",
                prompt=question,
                images=[base64_img],
                stream=False,
                options={"num_gpu": -1},
            )
            return f"Описание от вопроса: {response['response']}"
        except Exception as e:
            return f"Ошибка: {str(e)}"


class ImageAnalysisInput(BaseModel):
    image_path: str
    question: str


class InternetSearch:
    def __init__(self):
        pass

    def google_search(self, query):
        # Выполняет поиск в Google
        try:
            results = []
            for url in search(query, num_results=10, lang="ru"):
                results.append({"url": url})
            return json.dumps(results, ensure_ascii=False)
        except Exception as e:
            return f"Ошибка при выполнении поиска: {str(e)}"
