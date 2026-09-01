"""Start the API. Serves the built frontend too, if one exists."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="127.0.0.1", port=8088, reload=False)
