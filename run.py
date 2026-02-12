from src.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        port=8080,
        reload=False,
        log_level="info"
    )
