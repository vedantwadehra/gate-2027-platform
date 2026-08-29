from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # General
    app_name: str = "GATE 2027 DA/CS Platform"
    environment: str = "development"

    # Database
    database_url: str = "sqlite:///./gate.db"

# LLM provider: "openai" | "google" | "groq" | "mock"
    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    google_model: str = "gemini-2.0-flash"
    groq_model: str = "llama-3.3-70b-versatile"

    # JWT (set a long random string in production)
    jwt_secret: str = "dev-secret-change-me"

    # Admin key for the question CRUD / seed / reset API (send as X-Admin-Key).
    admin_key: str = "admin-dev-key"

    # CORS (comma separated list of allowed origins)
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
