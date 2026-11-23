"""Developer bootstrap; apply reviewed migrations in production before starting the API."""
from .main import Base, engine
if __name__ == '__main__':
    Base.metadata.create_all(engine)
    print('Database tables created')
