import logging
import logging.config
import os
from pathlib import Path

from dotenv import load_dotenv

def env_to_bool(key:str, default=False):
    v = os.getenv(key, default)
    if not v:
        return default

    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True

    return False


class Settings:
    def __init__(self):
        # Parents 0 will be conf, 1 the module and 2 the repo itself
        base_dir = Path(__file__).resolve().parents[1]
        load_dotenv(override=True)

        # Application
        self.DEBUG = env_to_bool('DEBUG', False)
        self.LOG_LEVEL: int = int(os.getenv('LOG_LEVEL', '20'))
        self.HTTPX_LOG_LEVEL: int = int(os.getenv('HTTPX_LOG_LEVEL', '30'))
        self.HTTPX_HAR_ENABLED: bool = env_to_bool('HTTPX_HAR_ENABLED', False)
        har_path  = os.getenv('HTTPX_HAR_PATH', None)
        self.HTTPX_HAR_PATH: str = har_path if har_path else os.path.join(base_dir.parent, 'har')

        # ILUCCA
        self.ILUCCA_USERNAME: str = os.getenv('ILUCCA_USERNAME', 'placeholder')
        self.ILUCCA_PASSWORD: str = os.getenv('ILUCCA_PASSWORD', 'placeholder')

        # Telegram
        self.TELEGRAM_ENABLED = env_to_bool('TELEGRAM_ENABLED', False)
        self.TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
        self.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

        # Configure logging
        logging_config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'},
                'detailed': {'format': '%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(lineno)d - %(message)s'}
            },
            'handlers': {
                'console': {'class': 'logging.StreamHandler', 'formatter': 'detailed', 'level': self.LOG_LEVEL},
            },
            'loggers': {
                '': {
                    'handlers': ['console'],
                    'level': self.LOG_LEVEL
                },
                'app.module1': {
                    'handlers': ['console'],
                    'level': 'DEBUG',
                    'propagate': False
                }
            }
        }
        logging.config.dictConfig(logging_config)
        # 2. Forcefully override external libraries directly
        # This bypasses the dictConfig internal validation that is failing
        logging.getLogger("httpx").setLevel(self.HTTPX_LOG_LEVEL)
        logging.getLogger("httpcore").setLevel(self.HTTPX_LOG_LEVEL)

settings = Settings()
