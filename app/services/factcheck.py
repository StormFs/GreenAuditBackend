from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_community.tools import DuckDuckGoSearchRun
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from app.schemas.report import EnvironmentalClaim
from app.core.interfaces import IFactCheckService
from app.core.config import settings
import asyncio

class MockFactCheckService(IFactCheckService):
    async def verify_claim(self, claim: EnvironmentalClaim) -> dict:
        print(f"MockFactCheck: Verifying '{claim.description}'")
        await asyncio.sleep(2) # Simulate work
        
        # Simple logic to make it look real-ish
        if "renewable" in claim.description.lower() or "reduced" in claim.description.lower():
             return {
                "verified": True,
                "confidence": 0.95,
                "evidence": "Mock Source: Annual Sustainability Report 2024 confirms this target was met.",
                "sources": ["https://example.com/report2024.pdf"]
            }
        else:
             return {
                "verified": False,
                "confidence": 0.80,
                "evidence": "Mock Source: No public record found matching this specific claim magnitude.",
                "sources": ["https://example.com/search_results"]
            }

class FactCheckResponse(BaseModel):
    is_verified: bool = Field(description="True if evidence supports the claim")
    confidence: float = Field(description="Confidence score 0.0 to 1.0")
    evidence_summary: str = Field(description="Summary of the findings")
    source_urls: List[str] = Field(description="List of relevant URLs found in the search text")

class WebFactCheckService(IFactCheckService):
    def __init__(self):
        if settings.GROQ_API_KEY:
            print("Using Groq (Llama 3) for Fact Checking.")
            self.llm = ChatGroq(
                model="llama-3.3-70b-versatile", 
                temperature=0,
                groq_api_key=settings.GROQ_API_KEY
            )
        elif settings.GOOGLE_API_KEY:
             print("Using Google Gemini for Fact Checking.")
             self.llm = ChatGoogleGenerativeAI(
                model="gemini-flash-latest",
                temperature=0,
                google_api_key=settings.GOOGLE_API_KEY
            )
        else:
             print("Warning: No AI API Key (Gemini/Groq). WebFactCheckService will fail.")
             
        self.search = DuckDuckGoSearchRun()
        self.parser = JsonOutputParser(pydantic_object=FactCheckResponse)

    async def verify_claim(self, claim: EnvironmentalClaim) -> dict:
        try:
            print(f"FactChecking claim: {claim.description[:50]}...")
            # 1. Search (Executes synchronously)
            # We search for the claim description + "verification" or "audit"
            query = f"{claim.description} verification audit report"
            try:
                search_results = self.search.invoke(query)
            except Exception as se:
                print(f"Search failed: {se}")
                search_results = "Search tool unavailable."

            # 2. Analyze with LLM
            prompt = ChatPromptTemplate.from_template(
                """
                You are an expert environmental auditor. Your goal is to fact-check the following claim using the provided search results.
                
                Claim: "{claim_desc}"
                Date Claimed: "{date_claimed}"
                
                Search Results:
                {search_results}
                
                Analyze the evidence. 
                - If the search results confirm the claim, set is_verified to true.
                - If they contradict, set false.
                - If inconclusive (no relevant info found), set false with low confidence (e.g. 0.1).
                - Summarize the evidence in 'evidence_summary'.
                - If you see URLs in the search text, list them.
                
                {format_instructions}
                """
            )

            chain = prompt | self.llm | self.parser
            
            result = await chain.ainvoke({
                "claim_desc": claim.description,
                "date_claimed": claim.date_claimed or "Unknown",
                "search_results": search_results,
                "format_instructions": self.parser.get_format_instructions()
            })
            
            # Helper to normalize keys if needed, but Pydantic parser matches keys
            return {
                "verified": result["is_verified"],
                "confidence": result["confidence"],
                "evidence": result["evidence_summary"],
                "sources": result.get("source_urls", [])
            }

        except Exception as e:
            print(f"Fact check extraction failed: {e}")
            return {
                "verified": False, 
                "confidence": 0.0, 
                "evidence": f"AI Verification failed: {str(e)}", 
                "sources": []
            }
