"""Tests for the fork-only extensions to the Jira integration.

Covers the additions that keep the MCP server usable without falling back to
direct REST calls:

* ``description_format`` on get/create/update (raw wiki markup round trip);
* ``content_format`` on add/edit comment;
* ``jira_delete_comment``;
* loose issue link type names;
* the compact project components mode;
* the ``renderedFields`` expansion.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from mcp_atlassian.jira import JiraFetcher
from mcp_atlassian.jira.comments import CommentsMixin
from mcp_atlassian.jira.links import LinksMixin
from mcp_atlassian.models.jira.issue import JiraIssue
from mcp_atlassian.models.jira.link import JiraIssueLinkType


def _issue_payload(description: str) -> dict:
    """Build a minimal Jira issue response with the given description."""
    return {
        "id": "1",
        "key": "TEST-1",
        "fields": {
            "summary": "Summary",
            "description": description,
            "status": {"name": "Open"},
            "issuetype": {"name": "Task"},
            "created": "2024-01-01T00:00:00.000+0000",
            "updated": "2024-01-01T00:00:00.000+0000",
        },
    }


@pytest.fixture
def server_config(jira_config_factory):
    """Jira Server/Data Center configuration (not atlassian.net)."""
    return jira_config_factory(url="https://jira.example.com")


@pytest.fixture
def issues_mixin(server_config):
    """JiraFetcher with mocked API client and converters."""
    with patch("atlassian.Jira") as mock_jira_class:
        mock_jira_class.return_value = MagicMock()
        mixin = JiraFetcher(config=server_config)
    mixin.jira = MagicMock()
    mixin.preprocessor = Mock()
    mixin._clean_text = Mock(side_effect=lambda text: f"MD:{text}")
    mixin._markdown_to_jira = Mock(side_effect=lambda text: f"WIKI:{text}")
    return mixin


class TestDescriptionFormat:
    """description_format keeps the stored wiki markup intact."""

    def test_get_issue_wiki_returns_raw_description(self, issues_mixin):
        issues_mixin.jira.get_issue.return_value = _issue_payload("h2. Raw *wiki*")

        issue = issues_mixin.get_issue("TEST-1", description_format="wiki")

        assert issue.description == "h2. Raw *wiki*"
        issues_mixin._clean_text.assert_not_called()

    def test_get_issue_markdown_is_the_default(self, issues_mixin):
        issues_mixin.jira.get_issue.return_value = _issue_payload("h2. Raw")

        issue = issues_mixin.get_issue("TEST-1")

        assert issue.description == "MD:h2. Raw"
        issues_mixin._clean_text.assert_called_once_with("h2. Raw")

    def test_get_issue_rejects_unknown_format(self, issues_mixin):
        with pytest.raises(ValueError, match="Unsupported description_format"):
            issues_mixin.get_issue("TEST-1", description_format="html")

    def test_get_issue_rejects_wiki_on_cloud(self, issues_mixin, jira_config_factory):
        issues_mixin.config = jira_config_factory(url="https://test.atlassian.net")

        with pytest.raises(ValueError, match="only supported on Jira"):
            issues_mixin.get_issue("TEST-1", description_format="wiki")

    def test_update_issue_wiki_skips_conversion(self, issues_mixin):
        issues_mixin.jira.get_issue.return_value = _issue_payload("h2. Raw")

        issues_mixin.update_issue(
            "TEST-1",
            fields={"description": "h2. Raw *wiki*"},
            description_format="wiki",
        )

        payload = issues_mixin.jira.update_issue.call_args.kwargs["update"]
        assert payload["fields"]["description"] == "h2. Raw *wiki*"
        issues_mixin._markdown_to_jira.assert_not_called()

    def test_update_issue_markdown_converts(self, issues_mixin):
        issues_mixin.jira.get_issue.return_value = _issue_payload("h2. Raw")

        issues_mixin.update_issue("TEST-1", fields={"description": "## Raw"})

        payload = issues_mixin.jira.update_issue.call_args.kwargs["update"]
        assert payload["fields"]["description"] == "WIKI:## Raw"

    def test_update_issue_wiki_applies_to_direct_kwargs(self, issues_mixin):
        issues_mixin.jira.get_issue.return_value = _issue_payload("h2. Raw")

        issues_mixin.update_issue(
            "TEST-1",
            description="h2. Raw",
            description_format="wiki",
        )

        payload = issues_mixin.jira.update_issue.call_args.kwargs["update"]
        assert payload["fields"]["description"] == "h2. Raw"

    def test_create_issue_wiki_skips_conversion(self, issues_mixin):
        issues_mixin.jira.create_issue.return_value = {"key": "TEST-1"}
        issues_mixin.jira.get_issue.return_value = _issue_payload("h2. Raw")

        issues_mixin.create_issue(
            project_key="TEST",
            summary="Summary",
            issue_type="Task",
            description="h2. Raw",
            description_format="wiki",
        )

        fields = issues_mixin.jira.create_issue.call_args.kwargs["fields"]
        assert fields["description"] == "h2. Raw"
        issues_mixin._markdown_to_jira.assert_not_called()


@pytest.fixture
def comments_mixin(server_config):
    """CommentsMixin with mocked API client and converters."""
    mixin = CommentsMixin(config=server_config)
    mixin.jira = MagicMock()
    mixin.preprocessor = Mock()
    mixin._clean_text = Mock(side_effect=lambda text: text)
    mixin._markdown_to_jira = Mock(side_effect=lambda text: f"WIKI:{text}")
    mixin._is_internal_only_project = Mock(return_value=False)
    mixin._enforce_internal_only_edit = Mock()
    return mixin


class TestCommentFormatAndDelete:
    """Raw wiki comments and comment deletion."""

    def test_add_comment_wiki_skips_conversion(self, comments_mixin):
        comments_mixin.jira.issue_add_comment.return_value = {
            "id": "1",
            "body": "*bold*",
            "created": "2024-01-01T00:00:00.000+0000",
            "updated": "2024-01-01T00:00:00.000+0000",
            "author": {"displayName": "User"},
        }

        comments_mixin.add_comment("TEST-1", "*bold*", content_format="wiki")

        args = comments_mixin.jira.issue_add_comment.call_args.args
        assert args[1] == "*bold*"
        comments_mixin._markdown_to_jira.assert_not_called()

    def test_add_comment_markdown_converts(self, comments_mixin):
        comments_mixin.jira.issue_add_comment.return_value = {
            "id": "1",
            "body": "WIKI:**bold**",
            "created": "2024-01-01T00:00:00.000+0000",
            "updated": "2024-01-01T00:00:00.000+0000",
            "author": {"displayName": "User"},
        }

        comments_mixin.add_comment("TEST-1", "**bold**")

        args = comments_mixin.jira.issue_add_comment.call_args.args
        assert args[1] == "WIKI:**bold**"

    def test_edit_comment_wiki_skips_conversion(self, comments_mixin):
        comments_mixin.jira.issue_edit_comment.return_value = {
            "id": "1",
            "body": "*bold*",
            "updated": "2024-01-01T00:00:00.000+0000",
            "author": {"displayName": "User"},
        }

        comments_mixin.edit_comment(
            "TEST-1", "1", "*bold*", content_format="wiki"
        )

        args = comments_mixin.jira.issue_edit_comment.call_args.args
        assert args[2] == "*bold*"
        comments_mixin._markdown_to_jira.assert_not_called()

    def test_delete_comment_calls_rest_delete(self, comments_mixin):
        comments_mixin.jira.delete.return_value = None

        result = comments_mixin.delete_comment("TEST-1", "10001")

        comments_mixin.jira.delete.assert_called_once_with(
            "rest/api/2/issue/TEST-1/comment/10001"
        )
        assert result == {
            "issue_key": "TEST-1",
            "comment_id": "10001",
            "deleted": True,
        }


@pytest.fixture
def links_mixin(server_config):
    """LinksMixin with a mocked API client."""
    mixin = LinksMixin(config=server_config)
    mixin.jira = MagicMock()
    return mixin


class TestLinkTypeAliases:
    """Link type names are matched loosely."""

    @pytest.fixture(autouse=True)
    def _link_types(self, links_mixin):
        links_mixin.get_issue_link_types = Mock(
            return_value=[
                JiraIssueLinkType(id="10000", name="Relate"),
                JiraIssueLinkType(id="10001", name="Blocks"),
            ]
        )

    def test_exact_match(self, links_mixin):
        assert links_mixin._resolve_link_type_name("Relate") == "Relate"

    def test_case_insensitive_match(self, links_mixin):
        assert links_mixin._resolve_link_type_name("relate") == "Relate"

    def test_plural_match(self, links_mixin):
        assert links_mixin._resolve_link_type_name("Relates") == "Relate"

    def test_unknown_name_lists_available_types(self, links_mixin):
        with pytest.raises(ValueError, match="Available types: Blocks, Relate"):
            links_mixin._resolve_link_type_name("Duplicates")

    def test_create_issue_link_sends_resolved_name(self, links_mixin):
        links_mixin.jira.create_issue_link.return_value = None

        links_mixin.create_issue_link(
            {
                "type": {"name": "Relates"},
                "inwardIssue": {"key": "TEST-1"},
                "outwardIssue": {"key": "TEST-2"},
            }
        )

        sent = links_mixin.jira.create_issue_link.call_args.args[0]
        assert sent["type"]["name"] == "Relate"


@pytest.fixture
def projects_mixin(server_config):
    """JiraFetcher with a mocked API client."""
    with patch("atlassian.Jira") as mock_jira_class:
        mock_jira_class.return_value = MagicMock()
        mixin = JiraFetcher(config=server_config)
    mixin.jira = MagicMock()
    return mixin


class TestCompactComponents:
    """The compact components mode trims the response."""

    def test_compact_keeps_id_name_lead(self, projects_mixin):
        projects_mixin.jira.get_project_components.return_value = [
            {
                "id": "1",
                "name": "Backend",
                "lead": {"displayName": "User", "avatarUrls": {"48x48": "x"}},
                "assigneeType": "PROJECT_LEAD",
            }
        ]

        result = projects_mixin.get_project_components("TEST", compact=True)

        assert result == [{"id": "1", "name": "Backend", "lead": "User"}]

    def test_full_mode_is_unchanged(self, projects_mixin):
        raw = [{"id": "1", "name": "Backend", "lead": {"displayName": "User"}}]
        projects_mixin.jira.get_project_components.return_value = raw

        assert projects_mixin.get_project_components("TEST") == raw


class TestRenderedFields:
    """The renderedFields expansion reaches the simplified output."""

    def test_rendered_fields_are_extracted_and_filtered(self):
        payload = _issue_payload("plain")
        payload["renderedFields"] = {
            "description": "<p>rendered</p>",
            "comment": {"1": {"body": "<p>comment</p>"}},
            "summary": "duplicate",
        }

        issue = JiraIssue.from_api_response(payload)

        assert issue.rendered == {
            "description": "<p>rendered</p>",
            "comment": {"1": {"body": "<p>comment</p>"}},
        }
        assert issue.to_simplified_dict()["rendered"] == issue.rendered

    def test_no_expansion_means_no_rendered_key(self):
        issue = JiraIssue.from_api_response(_issue_payload("plain"))

        assert issue.rendered is None
        assert "rendered" not in issue.to_simplified_dict()
