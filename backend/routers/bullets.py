"""Router for managing liked bullet points."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from src.database.db import get_db
from src.database.models import LikedBullet
from backend.limiter import limiter

router = APIRouter()


class LikedBulletCreate(BaseModel):
    """Request model for saving a liked bullet."""
    original_text: str = Field(..., max_length=2000)
    rewritten_text: str = Field(..., max_length=2000)
    role_title: Optional[str] = Field(None, max_length=200)
    company: Optional[str] = Field(None, max_length=200)
    job_id: Optional[int] = None


class LikedBulletResponse(BaseModel):
    """Response model for a liked bullet."""
    id: int
    original_text: str
    rewritten_text: str
    role_title: Optional[str]
    company: Optional[str]
    job_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedLikedBulletsResponse(BaseModel):
    """Paginated response for liked bullets."""
    items: List[LikedBulletResponse]
    total: int
    skip: int
    limit: int


@router.post("", response_model=LikedBulletResponse)
@limiter.limit("60/minute")
async def save_liked_bullet(
    request: Request,
    bullet: LikedBulletCreate,
    session: Session = Depends(get_db)
):
    """Save a new liked bullet point."""
    db_bullet = LikedBullet(
        original_text=bullet.original_text,
        rewritten_text=bullet.rewritten_text,
        role_title=bullet.role_title,
        company=bullet.company,
        job_id=bullet.job_id
    )
    
    session.add(db_bullet)
    session.commit()
    session.refresh(db_bullet)
    
    return db_bullet


@router.get("", response_model=PaginatedLikedBulletsResponse)
@limiter.limit("200/minute")
async def list_liked_bullets(
    request: Request,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    role_filter: Optional[str] = Query(default=None, max_length=200),
    session: Session = Depends(get_db)
):
    """List liked bullet points with pagination and optional filtering."""
    query = session.query(LikedBullet)

    # Apply role filter if provided
    if role_filter:
        query = query.filter(LikedBullet.role_title == role_filter)

    total = query.count()
    bullets = query.order_by(LikedBullet.created_at.desc()).offset(skip).limit(limit).all()

    return PaginatedLikedBulletsResponse(
        items=bullets,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/roles", response_model=List[str])
@limiter.limit("200/minute")
async def list_unique_roles(request: Request, session: Session = Depends(get_db)):
    """Get list of unique role titles for filtering."""
    results = session.query(LikedBullet.role_title).distinct().filter(
        LikedBullet.role_title.isnot(None)
    ).all()
    return [r[0] for r in results if r[0]]


@router.delete("/{bullet_id}")
@limiter.limit("60/minute")
async def delete_liked_bullet(
    request: Request,
    bullet_id: int,
    session: Session = Depends(get_db)
):
    """Delete a liked bullet point."""
    bullet = session.query(LikedBullet).filter(LikedBullet.id == bullet_id).first()
    if not bullet:
        raise HTTPException(status_code=404, detail="Bullet not found")

    session.delete(bullet)
    session.commit()
    return {"status": "success"}
