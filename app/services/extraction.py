from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.schemas.report import EnvironmentalClaim, GeoCoordinates
from app.core.interfaces import IExtractionService
from app.core.config import settings

# Helper for Pydantic v1 used by LangChain inside structured output if needed,
# or we can rely on standard Pydantic v2 if the library supports it fully.
# Recent LangChain versions support Pydantic v2.

class ExtractionResult(BaseModel):
    claims: List[EnvironmentalClaim]

class GeminiExtractionService(IExtractionService):
    def __init__(self):
        if not settings.GOOGLE_API_KEY:
             print("Warning: GOOGLE_API_KEY not set. GeminiExtractionService will fail if called.")
             
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-flash-latest", 
            temperature=0,
            google_api_key=settings.GOOGLE_API_KEY,
            convert_system_message_to_human=True 
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True
    )
    async def extract_claims(self, text: str) -> List[EnvironmentalClaim]:
        """
        Extracts environmental claims and coordinates from text using Gemini.
        """
        # We want the llm to return a list of EnvironmentalClaim objects.
        # with_structured_output is the modern LangChain way.
        structured_llm = self.llm.with_structured_output(ExtractionResult)

        prompt_template = ChatPromptTemplate.from_messages([
            ("user", "You are an expert environmental auditor. Extract all specific environmental claims (like 'planted trees', 'restored area') and their geographic coordinates from the following text. Return the result as a JSON object with a 'claims' key.\n\nText to analyze:\n{text}")
        ])

        chain = prompt_template | structured_llm
        
        try:
            result = await chain.ainvoke({"text": text})
            return result.claims
        except Exception as e:
            print(f"Error calling Gemini: {e}")
            raise e

class MockExtractionService(IExtractionService):
    def __init__(self):
        # self.llm = ChatOpenAI(model="gpt-4", temperature=0)
        pass

    async def extract_claims(self, text: str) -> List[EnvironmentalClaim]:
        """
        Extracts environmental claims and coordinates from text using LangChain.
        """
        # Placeholder for LangChain logic
        # prompt = ChatPromptTemplate.from_messages([
        #     ("system", "Extract environmental claims and their locations."),
        #     ("user", "{text}")
        # ])
        # chain = prompt | self.llm.with_structured_output(List[EnvironmentalClaim])
        # return await chain.ainvoke({"text": text})

        # Mock implementation for scaffolding
        return [
            EnvironmentalClaim(
                description="Planted 5000 trees in the Amazon Rainforest",
                location=GeoCoordinates(latitude=-3.4653, longitude=-62.2159),
                date_claimed="2025-06-15"
            ),
             EnvironmentalClaim(
                description="Restored 50 hectares of mangroves",
                location=GeoCoordinates(latitude=9.9281, longitude=-84.0907),
                date_claimed="2025-08-20"
            )
        ]
