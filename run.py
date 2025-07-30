from app.main import app
import logging

if __name__ == "__main__":
    import uvicorn
    logging.info("Starting server")
    uvicorn.run(
        app,
        port=8000,
        reload=False,
        log_level="info"
    )