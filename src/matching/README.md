# Matching Module

Calculates job-resume compatibility scores using NLP and rule-based algorithms.

## Overview

This module is the core intelligence of the job matcher. It takes job postings and a resume, then produces a match score (0-100%) indicating how well the job fits the candidate.

## Files

| File | Purpose |
|------|---------|
| `engine.py` | Main orchestrator - combines skills and experience scores |
| `skills_matcher.py` | NLP-based semantic skill matching using sentence-transformers |
| `skill_extractor.py` | Extracts skills from job descriptions using a curated dictionary |

## Score Calculation

```
Overall Score = (Skills × 0.45) + (Experience × 0.35) + (Domains × 0.20)
```

Weights are configurable in `config.yaml` under `matching.weights`.

### Skills Score (skills_matcher.py)

Uses **sentence-transformers** to compute semantic similarity:

1. Extract skills from job description using `skill_extractor.py`
2. Generate embeddings for job skills and resume skills
3. Compute cosine similarity between embeddings
4. Score based on proportion of matching skills (threshold: 0.5 similarity)

**Key function:** `SkillsMatcher.calculate_match()`

### Experience Score (engine.py)

Rule-based comparison:

1. Extract required years from job description (regex patterns)
2. Compare against resume's years of experience
3. Apply seniority level matching (entry/mid/senior/director)
4. Step-based scoring for experience gaps

**Key function:** `JobMatcher._calculate_experience_score()`

## Skill Extraction Dictionary

Located in `skill_extractor.py` as `PM_SKILLS_DICT`. Contains ~180 skills across 7 categories:

- **Product Management**: roadmap, PRD, backlog, user stories, etc.
- **Metrics & Analytics**: KPIs, A/B testing, OKRs, etc.
- **Technical**: SQL, APIs, cloud platforms, AI/ML, etc.
- **Methodologies**: Agile, Scrum, Kanban, Jira, etc.
- **Business**: B2B, SaaS, enterprise, go-to-market, etc.
- **Collaboration**: stakeholder management, cross-functional, etc.
- **Engineering Partnership**: DevOps, QA, technical specs, etc.

### Adding New Skills

Edit `PM_SKILLS_DICT` in `skill_extractor.py`:

```python
PM_SKILLS_DICT = {
    "category_name": [
        "existing skill",
        "new skill to add",  # Add here
    ],
    # ...
}
```

## Usage Example

```python
from src.matching.engine import JobMatcher
from src.database.models import Resume, JobPosting

matcher = JobMatcher()
result = matcher.match(job_posting, resume)

print(f"Overall: {result.match_score}%")
print(f"Skills: {result.skills_score}%")
print(f"Experience: {result.experience_score}%")
print(f"Matching skills: {result.matching_skills}")
print(f"Skill gaps: {result.skill_gaps}")
```

## Configuration

In `config.yaml`:

```yaml
matching:
  weights:
    skills: 0.45      # Weight for skills match
    experience: 0.35  # Weight for experience match
    domains: 0.20     # Weight for domain match
  min_match_score: 0.6  # Minimum score to consider a match
```

## Related Skills

The matcher supports **related skills matching** with partial credit. When a job requires a skill that the resume doesn't have directly, but has a related skill, partial credit is given.

### How It Works

1. First, semantic similarity matching is attempted (full credit)
2. If no direct match, check if resume has a related skill (partial credit, default 0.7x)

### Configuration

Related skills are defined in `data/skill_relationships.json`:

```json
{
  "config": {
    "related_skill_weight": 0.7
  },
  "relationships": {
    "product_management": {
      "agile": ["scrum", "kanban", "lean", "sprint"],
      "product roadmap": ["product strategy", "prioritization"]
    }
  }
}
```

### Editing Relationships

To add or modify skill relationships:

1. Open `data/skill_relationships.json`
2. Add skills to the appropriate category
3. Changes take effect on next run (cached at startup)

Example - adding a new relationship:
```json
"technical": {
  "kubernetes": ["docker", "containerization", "devops"],
  "react": ["javascript", "frontend", "vue"]
}
```

### Match Details

The match details now include a `match_type` field:
- `"direct"`: Semantic similarity match (full credit)
- `"related"`: Related skill match (partial credit)

```python
{
  "Python": {
    "matched_skill": "Data Science",
    "similarity": 0.7,
    "match_type": "related",
    "credit": 0.7,
    "relationship": "python ↔ data science"
  }
}
```

## Dependencies

- `sentence-transformers`: NLP embeddings model
- `numpy`: Vector operations for similarity calculation
- `spacy`: Text processing (optional, for advanced extraction)
