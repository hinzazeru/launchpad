"""Resume exporter module for generating tailored resume files.

Handles the creation of modified resume files with user-selected bullet changes.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from src.resume.parser import ResumeParser, ResumeStructure

logger = logging.getLogger(__name__)

# Default output directory
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "tailored_resumes"


@dataclass
class BulletChange:
    """Represents a single bullet point change."""
    original: str
    replacement: str
    change_type: str  # 'original', 'suggestion', 'custom'


@dataclass
class ExportResult:
    """Result of exporting a tailored resume."""
    filename: str
    filepath: Path
    content: str
    changes_made: int
    roles_modified: int


class ResumeExporter:
    """Exports tailored resumes with user-selected bullet changes."""

    def __init__(self, output_dir: Path = None):
        """Initialize the exporter.

        Args:
            output_dir: Directory for output files. Defaults to output/tailored_resumes/
        """
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.parser = ResumeParser()

    def export(
        self,
        resume_text: str,
        selections: Dict[str, List[BulletChange]],
        company: str,
        job_title: str = ""
    ) -> ExportResult:
        """Export a tailored resume with selected changes.

        Args:
            resume_text: Original resume text
            selections: Dict mapping role_key to list of BulletChange objects
            company: Target company name (used in filename)
            job_title: Optional job title for reference

        Returns:
            ExportResult with file details
        """
        # Parse original resume
        structure = self.parser.parse_auto(resume_text)

        # Build new content
        content = self._build_content(structure, selections)

        # Generate filename
        filename = self._generate_filename(company)
        filepath = self.output_dir / filename

        # Write file
        with open(filepath, 'w') as f:
            f.write(content)

        # Count changes
        changes_made = sum(
            1 for bullets in selections.values()
            for b in bullets if b.change_type != 'original'
        )
        roles_modified = sum(
            1 for bullets in selections.values()
            if any(b.change_type != 'original' for b in bullets)
        )

        logger.info(f"Exported tailored resume: {filename} ({changes_made} changes)")

        return ExportResult(
            filename=filename,
            filepath=filepath,
            content=content,
            changes_made=changes_made,
            roles_modified=roles_modified
        )

    def _build_content(
        self,
        structure: ResumeStructure,
        selections: Dict[str, List[BulletChange]]
    ) -> str:
        """Build the tailored resume content.

        Args:
            structure: Parsed resume structure
            selections: Bullet selections by role

        Returns:
            New resume content as string
        """
        lines = []

        # Summary
        if structure.summary:
            lines.append(structure.summary)
            lines.append("")

        # Experience header
        lines.append("Experience")
        lines.append("")

        # Process each role
        for role in structure.roles:
            role_key = f"{role.company}_{role.title}"

            # Role header
            lines.append(role.company)
            lines.append(role.title)
            if role.duration:
                lines.append(role.duration)

            # Bullets
            if role_key in selections:
                for change in selections[role_key]:
                    lines.append(f"- {change.replacement}")
            else:
                for bullet in role.bullets:
                    lines.append(f"- {bullet}")

            lines.append("")

        # Education
        if structure.education:
            lines.append(structure.education)

        return "\n".join(lines)

    def _generate_filename(self, company: str) -> str:
        """Generate a unique filename for the export.

        Args:
            company: Company name

        Returns:
            Filename string
        """
        safe_company = "".join(c if c.isalnum() else "_" for c in company)
        safe_company = safe_company[:30]  # Limit length
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"Resume_Tailored_{safe_company}_{date_str}.txt"

    def generate_diff(
        self,
        selections: Dict[str, List[BulletChange]]
    ) -> List[Dict]:
        """Generate a diff view of changes.

        Args:
            selections: Bullet selections by role

        Returns:
            List of change dictionaries for display
        """
        changes = []

        for role_key, bullets in selections.items():
            for bullet in bullets:
                if bullet.change_type != 'original':
                    changes.append({
                        'role': role_key.replace('_', ' @ ', 1),
                        'original': bullet.original,
                        'new': bullet.replacement,
                        'type': bullet.change_type
                    })

        return changes

    def export_markdown(
        self,
        resume_text: str,
        selections: Dict[str, List[BulletChange]],
        company: str
    ) -> ExportResult:
        """Export tailored resume as Markdown format.

        Args:
            resume_text: Original resume text
            selections: Bullet selections by role
            company: Target company name

        Returns:
            ExportResult with markdown content
        """
        structure = self.parser.parse_auto(resume_text)
        lines = []

        # Summary as intro
        if structure.summary:
            lines.append(structure.summary)
            lines.append("")

        # Experience section
        lines.append("## Experience")
        lines.append("")

        for role in structure.roles:
            role_key = f"{role.company}_{role.title}"

            lines.append(f"### {role.title}")
            lines.append(f"**{role.company}**")
            if role.duration:
                lines.append(f"*{role.duration}*")
            lines.append("")

            if role_key in selections:
                for change in selections[role_key]:
                    lines.append(f"- {change.replacement}")
            else:
                for bullet in role.bullets:
                    lines.append(f"- {bullet}")

            lines.append("")

        # Education
        if structure.education:
            lines.append("## Education")
            lines.append("")
            lines.append(structure.education)

        content = "\n".join(lines)

        # Generate filename
        safe_company = "".join(c if c.isalnum() else "_" for c in company)[:30]
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Resume_Tailored_{safe_company}_{date_str}.md"
        filepath = self.output_dir / filename

        with open(filepath, 'w') as f:
            f.write(content)

        changes_made = sum(
            1 for bullets in selections.values()
            for b in bullets if b.change_type != 'original'
        )

        return ExportResult(
            filename=filename,
            filepath=filepath,
            content=content,
            changes_made=changes_made,
            roles_modified=sum(1 for b in selections.values() if any(x.change_type != 'original' for x in b))
        )


def get_exporter(output_dir: Path = None) -> ResumeExporter:
    """Factory function to get a ResumeExporter instance.

    Args:
        output_dir: Optional custom output directory

    Returns:
        ResumeExporter instance
    """
    return ResumeExporter(output_dir=output_dir)
