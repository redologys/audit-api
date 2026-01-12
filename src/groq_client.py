"""
Groq API client for LLM-based business audit scoring.
Uses llama-3.3-70b-versatile with JSON mode for structured output.
"""
import os
import json
import asyncio
from pathlib import Path
from typing import Optional
import httpx
from groq import Groq, AsyncGroq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "30"))
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # Base delay for exponential backoff


class GroqClientError(Exception):
    """Custom exception for Groq client errors."""
    pass


class GroqAuditClient:
    """
    Async client for calling Groq API to generate business audits.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GROQ_API_KEY
        if not self.api_key:
            raise GroqClientError("GROQ_API_KEY is required")
        
        self.client = AsyncGroq(api_key=self.api_key)
        self.system_prompt = self._load_system_prompt()
    
    def _load_system_prompt(self) -> str:
        """Load system prompt from config file."""
        # Try multiple possible locations
        possible_paths = [
            Path(__file__).parent.parent / "config" / "system_prompt.txt",
            Path("config/system_prompt.txt"),
            Path("../config/system_prompt.txt"),
        ]
        
        for path in possible_paths:
            if path.exists():
                return path.read_text(encoding="utf-8")
        
        raise GroqClientError(
            f"System prompt not found. Tried: {[str(p) for p in possible_paths]}"
        )
    
    async def generate_audit(self, business_data: dict) -> dict:
        """
        Generate a business audit using Groq API.
        
        Args:
            business_data: Formatted business input data
            
        Returns:
            Parsed JSON audit result
            
        Raises:
            GroqClientError: If API call fails after retries
        """
        user_message = self._format_user_message(business_data)
        
        last_error = None
        
        for attempt in range(MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    self._call_groq_api(user_message),
                    timeout=TIMEOUT_SECONDS
                )
                
                # Parse and validate JSON response
                audit_result = self._parse_response(response)
                return audit_result
                
            except asyncio.TimeoutError:
                last_error = GroqClientError(f"Request timed out after {TIMEOUT_SECONDS}s")
            except json.JSONDecodeError as e:
                last_error = GroqClientError(f"Invalid JSON response: {e}")
            except Exception as e:
                last_error = GroqClientError(f"API error: {str(e)}")
            
            # Exponential backoff before retry
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE ** (attempt + 1)
                await asyncio.sleep(delay)
        
        raise last_error or GroqClientError("Unknown error occurred")
    
    async def _call_groq_api(self, user_message: str) -> str:
        """Make the actual API call to Groq."""
        chat_completion = await self.client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            response_format={"type": "json_object"},  # Strict JSON mode
        )
        
        return chat_completion.choices[0].message.content
    
    def _format_user_message(self, business_data: dict) -> str:
        """Format the user message with business data."""
        return f"""Analyze the following business and generate a comprehensive digital presence audit:

BUSINESS DATA:
- Business Name: {business_data.get('businessName', 'Unknown')}
- Website URL: {business_data.get('websiteUrl') or 'No website provided'}
- Industry: {business_data.get('industry', 'unknown')}
- Location: {business_data.get('location', 'unknown')}
- Business Age: {business_data.get('businessAge', 'unknown')}
- Phone Number: {business_data.get('phoneNumber') or 'Not provided'}

SOCIAL MEDIA HANDLES:
- Instagram: {business_data.get('socialHandles', {}).get('instagram') or 'Not provided'}
- Facebook: {business_data.get('socialHandles', {}).get('facebook') or 'Not provided'}
- TikTok: {business_data.get('socialHandles', {}).get('tiktok') or 'Not provided'}
- Twitter/X: {business_data.get('socialHandles', {}).get('twitter') or 'Not provided'}
- LinkedIn: {business_data.get('socialHandles', {}).get('linkedin') or 'Not provided'}
- YouTube: {business_data.get('socialHandles', {}).get('youtube') or 'Not provided'}

Generate a complete audit following the JSON schema specified in your instructions. Be thorough but realistic in your scoring based on the provided information."""

    def _parse_response(self, response: str) -> dict:
        """Parse and validate the JSON response."""
        if not response:
            raise GroqClientError("Empty response from API")
        
        try:
            result = json.loads(response)
        except json.JSONDecodeError as e:
            # Try to extract JSON if wrapped in markdown
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                raise GroqClientError(f"Failed to parse JSON: {e}")
        
        # Basic validation
        required_fields = ['overallScore', 'grade', 'categoryBreakdown']
        missing = [f for f in required_fields if f not in result]
        if missing:
            raise GroqClientError(f"Missing required fields: {missing}")
        
        return result


# Synchronous wrapper for non-async contexts
class GroqAuditClientSync:
    """Synchronous wrapper for GroqAuditClient."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.async_client = GroqAuditClient(api_key)
    
    def generate_audit(self, business_data: dict) -> dict:
        """Generate audit synchronously."""
        return asyncio.run(self.async_client.generate_audit(business_data))


# Convenience function
async def run_audit(business_data: dict, api_key: Optional[str] = None) -> dict:
    """
    Convenience function to run an audit.
    
    Args:
        business_data: Formatted business input
        api_key: Optional Groq API key (uses env var if not provided)
        
    Returns:
        Audit result dictionary
    """
    client = GroqAuditClient(api_key)
    return await client.generate_audit(business_data)
