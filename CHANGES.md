# Local Modifications

This is a personal fork of [mcp-atlassian](https://github.com/rambom/mcp-atlassian) with custom modifications.

See git history for details (`git diff upstream/main`).

## Changes

- Add attachment tools for Jira and Confluence: `list_issue_attachments` / `download_attachment_to_file` (Jira) and `list_content_attachments` / `download_confluence_attachment_to_file` (Confluence) — list metadata and download attachments to local filesystem paths instead of returning base64-encoded EmbeddedResource for LLMs that do not support it.
- Add `description_format` (`markdown` by default, `wiki` for raw Server/Data Center markup) to `jira_get_issue`, `jira_create_issue` and `jira_update_issue`. Reading with `wiki` and writing back with `wiki` preserves the stored formatting instead of round-tripping through Markdown, which used to mangle `{code}` blocks, headings and escaped characters. The option is rejected on Jira Cloud, where descriptions are stored as ADF.
- Add `content_format` (`markdown` by default, `wiki` for raw Server/Data Center markup) to `jira_add_comment` and `jira_edit_comment` for the same reason.
- Add `jira_delete_comment` so a comment can be removed through MCP instead of a direct REST call.
- Return the `renderedFields` expansion in `jira_get_issue` output (description, environment and comment HTML) when `expand=renderedFields` is requested; previously the expansion was accepted but dropped.
- Add a `compact` mode to `jira_get_project_components` that returns only id, name and lead display name; the full response includes avatars and nested objects and can reach hundreds of kilobytes.
- Accept loosely spelled issue link type names in `jira_create_issue_link` (`Relates` for `Relate`, case-insensitive, singular/plural) and report the available names when no match exists.
- Classify the fork-only tool arguments (`attachment_id`, `destination_path`, `overwrite`) in the scope guard so the argument-classification check passes for the attachment download tools.
