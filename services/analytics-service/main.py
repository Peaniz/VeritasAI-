import uvicorn
from src.app import create_app
from src.settings import settings

app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
