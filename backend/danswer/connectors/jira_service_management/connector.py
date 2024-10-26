from typing import Callable, Any
from datetime import datetime, timezone
import time

from danswer.connectors.interfaces import LoadConnector, PollConnector, GenerateDocumentsOutput, SecondsSinceUnixEpoch
from danswer.connectors.models import Document, Section
from danswer.configs.constants import DocumentSource, HTML_SEPARATOR
from danswer.connectors.jira_service_management.client import JiraServiceManagementClient

class JiraServiceManagementClientNotSetUpError(PermissionError):
    def __init__(self) -> None:
        super().__init__(
            "Jira Service Management Client is not set up, was load_credentials called?"
        )


class JiraServiceManagementConnector(LoadConnector, PollConnector):
    def __init__(self, batch_size: int = 100) -> None:
        self.batch_size = batch_size
        self.jira_client: JiraServiceManagementClient | None = None

    def load_credentials(self, credentials: dict[str, Any]) -> dict[str, Any] | None:
        self.jira_client = JiraServiceManagementClient(
            base_url=credentials["jira_base_url"],
            api_token=credentials["jira_api_token"],
            email=credentials["jira_email"],
        )
        return None

    def _get_doc_batch(
        self,
        endpoint: str,
        transformer: Callable[[dict], Document],
        start_ind: int,
        start: SecondsSinceUnixEpoch | None = None,
        end: SecondsSinceUnixEpoch | None = None,
    ) -> tuple[list[Document], int]:
        doc_batch: list[Document] = []

        params = {
            "startAt": start_ind,
            "maxResults": self.batch_size,
        }

        if start:
            params["jql"] = f"updated >= '{datetime.fromtimestamp(start, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}'"
        if end:
            if "jql" in params:
                params["jql"] += f" AND updated <= '{datetime.fromtimestamp(end, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}'"
            else:
                params["jql"] = f"updated <= '{datetime.fromtimestamp(end, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}'"

        batch = self.jira_client.get(endpoint, params=params).get("issues", [])
        for item in batch:
            doc_batch.append(transformer(item))

        return doc_batch, len(batch)

    def _ticket_to_document(self, ticket: dict):
        issue_key = ticket.get("key")
        fields = ticket.get("fields", {})
        summary = fields.get("summary", "")
        description = fields.get("description", "")

        url = self.jira_client.build_app_url(f"/browse/{issue_key}")
        text = f"{summary}\n{description}"

        return Document(
            id=f"ticket:{issue_key}",
            sections=[Section(link=url, text=text)],
            source=DocumentSource.JIRA_SERVICE_MANAGEMENT,
            semantic_identifier=f"Ticket: {summary}",
            metadata={
                "type": "ticket",
                "updated_at": fields.get("updated", ""),
                "status": fields.get("status", {}).get("name", ""),
                "priority": fields.get("priority", {}).get("name", ""),
            },
        )

    def load_from_state(self) -> GenerateDocumentsOutput:
        if self.jira_client is None:
            raise JiraServiceManagementClientNotSetUpError()

        return self.poll_source(None, None)

    def poll_source(
        self, start: SecondsSinceUnixEpoch | None, end: SecondsSinceUnixEpoch | None
    ) -> GenerateDocumentsOutput:
        if self.jira_client is None:
            raise JiraServiceManagementClientNotSetUpError()

        start_ind = 0
        while True:
            doc_batch, num_results = self._get_doc_batch(
                "search",
                self._ticket_to_document,
                start_ind,
                start,
                end
            )
            start_ind += num_results
            if doc_batch:
                yield doc_batch

            if num_results < self.batch_size:
                break
            else:
                time.sleep(0.2)
