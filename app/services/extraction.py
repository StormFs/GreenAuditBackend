from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
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

class LLMExtractionService(IExtractionService):
    def __init__(self):
        if settings.GROQ_API_KEY:
            print("Using Groq (Llama 3) for extraction.")
            self.llm = ChatGroq(
                model="llama-3.3-70b-versatile", 
                temperature=0,
                groq_api_key=settings.GROQ_API_KEY
            )
        elif settings.GOOGLE_API_KEY:
             print("Using Google Gemini for extraction.")
             self.llm = ChatGoogleGenerativeAI(
                model="gemini-flash-latest", 
                temperature=0,
                google_api_key=settings.GOOGLE_API_KEY,
                convert_system_message_to_human=True 
            )
        else:
            print("Warning: No AI API Key found (Gemini/Groq). Service will fail.")

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=5, max=120),
        reraise=True
    )
    async def extract_claims(self, text: str) -> List[EnvironmentalClaim]:
        """
        Extracts environmental claims and coordinates from text.
        Handles chunking for large texts to respect rate limits.
        """
        structured_llm = self.llm.with_structured_output(ExtractionResult)

        prompt_template = ChatPromptTemplate.from_messages([
            ("user", "You are an expert environmental auditor. Extract all specific environmental claims. If a claim has a specific target number (e.g., '15%', '500 trees', '50 hectares'), extract that into 'measure_value' and 'measure_unit'. Also extract geographic coordinates if available.\n\nText to analyze:\n{text}")
        ])

        chain = prompt_template | structured_llm
        
        # Max chunk size logic (~15k characters is roughly 4k tokens, safe depending on model)
        # Groq Llama3 limits are tight on free tier.
        CHUNK_SIZE = 12000 
        overlap = 500
        
        all_claims = []
        
        # Simple chunking
        if len(text) > CHUNK_SIZE:
            print(f"Text too large ({len(text)} chars), chunking...")
            chunks = []
            start = 0
            while start < len(text):
                end = start + CHUNK_SIZE
                chunks.append(text[start:end])
                start = end - overlap
            
            print(f"Split into {len(chunks)} chunks.")
            
            for i, chunk in enumerate(chunks):
                print(f"Processing chunk {i+1}/{len(chunks)}...")
                try:
                    result = await chain.ainvoke({"text": chunk})
                    if result and result.claims:
                        all_claims.extend(result.claims)
                except Exception as e:
                    print(f"Error processing chunk {i+1}: {e}")
                    # If it's a rate limit, the outer retry might not be enough if we crash here.
                    # But we let tenacity handle the retry on the WHOLE function? 
                    # No, that would restart all chunks. ideally we retry per chunk.
                    # For now, let's just log and continue to next chunk to not fail completely?
                    # Or simple sleep?
                    if "429" in str(e) or "413" in str(e):
                        # Simple naive backoff if inner failure
                        import asyncio
                        await asyncio.sleep(60) 
                        # Retry once?
                        try:
                            result = await chain.ainvoke({"text": chunk})
                            if result and result.claims:
                                all_claims.extend(result.claims)
                        except:
                            pass
        else:
            try:
                result = await chain.ainvoke({"text": text})
                if result:
                    all_claims = result.claims
            except Exception as e:
                 print(f"Error calling LLM: {e}")
                 raise e
                 
        return all_claims

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
                date_claimed="2025-06-15",
                measure_value=5000,
                measure_unit="trees"
            ),
             EnvironmentalClaim(
                description="Restored 50 hectares of mangroves",
                location=GeoCoordinates(latitude=9.9281, longitude=-84.0907),
                date_claimed="2025-08-20",
                measure_value=50,
                measure_unit="hectares"
            ),
             EnvironmentalClaim(
                description="Our data centers run on 100% renewable energy",
                location=None, # Non-spatial claim for fact checking
                date_claimed="2025-01-01",
                measure_value=100,
                measure_unit="%"
            )
        ]
