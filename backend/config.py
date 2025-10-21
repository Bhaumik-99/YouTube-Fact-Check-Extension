import os
from typing import Optional

class Config:  
    """Configuration class for fact-checker backend"""
    
    def __init__(self):
        # API Keys (use environment variables in production)
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY", "your-openai-api-key-here")
        self.google_factcheck_api_key: Optional[str] = os.getenv("GOOGLE_FACTCHECK_API_KEY", "your-google-factcheck-api-key")
        self.bing_search_api_key: Optional[str] = os.getenv("BING_SEARCH_API_KEY", "your-bing-search-api-key")
        
        # Server settings
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        self.debug: bool = os.getenv("DEBUG", "True").lower() == "true"
        
        # Audio processing settings
        self.max_audio_size_mb: int = int(os.getenv("MAX_AUDIO_SIZE_MB", "10"))
        self.supported_audio_formats: list = ["webm", "mp3", "wav", "m4a"]
        
        # Fact-checking settings
        self.max_claims_per_chunk: int = int(os.getenv("MAX_CLAIMS_PER_CHUNK", "5"))
        self.min_confidence_threshold: int = int(os.getenv("MIN_CONFIDENCE_THRESHOLD", "30"))
        
        # Rate limiting (requests per minute)
        self.rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
        
    def validate(self) -> bool:
        """Validate configuration settings"""
        if not self.openai_api_key or self.openai_api_key.startswith("your-"):
            print("Warning: OpenAI API key not configured properly")
            return False
        
        return True

# Global config instance
config = Config()
