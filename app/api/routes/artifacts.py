from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_session
from app.models.artifact import Artifact
from app.models.user import User
from app.schemas.artifact import ArtifactCreate, ArtifactOut

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("", response_model=list[ArtifactOut])
async def list_artifacts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Artifact).order_by(Artifact.id).limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.get("/{artifact_id}", response_model=ArtifactOut)
async def get_artifact(artifact_id: int, session: AsyncSession = Depends(get_session)):
    artifact = await session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artifact not found")
    return artifact


@router.post("", response_model=ArtifactOut, status_code=status.HTTP_201_CREATED)
async def create_artifact(
    data: ArtifactCreate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    artifact = Artifact(**data.model_dump())
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)
    return artifact
