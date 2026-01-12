"""
Pydantic models for input validation and type safety.
"""
from typing import Optional, Dict
from pydantic import BaseModel, Field, field_validator, EmailStr
import re


class SocialHandles(BaseModel):
    """Social media handles for the business."""
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    twitter: Optional[str] = None
    linkedin: Optional[str] = None
    youtube: Optional[str] = None

    @field_validator('instagram', 'tiktok', 'twitter', mode='before')
    @classmethod
    def clean_handle(cls, v: Optional[str]) -> Optional[str]:
        """Remove @ prefix if present."""
        if v and v.startswith('@'):
            return v[1:]
        return v


class BusinessInput(BaseModel):
    """Input model for business audit request."""
    business_name: str = Field(..., min_length=2, max_length=200, description="Name of the business")
    website_url: Optional[str] = Field(None, description="Business website URL")
    industry: str = Field("unknown", description="Industry category")
    location: str = Field("unknown", description="City/State location")
    social_handles: SocialHandles = Field(default_factory=SocialHandles)
    business_age: Optional[str] = Field(None, pattern="^(new|established|unknown)$")
    phone_number: Optional[str] = Field(None, description="Business phone number")
    email: Optional[EmailStr] = Field(None, description="Email to send report to")

    @field_validator('website_url', mode='before')
    @classmethod
    def sanitize_url(cls, v: Optional[str]) -> Optional[str]:
        """Add https:// if missing and validate URL format."""
        if not v or v.strip() == '':
            return None
        
        v = v.strip()
        
        # Add https:// if no protocol specified
        if not v.startswith(('http://', 'https://')):
            v = f'https://{v}'
        
        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE
        )
        
        if not url_pattern.match(v):
            raise ValueError('Invalid URL format')
        
        return v

    @field_validator('phone_number', mode='before')
    @classmethod
    def clean_phone(cls, v: Optional[str]) -> Optional[str]:
        """Clean and validate phone number."""
        if not v:
            return None
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', v)
        
        # US phone numbers should have 10-11 digits
        if len(digits) < 10:
            return None  # Invalid, but don't fail - just ignore
        
        return digits

    @field_validator('industry', mode='before')
    @classmethod
    def normalize_industry(cls, v: Optional[str]) -> str:
        """Normalize industry to known categories."""
        if not v:
            return "unknown"
        
        v = v.lower().strip().replace(' ', '_')
        
        valid_industries = [
            "restaurant", "professional_services", "retail", "home_services",
            "healthcare", "fitness", "beauty", "real_estate", "automotive",
            "technology", "education", "entertainment", "other", "unknown"
        ]
        
        return v if v in valid_industries else "other"


def validate_business_input(data: dict) -> BusinessInput:
    """
    Validate and sanitize business input data.
    
    Args:
        data: Raw input dictionary from API request
        
    Returns:
        Validated BusinessInput model
        
    Raises:
        ValueError: If validation fails
    """
    # Handle nested social_handles if passed as flat dict
    if 'social_handles' not in data:
        social_keys = ['instagram', 'facebook', 'tiktok', 'twitter', 'linkedin', 'youtube']
        social_handles = {}
        for key in social_keys:
            if key in data:
                social_handles[key] = data.pop(key)
        if social_handles:
            data['social_handles'] = social_handles
    
    return BusinessInput(**data)


def format_input_for_groq(validated_input: BusinessInput) -> dict:
    """
    Format validated input for sending to Groq API.
    
    Args:
        validated_input: Validated BusinessInput model
        
    Returns:
        Dictionary formatted for the Groq system prompt
    """
    return {
        "businessName": validated_input.business_name,
        "websiteUrl": validated_input.website_url,
        "industry": validated_input.industry,
        "location": validated_input.location,
        "socialHandles": {
            "instagram": validated_input.social_handles.instagram,
            "facebook": validated_input.social_handles.facebook,
            "tiktok": validated_input.social_handles.tiktok,
            "twitter": validated_input.social_handles.twitter,
            "linkedin": validated_input.social_handles.linkedin,
            "youtube": validated_input.social_handles.youtube,
        },
        "businessAge": validated_input.business_age or "unknown",
        "phoneNumber": validated_input.phone_number,
    }
