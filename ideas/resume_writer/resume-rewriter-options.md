# Design Options: Resume Bullet Point Targeter

## Overview
This document outlines the design options for the new **Resume Bullet Point Targeter**. The goal is to build an On-Demand web interface that enables users to rewrite specific resume bullet points to better align with a target job description.

## 1. Architecture Recommendations ("The Stack")

Since the current system is purely Python (scripts + CLI), introducing a Web UI requires a strategic choice.

### Option A: Python-Native Web App (Recommended for Speed)
**Technology:** [Streamlit](https://streamlit.io/) or [NiceGUI](https://nicegui.io/)
**Why:** Keeps the entire codebase in Python. No need to build a separate API or manage a Node.js environment. Streamlit is designed exactly for this "Data + AI" workflow (Side-by-side text comparison, buttons, inputs).
*   **Pros:** Rapid development (days, not weeks). Direct access to existing Python classes (`GeminiClient`, `ResumeParser`).
*   **Cons:** UI is less customizable than raw React.

### Option B: Modern Web App (Recommended for UX/Polish)
**Technology:** Next.js (Frontend) + FastAPI (Backend)
**Why:** Delivers the "Premium" feel requested (glassmorphism, animations, complex state management).
*   **Pros:** Total control over UI/UX. Can implement complex drag-and-drop or rich text editing easily.
*   **Cons:** High complexity. Requires separating the current logic into an API server (FastAPI) and a frontend client. Two languages to maintain (Python + TypeScript).

### Recommendation
**Start with Option A (Streamlit)** to validate the logic and prompts. If the UX feels too limiting, upgrade to Option B. *However, knowing your preference for "Premium" design, Option B is the likely end-state, but Option A is the smart MVP.*

## 2. Core Logic & Challenges

You requested a **bullet-by-bullet** review. Here is the technical challenge to that approach and a proposed refinement.

### The Challenge: Contextual Integrity
*   **Issue:** Rewriting bullets in isolation (bullet #3 without knowing bullet #1) often leads to repetitive or disjointed text.
*   **Issue:** Matching specific bullets from a text file (`resume.txt`) back to their original location for replacement is fragile if using simple string matching (duplicates exist).

### Proposed Logic: "Role-Based" Contextual Rewriting
Instead of sending one bullet at a time to Gemini:
1.  **Parse:** Identify "Role Blocks" in the resume.
2.  **Analyze:** Send the *entire* Role Block + Job Description to Gemini.
3.  **Instruction:** "For the role of 'Product Manager at Company X', identify bullets that are weak matches (<90%). Rewrite them to better fit the JD keywords, but keep the core truth."
4.  **UI:** Display the results bullet-by-bullet, but the *generation* happened with full context.

## 3. Workflow Design

### Step 1: Selection
*   **UI:** A dashboard showing the "Jobs Database" (imported from Apify/Files).
*   **Action:** Click a "Tailor Resume" button on a specific job card.

### Step 2: Analysis (The "Magic")
*   User selects which Resume Role(s) to target (default: All recent).
*   System creates a prompt for Gemini:
    *   *Input:* JD + Resume Role Block.
    *   *Task:* Score alignment of each bullet. For low scores, generate 2-3 alternatives using JD language.
    *   *Output:* JSON structure mapping `original_bullet` -> [`suggestion_1`, `suggestion_2`].

### Step 3: The Review Interface (Side-by-Side)
*   **Left Column:** Original Resume segments.
*   **Right Column:** AI Suggestions.
    *   **High Match (>90%):** Shown in Green (No change needed).
    *   **Optimization Opportunity:** Shows 2-3 radio button options.
    *   **Action:** User selects an option or keeps original. Can also manually edit the selection.

### Step 4: Export & Save
*   System reconstructs the resume.
*   **File Name:** `Resume_Updated_[Company]_[Date].txt` (or `.md`).
*   **Feature:** "Diff View" to see exactly what changed before saving.

## 4. Prerequisites (The "Boring" Stuff)

To make this work reliably, we need to upgrade the data handling:
1.  **Structured Resume:** We must convert `resume.txt` into a structured format (JSON or Markdown with strict headers) internally so the code knows exactly which text belongs to "Experience A" vs "Experience B".
2.  **Database/State:** We need to store the "Draft" state of a tailoring session so you don't lose progress if you refresh the browser.

## 5. Security & Costs
*   **Gemini:** Analyzing a full resume + JD per role will consume more tokens.
*   **Optimization:** We will strip the JD to only "Requirements/Responsibilities" before sending it to reducing token usage.

## Decision Matrix

| Feature | Low Complexity | High Complexity (Premium) |
| :--- | :--- | :--- |
| **Interface** | Streamlit / Python | Next.js + FastAPI |
| **Resume Format** | Markdown Parsing | JSON Schema |
| **Rewriting** | Whole Block text replacement | Granular multi-option selection |

**My Recommendation:**
Building a full Next.js app for a single-user tool is overkill *unless* you plan to productize this for others. However, if "WOW factor" is a key metric for you personally, Option B (Next.js) is the way to go.
