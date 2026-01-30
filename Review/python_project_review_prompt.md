# Python Project Code Review Prompt

You are an expert Python code reviewer specializing in CLI tools and Telegram bot development. Your task is to perform a comprehensive code review of a Python project and output your findings to a markdown file.

## Project Context

- **Project Type:** CLI tool with Telegram bot integration
- **Primary Focus Areas:** Performance considerations, dependency management, and error handling
- **Secondary Focus:** Telegram-specific best practices and general Python code quality

## Instructions

1. **Explore the codebase** located at `/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch`. Start by examining the project structure, then review all Python files, documentation files, configuration files, and dependency specifications (requirements.txt, pyproject.toml, setup.py, Pipfile, etc.).

2. **Analyze the codebase** against the criteria outlined below.

3. **Generate a detailed review report** and save it as a markdown file at `'/Users/hinza/Library/CloudStorage/OneDrive-Personal/[20] Project/ClaudeProjects/LinkedInJobSearch/Review/output_review_report.md`.

---

## Review Criteria

### 1. Performance Considerations

Evaluate the following and identify issues or improvement opportunities:

**Response Latency**
- Blocking operations in bot command handlers
- Synchronous I/O where async would be appropriate
- Unnecessary sequential operations that could be parallelized
- Database or API calls without connection pooling

**Memory Usage**
- Large data structures held in memory unnecessarily
- Missing generators/iterators where appropriate
- Memory leaks (unclosed resources, circular references)
- Inefficient data structures for the use case

**Concurrency Handling**
- Proper use of async/await patterns
- Thread safety issues with shared state
- Race conditions
- Missing or improper use of locks/semaphores
- Connection pool exhaustion risks

**General Performance Hygiene**
- Inefficient algorithms or data access patterns
- Repeated computations that could be cached
- Unnecessary object creation in hot paths
- Missing indexing considerations for data lookups

**Telegram-Specific Performance**
- Webhook vs polling efficiency for the use case
- Proper handling of Telegram rate limits
- Efficient media/file handling
- Update queue management

---

### 2. Dependency Management

Analyze all dependency-related files and evaluate:

**Security Vulnerabilities**
- Known CVEs in current dependency versions
- Dependencies with poor security track records
- Transitive dependencies with known issues

**Outdated Packages**
- Dependencies significantly behind current stable versions
- Deprecated packages still in use
- Packages no longer maintained

**Unnecessary/Bloated Dependencies**
- Dependencies that could be replaced with standard library
- Heavy dependencies used for minimal functionality
- Duplicate functionality across dependencies

**License Compatibility**
- Licenses incompatible with project goals
- Copyleft licenses that may cause issues
- Missing license declarations

**Dependency Hygiene**
- Pinned vs unpinned versions
- Missing dependency specification files
- Dev vs production dependency separation
- Dependency resolution conflicts

---

### 3. Error Handling

Review all error handling patterns:

**Exception Handling Quality**
- Bare `except:` clauses
- Overly broad exception catching
- Swallowed exceptions (catch and ignore)
- Missing exception handling in critical paths
- Improper exception chaining

**Error Recovery**
- Missing retry logic for transient failures
- No graceful degradation strategies
- Missing circuit breaker patterns for external services
- Incomplete rollback on partial failures

**Error Reporting & Logging**
- Insufficient error context in logs
- Missing stack traces where needed
- Inconsistent logging levels
- Sensitive data in error messages

**User-Facing Errors**
- Cryptic error messages to end users
- Missing error codes or categories
- No guidance for error resolution
- Inconsistent error response formats

**Telegram-Specific Error Handling**
- Handling of Telegram API errors
- Network timeout handling
- Rate limit error recovery
- Webhook failure handling

---

### 4. Telegram Bot Best Practices

Evaluate adherence to Telegram bot development standards:

- Proper use of bot API (python-telegram-bot, aiogram, or other library)
- Conversation/state management patterns
- Inline keyboard and callback handling
- Media handling efficiency
- User session management
- Command structure and help documentation
- Privacy and data handling

---

### 5. General Python Code Quality

Note significant issues in:

- PEP 8 compliance (major violations only)
- Type hints usage and correctness
- Code organization and modularity
- Documentation and docstrings
- Test coverage gaps (if tests exist)

---

## Output Format

Generate the review report with the following structure:

```markdown
# Code Review Report: [Project Name]

**Review Date:** [Current Date]
**Reviewer:** AI Code Review Assistant

## Executive Summary

[2-3 paragraph overview of findings, overall health assessment, and top priorities]

## Findings by Effort Level

### Quick Wins (Low Effort, High Impact)

#### [Issue Title]
- **Severity:** Critical | High | Medium | Low
- **Category:** Performance | Dependencies | Error Handling | Telegram Best Practices | Code Quality
- **Location:** `path/to/file.py` (lines X-Y)
- **Description:** [Clear explanation of the issue]
- **Impact:** [What problems this causes or risks it introduces]
- **Recommendation:** [Specific actionable fix]
- **Code Example (if applicable):**
  ```python
  # Before
  [problematic code]
  
  # After
  [suggested improvement]
  ```

[Repeat for each quick win issue]

---

### Medium Effort Improvements

[Same structure as above for medium effort items]

---

### Major Refactoring (High Effort)

[Same structure as above for high effort items]

---

## Dependency Audit Summary

| Package | Current Version | Latest Version | Security Issues | Status |
|---------|-----------------|----------------|-----------------|--------|
| [name]  | [version]       | [version]      | [CVE IDs/None]  | [OK/Update/Replace/Remove] |

## Metrics Summary

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| Performance | X | X | X | X | X |
| Dependencies | X | X | X | X | X |
| Error Handling | X | X | X | X | X |
| Telegram Practices | X | X | X | X | X |
| Code Quality | X | X | X | X | X |
| **Total** | X | X | X | X | X |

## Recommended Action Plan

1. **Immediate (This Week):** [Critical and high-severity quick wins]
2. **Short-term (This Month):** [Remaining quick wins + medium effort high-severity]
3. **Medium-term (This Quarter):** [Medium effort items]
4. **Long-term (Backlog):** [Major refactoring items]

## Appendix

### Files Reviewed
- [List of all files examined]

### Tools/References Used
- [Any external references consulted]
```

---

## Severity Definitions

- **Critical:** Security vulnerabilities, data loss risks, or complete feature breakage
- **High:** Significant performance degradation, reliability issues, or major best practice violations
- **Medium:** Suboptimal patterns that affect maintainability or minor performance/reliability concerns
- **Low:** Code quality improvements, minor optimizations, or style suggestions

---

## Execution Instructions

1. Begin by listing the project directory structure
2. Read and analyze each relevant file
3. Cross-reference dependencies against known vulnerability databases conceptually
4. Compile findings into the report format above
5. Save the report to the specified output path
6. Confirm completion and summarize key statistics

**Begin the review now.**
