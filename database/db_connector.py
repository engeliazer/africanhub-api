from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
import os
from dotenv import load_dotenv
from typing import Optional
from .base import Base

# Load environment variables
load_dotenv()

# Database connection parameters (XAMPP default settings)
DB_USER = os.getenv('DB_USER', 'ocpac')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'oCpAc%402025')  # XAMPP default has no password
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_PORT = os.getenv('DB_PORT', '3306')  # XAMPP default port
DB_NAME = os.getenv('DB_NAME', 'ocpac')

# Create database URL for MySQL with explicit port using pymysql
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True  # Enable automatic reconnection
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create scoped session
db_session = scoped_session(SessionLocal)

# Create declarative base
Base = declarative_base()

def init_db():
    """Initialize the database by creating all tables"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Get a database session"""
    db_connector = DBConnector()
    return db_connector.get_session()

class DBConnector:
    _instance = None
    _engine = None
    _SessionFactory = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBConnector, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize database connection"""
        try:
            # Create engine with MySQL-specific configuration
            self._engine = create_engine(
                DATABASE_URL,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=3600,
                pool_pre_ping=True  # Enable automatic reconnection
            )
            
            # Create session factory
            self._SessionFactory = scoped_session(
                sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=self._engine
                )
            )
            
        except Exception as e:
            print(f"Error initializing database connection: {str(e)}")
            raise

    def get_session(self):
        """Get a new database session"""
        if not self._SessionFactory:
            raise RuntimeError("Database not initialized")
        return self._SessionFactory()

    def close_session(self, session):
        """Close a database session"""
        if session:
            session.close()

    def get_engine(self):
        """Get the SQLAlchemy engine"""
        if not self._engine:
            raise RuntimeError("Database engine not initialized")
        return self._engine

    def create_all_tables(self):
        """Create all tables defined in SQLAlchemy models"""
        try:
            Base.metadata.create_all(self._engine)
        except SQLAlchemyError as e:
            print(f"Error creating tables: {str(e)}")
            raise

    def drop_all_tables(self):
        """Drop all tables defined in SQLAlchemy models"""
        try:
            Base.metadata.drop_all(self._engine)
        except SQLAlchemyError as e:
            print(f"Error dropping tables: {str(e)}")
            raise

    def execute_query(self, query: str, params: Optional[dict] = None):
        """Execute a raw SQL query"""
        try:
            with self._engine.connect() as connection:
                if params:
                    result = connection.execute(query, params)
                else:
                    result = connection.execute(query)
                return result
        except SQLAlchemyError as e:
            print(f"Error executing query: {str(e)}")
            raise

    def __del__(self):
        """Cleanup when the instance is destroyed"""
        if self._SessionFactory:
            self._SessionFactory.remove() 