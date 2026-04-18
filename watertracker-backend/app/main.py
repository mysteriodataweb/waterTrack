from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routes import water

Base.metadata.create_all(bind=engine)

app = FastAPI(title="WaterTracker API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(water.router, prefix="/api")

@app.get("/")
def root():
    return {"message": "WaterTracker API en ligne "}