from motor.motor_asyncio import AsyncIOMotorClient
from backend.config import get_settings
import structlog

logger = structlog.get_logger()

class Database:
    client: AsyncIOMotorClient = None
    db = None

    async def connect(self):
        settings = get_settings()
        logger.info("Connecting to MongoDB...", url=settings.MONGODB_URL)
        self.client = AsyncIOMotorClient(settings.MONGODB_URL)
        self.db = self.client[settings.MONGODB_DB_NAME]
        logger.info("Connected to MongoDB", database=settings.MONGODB_DB_NAME)

    async def close(self):
        if self.client:
            logger.info("Closing MongoDB connection...")
            self.client.close()
            logger.info("MongoDB connection closed")

db = Database()

async def get_database():
    return db.db
