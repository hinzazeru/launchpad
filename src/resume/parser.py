from typing import List, Dict, Optional, Any
import re
import json
from dataclasses import dataclass, field

@dataclass
class ResumeRole:
    company: str
    title: str
    duration: str
    bullets: List[str]
    raw_text: str  # The full text block for this role for context
    # Extended fields from JSON
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""
    technologies: List[str] = field(default_factory=list)
    bullet_metadata: List[Dict] = field(default_factory=list)  # Keywords, metrics per bullet

@dataclass
class ResumeStructure:
    summary: str
    roles: List[ResumeRole]
    education: str
    raw_text: str
    # Extended fields from JSON
    contact: Dict[str, str] = field(default_factory=dict)
    skills: Dict[str, List[str]] = field(default_factory=dict)
    certifications: List[Dict] = field(default_factory=list)
    projects: List[Dict] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_format: str = "text"  # "text" or "json"

class ResumeParser:
    """Parses a plain text or JSON resume into structured blocks for rewriting."""

    def __init__(self):
        pass

    def parse_json(self, json_data: dict) -> ResumeStructure:
        """Parse a JSON resume into ResumeStructure.

        Args:
            json_data: Parsed JSON dictionary

        Returns:
            ResumeStructure object
        """
        # Extract roles from experience
        roles = []
        for exp in json_data.get('experience', []):
            # Handle bullets - can be strings or objects with 'text' key
            bullets = []
            bullet_metadata = []
            for bullet in exp.get('bullets', []):
                if isinstance(bullet, str):
                    bullets.append(bullet)
                    bullet_metadata.append({})
                elif isinstance(bullet, dict):
                    bullets.append(bullet.get('text', ''))
                    bullet_metadata.append({
                        'keywords': bullet.get('keywords', []),
                        'metrics': bullet.get('metrics', {}),
                        'category': bullet.get('category', '')
                    })

            # Build raw text representation
            raw_lines = [exp.get('company', ''), exp.get('title', '')]
            if exp.get('duration'):
                raw_lines.append(exp.get('duration'))
            for b in bullets:
                raw_lines.append(f"- {b}")
            raw_text = '\n'.join(raw_lines)

            role = ResumeRole(
                company=exp.get('company', 'Unknown Company'),
                title=exp.get('title', 'Unknown Title'),
                duration=exp.get('duration', ''),
                bullets=bullets,
                raw_text=raw_text,
                location=exp.get('location', ''),
                start_date=exp.get('start_date', ''),
                end_date=exp.get('end_date', ''),
                description=exp.get('description', ''),
                technologies=exp.get('technologies', []),
                bullet_metadata=bullet_metadata
            )
            roles.append(role)

        # Build education string from education array
        education_parts = []
        for edu in json_data.get('education', []):
            parts = []
            if edu.get('degree') and edu.get('field'):
                parts.append(f"{edu['degree']} in {edu['field']}")
            elif edu.get('degree'):
                parts.append(edu['degree'])
            if edu.get('institution'):
                parts.append(edu['institution'])
            if edu.get('graduation_date'):
                parts.append(edu['graduation_date'])
            if parts:
                education_parts.append(' - '.join(parts))
        education_str = '\n'.join(education_parts)

        # Build full raw text
        raw_text = self._json_to_text(json_data)

        return ResumeStructure(
            summary=json_data.get('summary', ''),
            roles=roles,
            education=education_str,
            raw_text=raw_text,
            contact=json_data.get('contact', {}),
            skills=json_data.get('skills', {}),
            certifications=json_data.get('certifications', []),
            projects=json_data.get('projects', []),
            metadata=json_data.get('metadata', {}),
            source_format='json'
        )

    def _json_to_text(self, json_data: dict) -> str:
        """Convert JSON resume to plain text representation."""
        lines = []

        # Summary
        if json_data.get('summary'):
            lines.append(json_data['summary'])
            lines.append('')

        # Experience
        lines.append('Experience')
        lines.append('')
        for exp in json_data.get('experience', []):
            lines.append(exp.get('company', ''))
            lines.append(exp.get('title', ''))
            if exp.get('duration'):
                lines.append(exp['duration'])
            for bullet in exp.get('bullets', []):
                if isinstance(bullet, str):
                    lines.append(f"- {bullet}")
                elif isinstance(bullet, dict):
                    lines.append(f"- {bullet.get('text', '')}")
            lines.append('')

        # Education
        lines.append('Education')
        for edu in json_data.get('education', []):
            parts = []
            if edu.get('degree'):
                parts.append(edu['degree'])
            if edu.get('field'):
                parts.append(f"in {edu['field']}")
            if edu.get('institution'):
                parts.append(f"- {edu['institution']}")
            if edu.get('graduation_date'):
                parts.append(f"({edu['graduation_date']})")
            lines.append(' '.join(parts))

        return '\n'.join(lines)

    def parse_json_string(self, json_string: str) -> ResumeStructure:
        """Parse a JSON string into ResumeStructure.

        Args:
            json_string: JSON string content

        Returns:
            ResumeStructure object
        """
        json_data = json.loads(json_string)
        return self.parse_json(json_data)

    def parse_auto(self, content: str) -> ResumeStructure:
        """Auto-detect format and parse accordingly.

        Args:
            content: Resume content (JSON string or plain text)

        Returns:
            ResumeStructure object
        """
        content = content.strip()

        # Try JSON first if it looks like JSON
        if content.startswith('{'):
            try:
                return self.parse_json_string(content)
            except json.JSONDecodeError:
                pass  # Fall through to text parsing

        # Default to text parsing
        return self.parse(content)
        
    def parse(self, text: str) -> ResumeStructure:
        """Parse raw resume text into a structured object."""
        # Normalize line endings
        text = text.replace('\r\n', '\n')
        
        # Split into main sections (simplistic approach based on known headers)
        # We assume "Experience" and "Education" are the main delimiters
        
        # Find indices
        summary_end = 0
        exp_start = 0
        edu_start = len(text)
        
        # regex for headers (case insensitive, standalone lines)
        exp_match = re.search(r'(?i)^Experience\s*$', text, re.MULTILINE)
        edu_match = re.search(r'(?i)^Education\s*$', text, re.MULTILINE)
        
        if exp_match:
            summary_end = exp_match.start()
            exp_start = exp_match.end()
            
        if edu_match:
            edu_start = edu_match.start()
            
        summary_section = text[:summary_end].strip()
        experience_section = text[exp_start:edu_start].strip()
        education_section = text[edu_start:].strip()
        
        roles = self._parse_experience_section(experience_section)
        
        return ResumeStructure(
            summary=summary_section,
            roles=roles,
            education=education_section,
            raw_text=text
        )
    
    def _parse_experience_section(self, text: str) -> List[ResumeRole]:
        """
        Parses the experience section into roles.
        Assumes a format where roles are separated by newlines and start with Company/Title info.
        """
        roles = []
        
        # Split by double newlines to find "blocks"
        # This is heuristics-based. A better way might be to look for the bullet points.
        
        # Strategy: Iterate through lines.
        # If a line starts with '-', it's a bullet.
        # Lines above bullets are "Header Info" (Company, Title, Date).
        # When we hit a new non-bullet line after a block of bullets, it's a new role.
        
        lines = text.split('\n')
        current_role_lines = []
        all_roles_lines = []
        
        # Group lines into role chunks
        # A chunk ends when we verify we have bullets and then hit a line that looks like a new header
        # OR we use spacing.
        
        # Simpler heuristic for this user's resume:
        # Roles seem to be separated by empty lines.
        # Let's split by double newlines `\n\n` and check if the block contains bullets.
        
        blocks = re.split(r'\n\s*\n', text)
        
        for block in blocks:
            if not block.strip():
                continue
                
            # Check if block has bullets
            if '-' in block or '•' in block:
                parsed_role = self._parse_single_role_block(block)
                if parsed_role:
                    roles.append(parsed_role)
            else:
                # Might be a stray header or part of the previous role?
                # For now, ignore non-bullet blocks in experience section
                pass
                
        return roles

    def _parse_single_role_block(self, block_text: str) -> Optional[ResumeRole]:
        """Parse a single block of text representing one role."""
        lines = [l.strip() for l in block_text.split('\n') if l.strip()]
        
        bullets = []
        header_lines = []
        
        for line in lines:
            if line.startswith('-') or line.startswith('•'):
                # Clean the bullet char
                content = re.sub(r'^[-•]\s*', '', line)
                bullets.append(content)
            else:
                header_lines.append(line)
        
        if not bullets:
            return None
            
        # Heuristics for header: 
        # Line 0: Company
        # Line 1: Title
        # Line 2: Date
        # (This varies, but let's try to map it)
        
        company = header_lines[0] if len(header_lines) > 0 else "Unknown Company"
        title = header_lines[1] if len(header_lines) > 1 else "Unknown Title"
        duration = header_lines[2] if len(header_lines) > 2 else ""
        
        # Fallback: if duration is missing but title has dates? 
        # We'll stick to this simple mapping for now given the resume.txt sample.
        
        return ResumeRole(
            company=company,
            title=title,
            duration=duration,
            bullets=bullets,
            raw_text=block_text
        )

    def extract_domains(self, text: str) -> List[Dict]:
        """Extract suggested domains from resume text.

        Scans the resume text for domain keywords and suggests relevant domains
        based on the candidate's experience.

        Args:
            text: Resume text content

        Returns:
            List of domain suggestions, each with:
                - domain: Domain name (e.g., "fintech", "ecommerce")
                - confidence: Confidence score (0.0-1.0)
                - evidence: Where/why this domain was detected
        """
        from src.matching.skill_extractor import load_domain_expertise

        if not text:
            return []

        expertise_data = load_domain_expertise()
        domains = expertise_data.get("domains", {})

        text_lower = text.lower()
        suggestions = []
        found_domains: Dict[str, Dict] = {}  # domain -> {count, keywords}

        # Search through all domain categories
        for category, category_domains in domains.items():
            for domain_name, domain_data in category_domains.items():
                keywords = domain_data.get("keywords", [])
                matched_keywords = []

                for keyword in keywords:
                    keyword_lower = keyword.lower()
                    # Use word boundary matching
                    pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                    matches = re.findall(pattern, text_lower)

                    if matches:
                        matched_keywords.append(keyword)

                if matched_keywords:
                    if domain_name in found_domains:
                        found_domains[domain_name]['count'] += len(matched_keywords)
                        found_domains[domain_name]['keywords'].extend(matched_keywords)
                    else:
                        found_domains[domain_name] = {
                            'count': len(matched_keywords),
                            'keywords': matched_keywords,
                            'category': category,
                            'description': domain_data.get('description', '')
                        }

        # Build suggestions with confidence scores
        for domain_name, data in found_domains.items():
            # Confidence based on number of matching keywords
            keyword_count = len(set(data['keywords']))  # Unique keywords
            if keyword_count >= 3:
                confidence = 0.9
            elif keyword_count >= 2:
                confidence = 0.75
            else:
                confidence = 0.6

            suggestions.append({
                'domain': domain_name,
                'confidence': confidence,
                'category': data['category'],
                'evidence': f"Found keywords: {', '.join(set(data['keywords'])[:3])}",
                'description': data['description']
            })

        # Sort by confidence descending
        suggestions.sort(key=lambda x: x['confidence'], reverse=True)

        return suggestions


# Factory for easy import
def get_parser():
    return ResumeParser()
