import requests # type: ignore
from typing import Any, Dict


class ApiClientRequestFailedError(ConnectionError):

    def __init__(self, service_name: str, status: int, error: str) -> None:
        super().__init__(
            f"Jira Service Management Client request failed with status {status}: {error}"
        )
        self.status = status
        self.error = error


class BaseApiClient:
    
    def __init__(self, base_url: str, api_token: str) -> None:
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token

    def _build_url(self, endpoint: str) -> str:
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _build_headers(self) -> Dict[str, str]:
        return {
            'Authorization': f"Bearer {self.api_token}",
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

    def _handle_response(self, response: requests.Response, service_name: str) -> Dict[str, Any]:
        try:
            response_data = response.json()
        except ValueError:
            response_data = {}

        if response.status_code >= 300:
            error = response_data.get("errorMessages", [response.reason])[0]
            raise ApiClientRequestFailedError(service_name, response.status_code, error)

        return response_data


class JiraServiceManagementClient(BaseApiClient):

    def __init__(self, base_url: str, api_token: str, project_key: str) -> None:
        super().__init__(base_url, api_token)
        self.project_key = project_key

    def create_issue(self, summary: str, description: str, issue_type: str = "Task") -> Dict[str, Any]:
        endpoint = "rest/api/3/issue"
        url = self._build_url(endpoint)
        headers = self._build_headers()

        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
            }
        }

        response = requests.post(url, headers=headers, json=payload)
        return self._handle_response(response, "Jira")

    def get_issue(self, issue_id: str) -> Dict[str, Any]:
        endpoint = f"rest/api/3/issue/{issue_id}"
        url = self._build_url(endpoint)
        headers = self._build_headers()

        response = requests.get(url, headers=headers)
        return self._handle_response(response, "Jira")

    def search_issues(self, jql: str, max_results: int = 50) -> Dict[str, Any]:
        endpoint = "rest/api/3/search"
        url = self._build_url(endpoint)
        headers = self._build_headers()

        params = {
            "jql": jql,
            "maxResults": max_results
        }

        response = requests.get(url, headers=headers, params=params)
        return self._handle_response(response, "Jira")

    def create_comment(self, issue_id: str, comment: str) -> Dict[str, Any]:
        endpoint = f"rest/api/3/issue/{issue_id}/comment"
        url = self._build_url(endpoint)
        headers = self._build_headers()

        payload = {"body": comment}

        response = requests.post(url, headers=headers, json=payload)
        return self._handle_response(response, "Jira")
