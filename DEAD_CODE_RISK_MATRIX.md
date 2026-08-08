# Dead Code Risk Matrix

| Component / Target | Candidate For Deletion | Confidence | Risk if Removed | Recommended Action | Justification |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `scratch_*.py` files | Yes | 100% | **None** | **Delete** | Abandoned debug files. Not imported anywhere. |
| Unused Imports (Ruff F401) | Yes | 100% | **None** | **Clean** | Leftover `typing` declarations from Sprint 3 PyUpgrade modernization. |
| Unused Local Variables | No | 60% | **Medium** | **Keep** | Often required for API payloads, debugging loops, or Pydantic serialization definitions. |
| FastAPI Route Methods | No | 0% | **High** | **Keep** | Falsely flagged by Vulture. Removing them takes down the API. |
| Locust Test Classes | No | 0% | **High** | **Keep** | Falsely flagged by Vulture. Required for platform stress testing. |
