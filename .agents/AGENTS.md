# WealthQuant Workspace Customization Rules

- **Workspace Path:** Always use `F:\ai-stock-platform` as the primary workspace path for all file reads, writes, modifications, and command executions. Do not use the `C:` drive copy.
- **Run Directory:** Always run commands (servers, test scripts, research pipelines) with the current working directory (`Cwd`) set to the corresponding subdirectory inside `F:\ai-stock-platform` (e.g., `F:\ai-stock-platform\backend` or `F:\ai-stock-platform\frontend`).
- **File Creations:** Always create new files and reports within `F:\ai-stock-platform` to ensure all data is consolidated in the main repository.
