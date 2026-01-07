from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "GreenAudit"
    API_V1_STR: str = "/api/v1"
    
    # External API Keys (Load from env in production)
    SENTINELHUB_INSTANCE_ID: str = ""
    SENTINELHUB_CLIENT_ID: str = ""
    SENTINELHUB_CLIENT_SECRET: str = ""
    
    # Gemini API Key
    GOOGLE_API_KEY: str = ""
    
    # Groq API Key
    GROQ_API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
