"""
A very simple FastAPI server for testing Docker networking.
"""
from fastapi import FastAPI
import uvicorn

# Create a simple FastAPI app
app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello World"}

@app.get("/health")
def health():
    return {"status": "healthy", "version": "test-1.0"}

if __name__ == "__main__":
    # Run the app directly
    uvicorn.run(app, host="0.0.0.0", port=8000)
