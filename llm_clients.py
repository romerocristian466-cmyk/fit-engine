import os
from openai import OpenAI, APITimeoutError, APIConnectionError
from google import genai
from google.genai import types
from pydantic import BaseModel
import json

class ResilientChatClient:
    def __init__(self):
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        self.openai_client = OpenAI(
            api_key=self.deepseek_api_key or "dummy_key_to_allow_init", 
            base_url="https://api.deepseek.com"
        )
        
        if self.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.gemini_api_key)
        else:
            self.gemini_client = None

    def chat_completion(self, messages: list[dict], system_prompt: str = None) -> dict:
        """
        Envía un mensaje al LLM, priorizando DeepSeek y conmutando a Gemini 2.5 Flash si falla.
        Returns: {"respuesta": str, "used_fallback": bool}
        """
        try:
            # Preparar mensajes para DeepSeek
            ds_messages = []
            if system_prompt:
                ds_messages.append({"role": "system", "content": system_prompt})
            
            # Formatear el historial
            for msg in messages:
                role = "assistant" if msg["role"] == "model" else msg["role"]
                ds_messages.append({"role": role, "content": msg["content"]})
                
            response = self.openai_client.chat.completions.create(
                model="deepseek-chat",
                messages=ds_messages,
                timeout=4.0
            )
            return {
                "respuesta": response.choices[0].message.content,
                "used_fallback": False
            }
        except (APITimeoutError, APIConnectionError, Exception) as e:
            # Captura errores 5xx y timeouts de OpenAI SDK y conmuta a Gemini
            print(f"[Fallback Triggered] DeepSeek falló: {str(e)}")
            return self._gemini_fallback(messages, system_prompt)

    def _gemini_fallback(self, messages: list[dict], system_prompt: str = None) -> dict:
        if not self.gemini_client:
            raise Exception("DeepSeek falló y GEMINI_API_KEY no está configurada para el fallback.")
        
        gemini_contents = []
        for msg in messages:
            role = msg["role"]
            # Convertir roles de OpenAI a roles de Gemini si es necesario
            if role == "assistant": role = "model"
            elif role == "system": continue # System prompts are handled separately
            gemini_contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])])
            )
            
        config = types.GenerateContentConfig()
        if system_prompt:
            config.system_instruction = system_prompt
            
        response = self.gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=gemini_contents,
            config=config,
        )
        
        return {
            "respuesta": response.text,
            "used_fallback": True
        }

    def structured_completion(self, messages: list[dict], response_schema: type[BaseModel], system_prompt: str = None):
        """
        Utiliza Gemini 2.5 Flash para extraer un JSON estructurado dado un esquema Pydantic.
        """
        if not self.gemini_client:
            raise Exception("GEMINI_API_KEY no está configurada para la extracción estructurada.")
            
        gemini_contents = []
        for msg in messages:
            role = msg["role"]
            if role == "assistant": role = "model"
            gemini_contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])])
            )
            
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        
        if system_prompt:
            config.system_instruction = system_prompt
            
        response = self.gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=gemini_contents,
            config=config,
        )
        
        # Validar y devolver la instancia Pydantic
        data = json.loads(response.text)
        return response_schema.model_validate(data)
