"""Resumes router for Resume Targeter API.

Provides endpoints for managing resumes (list, upload, delete, preview).
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
import json

from src.resume.parser import ResumeParser
from backend.limiter import limiter

router = APIRouter()

# Security constants
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_path_within_directory(file_path: Path, base_dir: Path) -> None:
    """Ensure file_path is within base_dir (prevent path traversal attacks)."""
    if not file_path.resolve().is_relative_to(base_dir.resolve()):
        raise HTTPException(status_code=403, detail="Access denied")

# Resume library directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
RESUME_LIBRARY_DIR = PROJECT_ROOT / "data" / "resumes"
RESUME_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)

# Initialize parser
parser = ResumeParser()


class ResumeMetadata(BaseModel):
    """Metadata for a saved resume."""
    filename: str
    name: str
    format: str  # "text", "json"
    saved_at: Optional[str] = None
    char_count: Optional[int] = None


class ResumeListResponse(BaseModel):
    """Response model for resume list."""
    resumes: List[ResumeMetadata]
    total: int


class ResumeRole(BaseModel):
    """A single role in a resume."""
    company: str
    title: str
    duration: str
    bullets: List[str]
    location: Optional[str] = None
    technologies: List[str] = []


class ResumePreview(BaseModel):
    """Parsed resume structure for preview."""
    summary: str
    roles: List[ResumeRole]
    education: str
    skills: Dict[str, List[str]] = {}
    source_format: str


class ResumeUploadResponse(BaseModel):
    """Response after uploading a resume."""
    success: bool
    filename: str
    message: str


class DomainSuggestion(BaseModel):
    """A suggested domain based on resume content."""
    domain: str
    confidence: float
    category: str
    evidence: str
    description: str


class SuggestedDomainsResponse(BaseModel):
    """Response for suggested domains endpoint."""
    filename: str
    suggestions: List[DomainSuggestion]
    total: int


@router.get("", response_model=ResumeListResponse)
@limiter.limit("200/minute")
async def list_resumes(request: Request):
    """List all saved resumes from the library."""
    resumes = []

    # Text files (.txt)
    for file in RESUME_LIBRARY_DIR.glob("*.txt"):
        meta_file = file.with_name(file.stem + "_meta.json")
        name = file.stem
        saved_at = None

        if meta_file.exists():
            try:
                with open(meta_file) as f:
                    meta = json.load(f)
                    name = meta.get("name", file.stem)
                    saved_at = meta.get("saved_at")
            except:
                pass

        resumes.append(ResumeMetadata(
            filename=file.name,
            name=name,
            format="text",
            saved_at=saved_at,
            char_count=file.stat().st_size
        ))

    # Markdown files (.md)
    for file in RESUME_LIBRARY_DIR.glob("*.md"):
        meta_file = file.with_name(file.stem + "_meta.json")
        name = file.stem
        saved_at = None

        if meta_file.exists():
            try:
                with open(meta_file) as f:
                    meta = json.load(f)
                    name = meta.get("name", file.stem)
                    saved_at = meta.get("saved_at")
            except:
                pass

        resumes.append(ResumeMetadata(
            filename=file.name,
            name=name,
            format="text",
            saved_at=saved_at,
            char_count=file.stat().st_size
        ))

    # JSON resume files (exclude schema and meta files)
    for file in RESUME_LIBRARY_DIR.glob("*.json"):
        if file.name.endswith('_meta.json') or file.name == 'resume_schema.json':
            continue

        try:
            with open(file) as f:
                data = json.load(f)

            if 'experience' in data:
                name = data.get('metadata', {}).get('name', file.stem)
                saved_at = data.get('metadata', {}).get('saved_at')
                resumes.append(ResumeMetadata(
                    filename=file.name,
                    name=name,
                    format="json",
                    saved_at=saved_at,
                    char_count=file.stat().st_size
                ))
        except:
            pass

    # Sort by name
    resumes.sort(key=lambda x: x.name.lower())

    return ResumeListResponse(resumes=resumes, total=len(resumes))


@router.get("/{filename}")
@limiter.limit("200/minute")
async def get_resume(request: Request, filename: str):
    """Get resume content by filename."""
    file_path = RESUME_LIBRARY_DIR / filename
    validate_path_within_directory(file_path, RESUME_LIBRARY_DIR)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Resume not found")

    with open(file_path) as f:
        content = f.read()

    return {
        "filename": filename,
        "content": content,
        "format": "json" if filename.endswith(".json") else "text"
    }


@router.get("/{filename}/preview", response_model=ResumePreview)
@limiter.limit("200/minute")
async def preview_resume(request: Request, filename: str):
    """Get parsed preview of a resume."""
    file_path = RESUME_LIBRARY_DIR / filename
    validate_path_within_directory(file_path, RESUME_LIBRARY_DIR)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Resume not found")

    with open(file_path) as f:
        content = f.read()

    try:
        structure = parser.parse_auto(content)

        roles = [
            ResumeRole(
                company=role.company,
                title=role.title,
                duration=role.duration,
                bullets=role.bullets,
                location=getattr(role, 'location', ''),
                technologies=getattr(role, 'technologies', [])
            )
            for role in structure.roles
        ]

        return ResumePreview(
            summary=structure.summary,
            roles=roles,
            education=structure.education,
            skills=structure.skills,
            source_format=structure.source_format
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse resume: {str(e)}")


@router.get("/{filename}/suggested-domains", response_model=SuggestedDomainsResponse)
@limiter.limit("200/minute")
async def get_suggested_domains(request: Request, filename: str):
    """Get AI-suggested domains from resume content.

    Analyzes the resume text and suggests domains based on
    keyword matches from the domain expertise taxonomy.
    """
    file_path = RESUME_LIBRARY_DIR / filename
    validate_path_within_directory(file_path, RESUME_LIBRARY_DIR)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Resume not found")

    with open(file_path) as f:
        content = f.read()

    try:
        # For JSON resumes, extract the text content
        if filename.endswith(".json"):
            structure = parser.parse_auto(content)
            text_content = structure.raw_text
        else:
            text_content = content

        # Extract domain suggestions
        suggestions = parser.extract_domains(text_content)

        return SuggestedDomainsResponse(
            filename=filename,
            suggestions=[
                DomainSuggestion(
                    domain=s['domain'],
                    confidence=s['confidence'],
                    category=s['category'],
                    evidence=s['evidence'],
                    description=s['description']
                )
                for s in suggestions
            ],
            total=len(suggestions)
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract domains: {str(e)}")


@router.post("", response_model=ResumeUploadResponse)
@limiter.limit("20/minute")
async def upload_resume(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...)
):
    """Upload a new resume to the library.

    Accepts .txt, .md, or .json files.
    """
    # Validate file extension
    allowed_extensions = {'.txt', '.md', '.json'}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Read content with size limit
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )
    content_str = content.decode('utf-8')

    # Validate JSON if applicable
    if file_ext == '.json':
        try:
            data = json.loads(content_str)
            if 'experience' not in data:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid JSON resume: missing 'experience' field"
                )
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")

    # Generate safe filename
    safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
    safe_name = safe_name.replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d")
    filename = f"{safe_name}_{timestamp}{file_ext}"

    file_path = RESUME_LIBRARY_DIR / filename

    # Save file
    with open(file_path, "w") as f:
        f.write(content_str)

    # Save metadata for text files
    if file_ext != '.json':
        meta_path = file_path.with_name(file_path.stem + "_meta.json")
        with open(meta_path, "w") as f:
            json.dump({
                "name": name,
                "saved_at": datetime.now().isoformat(),
                "char_count": len(content_str)
            }, f, indent=2)
    else:
        # Update metadata inside JSON
        try:
            data = json.loads(content_str)
            if 'metadata' not in data:
                data['metadata'] = {}
            data['metadata']['name'] = name
            data['metadata']['saved_at'] = datetime.now().isoformat()
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2)
        except:
            pass

    return ResumeUploadResponse(
        success=True,
        filename=filename,
        message=f"Resume '{name}' saved successfully"
    )


@router.delete("/{filename}")
@limiter.limit("20/minute")
async def delete_resume(request: Request, filename: str):
    """Delete a resume from the library."""
    file_path = RESUME_LIBRARY_DIR / filename
    validate_path_within_directory(file_path, RESUME_LIBRARY_DIR)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Resume not found")

    # Delete main file
    file_path.unlink()

    # Delete metadata file if exists
    meta_path = file_path.with_name(file_path.stem + "_meta.json")
    if meta_path.exists():
        meta_path.unlink()

    return {"success": True, "message": f"Deleted {filename}"}


@router.post("/parse")
@limiter.limit("60/minute")
async def parse_resume_content(request: Request, content: str = Form(...)):
    """Parse resume content without saving.

    Useful for previewing uploaded content before saving.
    """
    try:
        structure = parser.parse_auto(content)

        roles = [
            {
                "company": role.company,
                "title": role.title,
                "duration": role.duration,
                "bullets": role.bullets
            }
            for role in structure.roles
        ]

        return {
            "success": True,
            "summary": structure.summary,
            "roles": roles,
            "education": structure.education,
            "skills": structure.skills,
            "source_format": structure.source_format
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse error: {str(e)}")
