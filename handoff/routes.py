"""HTTP routes. Feature handlers stay unimplemented until their task branches."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/handoffs", status_code=501)
def create_handoff() -> None:
    raise HTTPException(status_code=501, detail="not implemented")


@router.get("/handoffs", status_code=501)
def list_handoffs() -> None:
    raise HTTPException(status_code=501, detail="not implemented")


@router.get("/handoffs/briefing", status_code=501)
def export_briefing() -> None:
    raise HTTPException(status_code=501, detail="not implemented")
