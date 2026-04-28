import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ALLOWED_ORIGINS
from app.routes import router

logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI()

app.add_middleware(
	CORSMiddleware,
	allow_origins=CORS_ALLOWED_ORIGINS,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(router)
