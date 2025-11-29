import json
import os
import random
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field


class ParticipantIn(BaseModel):
    name: str = Field(..., min_length=1)
    giftPreference: Optional[str] = None


class Participant(BaseModel):
    id: str
    name: str
    giftPreference: Optional[str] = None
    assignedTo: Optional[str] = None


ADMIN_SECRET = os.getenv("ADMIN_SECRET", "santaadmin")
BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"

_data_file_env = os.getenv("DATA_FILE")
if _data_file_env:
    _data_path = Path(_data_file_env)
    # If a directory is provided, store JSON inside it.
    DATA_FILE = _data_path / "data.json" if _data_path.is_dir() else _data_path
else:
    DATA_FILE = BASE_DIR / "data.json"

app = FastAPI(title="Secret Santa API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

participants: Dict[str, Participant] = {}
shuffled = False


def load_data():
    """Load participants from disk so data survives server restarts."""
    global participants, shuffled
    if not DATA_FILE.exists():
        return
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    participant_list = raw.get("participants", [])
    participants = {
        item["id"]: Participant(**item)
        for item in participant_list
        if "id" in item and "name" in item
    }
    shuffled = raw.get("shuffled", False) or any(
        p.assignedTo is not None for p in participants.values()
    )


def save_data():
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "participants": [p.model_dump() for p in participants.values()],
        "shuffled": shuffled,
    }
    DATA_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


load_data()


def require_admin(secret: Optional[str]):
    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Неверный секрет организатора.")


def build_valid_assignment(ids: List[str]) -> Dict[str, str]:
    """
    Shuffle until no participant is assigned to themselves.
    Uses a simple retry loop which is fine for small groups.
    """
    while True:
        receivers = ids.copy()
        random.shuffle(receivers)
        if all(giver != receiver for giver, receiver in zip(ids, receivers)):
            return {giver: receiver for giver, receiver in zip(ids, receivers)}


@app.get("/", include_in_schema=False)
def serve_index():
    if INDEX_FILE.exists():
        return FileResponse(str(INDEX_FILE))
        raise HTTPException(status_code=404, detail="Frontend not found.")


@app.get("/my-assignment/{participant_id}", include_in_schema=False)
def serve_assignment_page(participant_id: str):
    # Serve the same frontend for deep-linked assignment pages.
    if INDEX_FILE.exists():
        return FileResponse(str(INDEX_FILE))
    raise HTTPException(status_code=404, detail="Frontend not found.")


@app.post("/participants")
def add_participant(participant_in: ParticipantIn):
    if shuffled:
        raise HTTPException(
            status_code=400,
            detail="Распределение уже выполнено. Добавление новых участников недоступно.",
        )
    participant_id = str(uuid.uuid4())
    participant = Participant(
        id=participant_id,
        name=participant_in.name.strip(),
        giftPreference=participant_in.giftPreference.strip()
        if participant_in.giftPreference
        else None,
        assignedTo=None,
    )
    participants[participant_id] = participant
    save_data()
    return {
        "id": participant_id,
        "message": "Вы присоединились к Тайному Санте!",
        "assignmentLink": f"/my-assignment/{participant_id}",
    }


@app.get("/participants")
def list_participants(secret: Optional[str] = Query(None)):
    require_admin(secret)
    return list(participants.values())


@app.delete("/participants/{participant_id}")
def remove_participant(participant_id: str, secret: Optional[str] = Query(None)):
    require_admin(secret)
    if shuffled:
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалять участников после распределения.",
        )
    if participant_id not in participants:
        raise HTTPException(status_code=404, detail="Участник не найден.")
    participants.pop(participant_id)
    save_data()
    return {"message": "Участник удален."}


@app.post("/shuffle")
def shuffle(secret: Optional[str] = Query(None)):
    require_admin(secret)
    global shuffled
    if shuffled:
        raise HTTPException(status_code=400, detail="Распределение уже завершено.")
    if len(participants) < 2:
        raise HTTPException(
            status_code=400,
            detail="Для распределения нужно минимум двое участников.",
        )

    ids = list(participants.keys())
    assignment_map = build_valid_assignment(ids)

    for giver_id, receiver_id in assignment_map.items():
        participants[giver_id].assignedTo = receiver_id

    shuffled = True
    save_data()

    assignments_for_admin = [
        {
            "giver": participants[giver_id].name,
            "receiver": participants[receiver_id].name,
        }
        for giver_id, receiver_id in assignment_map.items()
    ]
    return {"message": "Распределение готово!", "assignments": assignments_for_admin}


@app.get("/assignment/{participant_id}")
def get_assignment(participant_id: str):
    participant = participants.get(participant_id)
    if not participant:
        raise HTTPException(status_code=404, detail="Участник не найден.")
    if not participant.assignedTo:
        raise HTTPException(status_code=400, detail="Распределение еще не готово.")
    receiver = participants.get(participant.assignedTo)
    if not receiver:
        raise HTTPException(status_code=500, detail="Данные распределения неполные.")
    return {
        "youAreGivingTo": {
            "name": receiver.name,
            "giftPreference": receiver.giftPreference,
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
