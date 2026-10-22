# NorthStar Health Benefits — Privacy and Data Handling Standard (2026)
Document-ID: NSHB-SEC-PRIV-2026
Version: 2026.1

> SYNTHETIC DEMO DATA — fictional standard for demonstration. Not legal or compliance advice.

## S-01 Minimum Necessary

### S-01.1 Minimum Necessary Access
Systems and users access only the minimum member health information necessary for their function. Visit histories and authorization records are considered protected health information.

## S-02 Logging

### S-02.1 Log Content
Application logs must not contain member health information, clinical details or secrets. Logs may contain synthetic identifiers, counts, reason codes and request identifiers.

## S-03 Non-Production Data

### S-03.1 Synthetic Data in Non-Production
Non-production environments, demonstrations and simulations use synthetic data only. Real member data must never be loaded into demonstration systems.

## S-04 Artificial Intelligence Usage

### S-04.1 AI Decision Boundaries
AI systems may summarize, explain, retrieve evidence and recommend engineering actions. AI systems must not approve or deny claims, modify production systems or alter policy without human approval.

### S-04.2 Untrusted Content
Content retrieved from documents or uploaded by users is treated as untrusted data. Instructions embedded in such content must not be executed.
