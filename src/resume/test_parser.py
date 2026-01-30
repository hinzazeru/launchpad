"""Unit tests for resume parser."""

import pytest
import os
from src.resume.parser import (
    read_resume_file,
    extract_skills,
    extract_experience_years,
    extract_job_titles,
    extract_education,
    parse_resume,
)


@pytest.fixture
def sample_resume_path():
    """Get path to sample resume fixture."""
    return os.path.join(
        os.path.dirname(__file__),
        "../../tests/fixtures/sample_resume.txt"
    )


@pytest.fixture
def sample_resume_text():
    """Sample resume text for testing."""
    return """
    John Doe
    Senior Product Manager

    SUMMARY
    Product Manager with 5 years of experience in B2B SaaS. Expert in Agile, Scrum, and Product Strategy.

    EXPERIENCE
    Senior Product Manager, Tech Co, 2020-Present
    Product Manager, Startup Inc, 2018-2020

    SKILLS
    Product Management, Roadmapping, Stakeholder Management, A/B Testing, SQL, Jira, OKRs

    EDUCATION
    MBA, Business School, 2018
    BS, Computer Science, 2015
    """


def test_read_resume_file_txt(sample_resume_path):
    """Test reading a .txt resume file."""
    content = read_resume_file(sample_resume_path)
    assert isinstance(content, str)
    assert len(content) > 0
    assert "Product Manager" in content


def test_read_resume_file_invalid_extension():
    """Test that invalid file extensions raise ValueError."""
    with pytest.raises(ValueError, match="Only .txt and .md files are supported"):
        read_resume_file("resume.pdf")


def test_read_resume_file_not_found():
    """Test that missing files raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        read_resume_file("nonexistent.txt")


def test_extract_skills_default_keywords(sample_resume_text):
    """Test skill extraction with default PM keywords."""
    skills = extract_skills(sample_resume_text)

    assert isinstance(skills, list)
    assert len(skills) > 0
    # Should find these skills from the sample text
    assert any("Product Management" in s for s in skills)
    assert any("Agile" in s or "agile" in s.lower() for s in skills)
    assert any("Scrum" in s or "scrum" in s.lower() for s in skills)


def test_extract_skills_custom_keywords():
    """Test skill extraction with custom keywords."""
    text = "Experienced in Python, JavaScript, and React"
    custom_skills = ["Python", "JavaScript", "React", "Java"]

    skills = extract_skills(text, skill_keywords=custom_skills)

    assert "Python" in skills
    assert "JavaScript" in skills
    assert "React" in skills
    assert "Java" not in skills


def test_extract_skills_case_insensitive():
    """Test that skill extraction is case insensitive."""
    text = "Expert in AGILE and scrum methodologies"

    skills = extract_skills(text)

    # Should match regardless of case
    assert any(s for s in skills if "agile" in s.lower())
    assert any(s for s in skills if "scrum" in s.lower())


def test_extract_experience_years_explicit():
    """Test extracting explicitly stated years of experience."""
    test_cases = [
        ("5 years of experience", 5.0),
        ("10+ years experience", 10.0),
        ("3 yrs of experience", 3.0),
        ("7 years in product management", 7.0),
        ("Experience: 8 years", 8.0),
    ]

    for text, expected_years in test_cases:
        years = extract_experience_years(text)
        assert years == expected_years, f"Failed for: {text}"


def test_extract_experience_years_from_dates():
    """Test extracting experience from date ranges."""
    text = """
    Product Manager, Company A, 2020-2023
    Associate PM, Company B, 2018-2020
    """

    years = extract_experience_years(text)
    assert years is not None
    assert years >= 5.0  # 3 + 2 = 5 years


def test_extract_experience_years_with_present():
    """Test extracting experience with 'present' end date."""
    text = "Product Manager, 2020-Present"

    years = extract_experience_years(text)
    assert years is not None
    assert years >= 4.0  # 2020 to 2024


def test_extract_experience_years_not_found():
    """Test when no experience information is found."""
    text = "Just graduated from college"

    years = extract_experience_years(text)
    assert years is None


def test_extract_job_titles(sample_resume_text):
    """Test extracting job titles."""
    titles = extract_job_titles(sample_resume_text)

    assert isinstance(titles, list)
    assert len(titles) > 0
    # Should find PM titles
    assert any("Senior Product Manager" in t for t in titles)
    assert any("Product Manager" in t for t in titles)


def test_extract_job_titles_multiple():
    """Test extracting multiple job titles."""
    text = """
    Senior Product Manager (2020-Present)
    Product Manager (2018-2020)
    Associate Product Manager (2016-2018)
    """

    titles = extract_job_titles(text)

    assert "Senior Product Manager" in titles
    assert "Product Manager" in titles
    assert "Associate Product Manager" in titles


def test_extract_job_titles_abbreviations():
    """Test extracting abbreviated job titles."""
    text = "Currently working as APM, previously TPM"

    titles = extract_job_titles(text)

    assert "APM" in titles
    assert "TPM" in titles


def test_extract_education_degree_format():
    """Test extracting education with degree format."""
    text = """
    EDUCATION
    MBA, Stanford University, 2020
    BS Computer Science, UC Berkeley, 2016
    """

    education = extract_education(text)

    assert education is not None
    assert "MBA" in education or "mba" in education.lower()


def test_extract_education_various_degrees():
    """Test extracting different types of degrees."""
    test_cases = [
        ("MBA from Harvard", "mba"),
        ("Master of Business Administration", "master"),
        ("BS in Computer Science", "bs"),
        ("Ph.D. in Economics", "ph"),  # Will match "Ph.D."
    ]

    for text, expected in test_cases:
        education = extract_education(text)
        assert education is not None
        assert expected.lower() in education.lower()


def test_extract_education_not_found():
    """Test when no education information is found."""
    text = "Self-taught developer with coding skills"

    education = extract_education(text)
    # May be None when no degree patterns match
    assert education is None


def test_parse_resume_integration(sample_resume_path):
    """Test full resume parsing integration."""
    result = parse_resume(sample_resume_path)

    # Check structure
    assert 'skills' in result
    assert 'experience_years' in result
    assert 'job_titles' in result
    assert 'education' in result
    assert 'raw_text' in result

    # Check content
    assert isinstance(result['skills'], list)
    assert len(result['skills']) > 0

    assert result['experience_years'] is not None
    assert result['experience_years'] >= 5.0

    assert isinstance(result['job_titles'], list)
    assert len(result['job_titles']) > 0

    assert result['education'] is not None
    assert isinstance(result['raw_text'], str)


def test_parse_resume_invalid_file():
    """Test parsing with invalid file."""
    with pytest.raises(ValueError):
        parse_resume("resume.pdf")


def test_parse_resume_missing_file():
    """Test parsing with missing file."""
    with pytest.raises(FileNotFoundError):
        parse_resume("nonexistent.txt")
