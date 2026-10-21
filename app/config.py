from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    frontend_url: str
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str
    db_password: str
    db_name: str = "academia"
    jwt_secret: str
    encryption_key: str
    hash_key: str
    webhook_secret: str
    catraca_simulada: bool = False
    catraca_host: str
    catraca_user: str
    catraca_pass: str
    catraca_path_abrir: str
    catraca_path_usuario: str
    seed_email: str | None = None
    seed_senha: str | None = None

    @property
    def producao(self) -> bool:
        return self.app_env == "production"


settings = Settings()  # falha ao iniciar se faltar algum segredo
