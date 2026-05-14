from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27017
    MONGO_USER: str = "mongo_admin"
    MONGO_PASSWORD: str = "password"
    MONGO_DB: str = "library_db"

    @property
    def MONGO_URL(self) -> str:
        return (
            f"mongodb://{self.MONGO_USER}:{self.MONGO_PASSWORD}"
            f"@{self.MONGO_HOST}:{self.MONGO_PORT}"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
