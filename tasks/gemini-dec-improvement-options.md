# Performance and Scalability Improvement Tasks

Here are the proposed tasks to improve the performance and scalability of the application. Please review each task, and I will await your instruction on which one to implement.

---

### Task 1.0: Optimize Database Operations

This task focuses on resolving database performance bottlenecks caused by inefficient query patterns (N+1 problems).

*   **Task 1.1: Implement Bulk Insertion Logic in `crud.py`**
    *   **Problem:** The current implementation inserts new jobs and match results one by one in a loop, resulting in a large number of separate database transactions.
    *   **Solution:** Create new functions in `src/database/crud.py` (e.g., `bulk_create_job_postings`, `bulk_create_match_results`) that utilize SQLAlchemy's `bulk_insert_mappings` method. This allows multiple records to be inserted in a single, efficient transaction.

*   **Task 1.2: Add Composite Index to `JobPosting` Table**
    *   **Problem:** The database table for job postings lacks an index on the columns used for duplicate checking (`title`, `company`). This leads to slow full-table scans.
    *   **Solution:** Add a composite unique index to the `(title, company)` columns in the `JobPosting` model located in `src/database/models.py`. A database migration will be required to apply this change.

*   **Task 1.3: Refactor Importer to Use Bulk Operations**
    *   **Problem:** The data importer at `src/importers/api_importer.py` checks for duplicates and inserts new jobs individually, triggering the N+1 problem.
    *   **Solution:** Modify the `import_jobs` function. First, it will fetch the `(title, company)` of all existing jobs into a Python `set` in a single query. Then, it will use this set to perform fast, in-memory duplicate checks before inserting all new jobs using the `bulk_create_job_postings` function from Task 1.1.

*   **Task 1.4: Refactor Matching Engine to Use Bulk Insert**
    *   **Problem:** The `save_match_results` function in `src/matching/engine.py` inserts each match result individually.
    *   **Solution:** Update the `save_match_results` function to collect all new `MatchResult` objects into a list and insert them all at once using the new `bulk_create_match_results` function from Task 1.1.

---

### Task 2.0: Parallelize CPU-Bound Matching Engine

This task addresses the primary computational bottleneck in the application.

*   **Task 2.1: Parallelize Job Matching Loop**
    *   **Problem:** The job matching loop in `src/matching/engine.py` is sequential. Since the skill matching logic is CPU-bound (due to sentence-transformer model encoding), the application cannot take advantage of multi-core processors.
    *   **Solution:** Refactor the `match_jobs` function in `src/matching/engine.py` to use a `concurrent.futures.ProcessPoolExecutor`. This will distribute the processing of jobs across multiple CPU cores, significantly speeding up the overall matching time.

---

### Task 3.0: Parallelize I/O-Bound Job Fetching (Optional)

This task improves the efficiency of fetching data from external APIs.

*   **Task 3.1: Concurrently Fetch Jobs from API**
    *   **Problem:** If the application is configured to run multiple job searches (e.g., for different keywords), it executes them one after another. The process is slowed down by waiting for each network request to complete.
    *   **Solution:** Refactor the job fetching logic in `src/importers/api_importer.py` to use a `concurrent.futures.ThreadPoolExecutor`. This will allow multiple API calls to run concurrently, overlapping the network wait times and reducing the total data retrieval time.
