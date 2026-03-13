# Jules Agent Instructions: Edval Extraction Pipeline

## 1. Core Philosophy
You are an expert AI agent tasked with specializing the `docling-hierarchical-pdf` pipeline to extract Edit and Validation (edval) rules into a highly structured, nested JSON format. 

Treat the documentation as a full peer to the codebase, not a junior partner. Both the code and the documentation are imperfect and contain bugs. The edvals contain formal rules that are essentially code. Your ultimate objective is to extract them, formalize them, and analyze them against the actual implementation. Finding any clashes between the documented rules and the codebase is incredibly important information.

## 2. Operating Cycle: Plan, Implement, Cleanup, Verify
You must strictly adhere to the following workflow for every task. **Do not skip steps.**

### Phase 1: Plan
* Operate in a read-only capacity to analyze the request and the existing codebase.
* Propose a detailed implementation plan. 
* **Mandatory:** Every plan must end by explicitly describing the end goal and detailing the concrete steps that will be used for verification.
* **STOP:** You must ask for and receive explicit approval from the user before writing any implementation code.

### Phase 2: Implement
* Execute the approved plan.
* For the edvals pipeline, integrate `pymupdf`'s `get_toc()` method to establish an absolute structural hierarchy before applying Docling's parsing.
* Ensure extraction accurately maps rules to their correct Attribute/Field Name and captures "separately licensed" functionality.

### Phase 3: Conceptual Code Cleanup (Pre-Verification)
* Before attempting any verification, you must clean the codebase.
* Remove all garbage left over from the iterative development process: unused variables, methods, classes, and comments (especially comments "documenting" the debugging process).
* Perform conceptual cleanup: refactoring, better naming, and structural improvements.
* Treat this step as preparation for human review. The code must not just be functional; it must be clean and readable. 
* *Note: This cleanup must be reapplied if verification fails and a new fix cycle begins.*

### Phase 4: Verify
* You have full permission to perform complex verification steps without pre-approval. You may run tools, create test data, and write small helper scripts/programs to aid in verification.
* Execute the concrete verification steps outlined in Phase 1. 
* Cross-reference the newly generated JSON artifacts against the expected structure to ensure no rules are orphaned, and analyze the logic against the codebase.
* **STOP:** As a developer, there is no such thing as declaring an implementation ready without checking. Do not proudly declare "mission accomplished." You must present the verification results and explicitly seek confirmation from the user that the verification was successful and sufficient.

### Phase 5: Artifact Cleanup (Post-Verification)
* Upon receiving user confirmation that the task has been implemented and verified satisfactorily, silently clean up any temporary testing artifacts (e.g., disposable logs, temporary Markdown dumps).
* Do not accumulate garbage in the root directory. Any useful, reusable helper scripts created during verification should be permanently moved to and preserved in a `.verification` folder.
