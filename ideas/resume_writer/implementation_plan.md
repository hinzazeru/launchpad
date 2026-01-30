# Implementation Plan: Resume Bullet Point Rewriter (Streamlit)

## Goal
Build a local, interactive Web UI using **Streamlit** that allows the user to select a job description and rewrite specific resume bullet points using Gemini. The system will support "Undo" capabilities and export to both `.txt` and `.pdf`.

## User Review Required
> [!IMPORTANT]
> **Cloud Deployment:** Moving to the cloud (e.g., Railway/Render) is easy with Streamlit, but requires that your `data/` and `resumes/` folders be persistent. In a ephemeral cloud container, files saved to disk disappear on restart unless a dedicated "Volume" is attached. We will design the code to be cloud-ready, but for now, it will run locally on your Mac.

> [!NOTE]
> **PDF Export:** We will use `reportlab` or `fpdf` to generate PDFs. This adds a new dependency. The PDF will be a "Clean" version (simple formatting), not a complex designer layout.

## Proposed Changes

### 1. New Dependencies
*   `streamlit`: For the Web UI.
*   `fpdf2` or `markdown-pdf`: For generating PDF exports.

### 2. File System Changes
*   Create `resumes/` directory.
*   Move `resume.txt` to `resumes/default_resume.txt`.
*   The system will scan this folder for all `.txt` and `.md` files to populate the "Resume Selector".

### 3. Core Logic Updates

#### [NEW] `src/resume/parser.py`
Create a robust parser to chunk the resume into "Role Blocks".
*   `parse_resume_structure(text)`: Returns a structured dictionary:
    ```json
    {
      "summary": "...",
      "experience": [
        {
          "id": "exp_1",
          "company": "Company A",
          "title": "PM",
          "raw_text": "...",
          "bullets": ["bullet 1", "bullet 2"]
        }
      ],
      "education": "..."
    }
    ```

#### [MODIFY] `src/integrations/gemini_client.py`
Add methods for the rewriting logic.
*   `rewrite_bullet_points(job_description, role_text)`:
    *   **Input:** The full JD text and the specific Role block from the resume.
    *   **Prompt:** "Analyze these bullet points against the JD. Identify weak matches (<90%). For those, generate 2-3 better alternatives using JD keywords. Return JSON."

### 3. User Interface (Streamlit)

#### [NEW] `src/web/app.py`
The main entry point for the UI.

**Layout:**
*   **Sidebar:**
    *   **Job Selector:** Dropdown to pick a job from the database/Apify logs.
    *   **Resume Selector:** Dropdown to pick a specific resume version from `resumes/*.txt`.
*   **Main Area:**
    *   **Header:** Job Title & Company (with Match Score).
    *   **Controls:**
        *   **Persona Selector:** Dropdown (Standard, Executive, Technical).
        *   **Cost Ticker:** Display estimated API cost for the current session.
        *   **History Slider:** Slider to revert to previous states ("Time Travel").
    *   **Review Mode:**
        *   Iterate through each "Role Block".
        *   **Comparison Card (Side-by-Side):**
            *   *Left:* Original Bullet.
            *   *Right:* AI Suggestions (Natural Flow - avoiding keyword stuffing).
            *   *Edit:* Text area to manually tweak.
*   **Footer / Floating Action Bar:**
    *   **preview:** See the assembled document.
    *   **Save:** Buttons for "Download .txt" and "Download .pdf".

### 4. Data persistence (Session State)
*   Use `st.session_state` to track changes *before* saving.
*   this enables the **Undo** feature: The UI just renders the current state of variables. "Undoing" is just resetting a variable to its previous value.

## Verification Plan

### Automated Tests
*   Test the `ResumeParser` against `resume.txt` to ensure it correctly identifies all roles and bullets.
*   Test `GeminiClient` response structure (mocked) to ensure it returns valid JSON for the UI.

### Manual Verification
1.  **Launch:** Run `streamlit run src/web/app.py`.
2.  **Select Job:** Pick a job from the existing `dataset.json` or logs.
3.  **Generate:** Click "Analyze & Rewrite".
4.  **Interact:** Select different options for 2-3 bullets.
5.  **Export:** Click "Save as PDF" and verify the file is created and readable.
