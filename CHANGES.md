# Local Modifications

This is a personal fork of [mcp-atlassian](https://github.com/rambom/mcp-atlassian) with custom modifications.

See git history for details (`git diff upstream/main`).

## Changes

- Add attachment tools for Jira and Confluence: `list_issue_attachments` / `download_attachment_to_file` (Jira) and `list_content_attachments` / `download_confluence_attachment_to_file` (Confluence) — list metadata and download attachments to local filesystem paths instead of returning base64-encoded EmbeddedResource for LLMs that do not support it.
