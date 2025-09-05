from src.main import app
import logging

if __name__ == "__main__":
    import uvicorn
    logging.info("Starting server")
    uvicorn.run(
        app,
        port=8080,
        reload=False,
        log_level="info"
    )