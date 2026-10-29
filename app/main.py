from fastapi import FastAPI

from app.api import ops_router

app = FastAPI(title="TaskFlow")

app.include_router(ops_router.router)
