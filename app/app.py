from pathlib import Path

import uvicorn
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from db import VALID_STATUSES, get_all_statuses, init_db, update_status

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI()


@app.on_event("startup")
async def startup() -> None:
    init_db()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/statuses")
async def statuses() -> dict[str, str]:
    return get_all_statuses()


class StatusUpdate(BaseModel):
    status: str


@app.patch("/api/status/{card_id}")
async def patch_status(card_id: str, body: StatusUpdate) -> dict[str, str]:
    if body.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status: {body.status}")
    if not update_status(card_id, body.status):
        raise HTTPException(status_code=404, detail=f"Card not found: {card_id}")
    return {"card_id": card_id, "status": body.status}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
