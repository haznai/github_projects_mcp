"""
GitHub Projects Client

A client for interacting with GitHub Projects using GraphQL API.
Extracted from github_projects_cli.py to be reusable in MCP server.
"""
import os
import httpx
from typing import Dict, List, Any, Optional


class GitHubProjectsClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable or pass token parameter.")

        self.base_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def execute_query(self, query: str) -> Dict[str, Any]:
        """Execute a GraphQL query against GitHub API"""
        with httpx.Client() as client:
            response = client.post(
                self.base_url,
                headers=self.headers,
                json={"query": query}
            )
            response.raise_for_status()
            return response.json()

    def get_user_projects(self, username: str) -> List[Dict[str, Any]]:
        """Get all projects for a user"""
        query = f"""
        query {{
            user(login: "{username}") {{
                projectsV2(first: 100) {{
                    nodes {{
                        id
                        title
                        shortDescription
                        number
                        url
                        updatedAt
                        closed
                    }}
                }}
            }}
        }}
        """
        result = self.execute_query(query)
        return result.get("data", {}).get("user", {}).get("projectsV2", {}).get("nodes", [])

    def get_org_projects(self, org: str) -> List[Dict[str, Any]]:
        """Get all projects for an organization"""
        query = f"""
        query {{
            organization(login: "{org}") {{
                projectsV2(first: 100) {{
                    nodes {{
                        id
                        title
                        shortDescription
                        number
                        url
                        updatedAt
                        closed
                    }}
                }}
            }}
        }}
        """
        result = self.execute_query(query)
        return result.get("data", {}).get("organization", {}).get("projectsV2", {}).get("nodes", [])

    def get_project_items(self, project_id: str) -> Dict[str, Any]:
        """Get all items in a project with their field values"""
        query = f"""
        query {{
            node(id: "{project_id}") {{
                ... on ProjectV2 {{
                    title
                    fields(first: 20) {{
                        nodes {{
                            ... on ProjectV2Field {{
                                id
                                name
                            }}
                            ... on ProjectV2SingleSelectField {{
                                id
                                name
                                options {{
                                    id
                                    name
                                }}
                            }}
                        }}
                    }}
                    items(first: 100) {{
                        nodes {{
                            id
                            fieldValues(first: 20) {{
                                nodes {{
                                    ... on ProjectV2ItemFieldTextValue {{
                                        text
                                        field {{
                                            ... on ProjectV2FieldCommon {{
                                                name
                                            }}
                                        }}
                                    }}
                                    ... on ProjectV2ItemFieldDateValue {{
                                        date
                                        field {{
                                            ... on ProjectV2FieldCommon {{
                                                name
                                            }}
                                        }}
                                    }}
                                    ... on ProjectV2ItemFieldSingleSelectValue {{
                                        name
                                        field {{
                                            ... on ProjectV2FieldCommon {{
                                                name
                                            }}
                                        }}
                                    }}
                                }}
                            }}
                            content {{
                                ... on DraftIssue {{
                                    title
                                    body
                                }}
                                ... on Issue {{
                                    title
                                    body
                                    number
                                    url
                                    state
                                    createdAt
                                    updatedAt
                                    author {{
                                        login
                                    }}
                                    assignees(first: 10) {{
                                        nodes {{
                                            login
                                        }}
                                    }}
                                    labels(first: 10) {{
                                        nodes {{
                                            name
                                            color
                                        }}
                                    }}
                                }}
                                ... on PullRequest {{
                                    title
                                    body
                                    number
                                    url
                                    state
                                    createdAt
                                    updatedAt
                                    author {{
                                        login
                                    }}
                                    assignees(first: 10) {{
                                        nodes {{
                                            login
                                        }}
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        result = self.execute_query(query)
        return result.get("data", {}).get("node", {})

    def get_issue_comments(self, owner: str, repo: str, issue_number: int) -> List[Dict[str, Any]]:
        """Get all comments for an issue"""
        query = f"""
        query {{
            repository(owner: "{owner}", name: "{repo}") {{
                issue(number: {issue_number}) {{
                    title
                    comments(first: 100) {{
                        nodes {{
                            id
                            body
                            createdAt
                            updatedAt
                            author {{
                                login
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        result = self.execute_query(query)
        issue = result.get("data", {}).get("repository", {}).get("issue", {})
        return issue.get("comments", {}).get("nodes", [])

    def get_commits_by_prefix(self, owner: str, repo: str, prefix: str) -> list:
        """Get commits with messages starting with given prefix"""
        query = f"""
        query {{
            repository(owner: "{owner}", name: "{repo}") {{
                defaultBranchRef {{
                    target {{
                        ... on Commit {{
                            history(first: 100) {{
                                nodes {{
                                    oid
                                    message
                                    author {{
                                        name
                                        date
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """
        result = self.execute_query(query)
        commits = result.get("data", {}).get("repository", {}).get("defaultBranchRef", {}).get("target", {}).get("history", {}).get("nodes", [])

        # Filter commits by prefix
        filtered_commits = []
        for commit in commits:
            message = commit.get("message", "")
            if message.startswith(prefix):
                filtered_commits.append(commit)

        return filtered_commits
