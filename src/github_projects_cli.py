#!/usr/bin/env python3
"""
GitHub Projects CLI Explorer

A simple CLI tool to explore GitHub Projects hierarchically using GraphQL.

Setup:
    1. Install dependencies through `uv`
    2. Set GitHub token: export GITHUB_TOKEN=your_token_here
       Token needs: read:project scope (+ repo scope for private repos)
    3. Run: uv run github_projects_cli.py

Classes:
    GitHubProjectsClient: Handles GraphQL queries to GitHub API
    GitHubProjectsCLI: Interactive CLI interface with caching

Features:
    - Lists all projects for a user/organization
    - Shows project items in kanban-style boards (grouped by status)
    - Displays issue details and all comments
    - Caches last used username/org for convenience
"""
import os
import httpx
from typing import Dict, List, Any, Optional
import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.markdown import Markdown

console = Console()
CACHE_FILE = Path(".github_projects_cache.json")

class GitHubProjectsClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {token}",
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


class GitHubProjectsCLI:
    def __init__(self, client: GitHubProjectsClient):
        self.client = client
        self.cache = self.load_cache()

    def load_cache(self) -> Dict[str, Any]:
        """Load cached settings"""
        try:
            return json.loads(CACHE_FILE.read_text())
        except:
            return {}

    def save_cache(self):
        """Save settings to cache"""
        CACHE_FILE.write_text(json.dumps(self.cache))

    def display_projects(self, projects: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Display projects in a table and let user select one"""
        if not projects:
            console.print("[red]No projects found![/red]")
            return None

        # Show only open projects
        projects = [p for p in projects if not p.get("closed", False)]
        if not projects:
            console.print("[yellow]No open projects found[/yellow]")
            return None

        table = Table(title="GitHub Projects", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=6)
        table.add_column("Title", style="cyan")
        table.add_column("Description", style="yellow")
        table.add_column("Updated", style="green")
        table.add_column("URL", style="blue")

        for idx, project in enumerate(projects, 1):
            table.add_row(
                str(idx),
                project.get("title", "Untitled"),
                project.get("shortDescription", "No description") or "No description",
                project.get("updatedAt", "Unknown")[:10],
                project.get("url", "")
            )

        console.print(table)

        choice = IntPrompt.ask(
            "\nWhich project are you interested in? (Enter number or 0 to exit)",
            default=0
        )

        if choice == 0 or choice > len(projects):
            return None

        return projects[choice - 1]

    def display_project_board(self, project_data: Dict[str, Any]):
        """Display project items in a kanban-style view"""
        title = project_data.get("title", "Untitled Project")
        items = project_data.get("items", {}).get("nodes", [])

        console.print(f"\n[bold cyan]Project: {title}[/bold cyan]")
        console.print(f"[dim]Total items: {len(items)}[/dim]\n")

        # Group items by status
        status_groups = {}

        for item in items:
            status = "No Status"

            # Find status field value
            for field_value in item.get("fieldValues", {}).get("nodes", []):
                field = field_value.get("field")
                if field and field.get("name", "").lower() == "status":
                    status = field_value.get("name", "No Status")
                    break

            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(item)

        # Define status order: TODO first, CLOSED last, everything else in between
        status_order = []
        todo_statuses = [s for s in status_groups.keys() if "todo" in s.lower()]
        closed_statuses = [s for s in status_groups.keys() if "closed" in s.lower() or "done" in s.lower()]
        other_statuses = [s for s in status_groups.keys() if s not in todo_statuses + closed_statuses]
        
        status_order.extend(todo_statuses)
        status_order.extend(sorted(other_statuses))
        status_order.extend(closed_statuses)

        # Display kanban board in order
        for status in status_order:
            status_items = status_groups[status]
            
            table = Table(title=f"{status} ({len(status_items)})", show_header=False, box=None)
            table.add_column("Issues", justify="center")

            for item in status_items:
                content = item.get("content") or {}
                if not content:
                    continue

                title = content.get("title", "Untitled")
                number = content.get('number', '')
                
                if number:
                    table.add_row(f"{title} #{number}")
                else:
                    table.add_row(title)

            console.print(table, justify="center")
            console.print()

        return items

    def display_issue_details(self, items: List[Dict[str, Any]]):
        """Let user select an issue and display its comments"""
        # Filter to only issues/PRs with numbers (not draft issues)
        numbered_items = []
        for item in items:
            content = item.get("content") or {}
            if content and content.get("number"):
                numbered_items.append(item)

        if not numbered_items:
            console.print("[red]No issues found![/red]")
            return

        choice = IntPrompt.ask(
            "\nWhich issue number would you like to see? (Enter issue number or 0 to go back)",
            default=0
        )

        if choice == 0:
            return

        # Find item by issue number
        selected_item = None
        for item in numbered_items:
            if item.get("content", {}).get("number") == choice:
                selected_item = item
                break

        if not selected_item:
            console.print(f"[red]Issue #{choice} not found![/red]")
            return
        content = selected_item.get("content", {})

        # Extract owner and repo from URL
        url = content.get("url", "")
        if "/issues/" in url or "/pull/" in url:
            parts = url.split("/")
            owner = parts[3]
            repo = parts[4]
            number = content.get("number")

            # Display issue details
            console.print(f"\n[bold cyan]Issue #{number}: {content.get('title', 'Untitled')}[/bold cyan]")
            console.print(f"[dim]Author: @{content.get('author', {}).get('login', 'Unknown')}[/dim]")
            console.print(f"[dim]State: {content.get('state', 'Unknown')}[/dim]")
            console.print(f"[dim]URL: {url}[/dim]\n")

            if content.get("body"):
                console.print(Panel(
                    Markdown(content.get("body")),
                    title="Description",
                    border_style="yellow"
                ))

            # Get and display comments
            try:
                comments = self.client.get_issue_comments(owner, repo, number)

                if comments:
                    console.print(f"\n[bold]Comments ({len(comments)})[/bold]\n")

                    for comment in comments:
                        author = comment.get("author", {}).get("login", "Unknown")
                        created = comment.get("createdAt", "Unknown")[:10]
                        body = comment.get("body", "No content")

                        console.print(Panel(
                            Markdown(body),
                            title=f"@{author} - {created}",
                            border_style="green"
                        ))
                else:
                    console.print("[dim]No comments on this issue[/dim]")

            except Exception as e:
                console.print(f"[red]Error fetching comments: {e}[/red]")

    def run(self):
        """Main CLI loop"""
        console.print("[bold cyan]GitHub Projects Explorer[/bold cyan]\n")

        while True:
            # Skip prompts if cache has both choice and username/org
            if self.cache.get("last_choice") and (self.cache.get("last_username") or self.cache.get("last_org")):
                choice = self.cache["last_choice"]
                console.print(f"[dim]Using cached: {choice}[/dim]")
            else:
                # Use cached choice or ask
                default_choice = self.cache.get("last_choice", "user")
                choice = Prompt.ask(
                    "What would you like to explore?",
                    choices=["user", "org", "exit"],
                    default=default_choice
                )

                if choice == "exit":
                    console.print("[yellow]Goodbye![/yellow]")
                    break

                # Save choice
                self.cache["last_choice"] = choice

            if choice == "user":
                if self.cache.get("last_username"):
                    username = self.cache["last_username"]
                    console.print(f"[dim]Using cached username: {username}[/dim]")
                else:
                    # Use cached username or ask
                    default_username = self.cache.get("last_username", "octocat")
                    username = Prompt.ask("Enter GitHub username", default=default_username)
                    self.cache["last_username"] = username
                    self.save_cache()

                try:
                    projects = self.client.get_user_projects(username)
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                    continue
            else:  # org
                if self.cache.get("last_org"):
                    org = self.cache["last_org"]
                    console.print(f"[dim]Using cached org: {org}[/dim]")
                else:
                    # Use cached org or ask
                    default_org = self.cache.get("last_org", "github")
                    org = Prompt.ask("Enter GitHub organization", default=default_org)
                    self.cache["last_org"] = org
                    self.save_cache()

                try:
                    projects = self.client.get_org_projects(org)
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                    continue

            selected_project = self.display_projects(projects)
            if not selected_project:
                continue

            # Get project details
            try:
                project_data = self.client.get_project_items(selected_project["id"])
                items = self.display_project_board(project_data)

                # Ask which issue to see comments for
                if items:
                    self.display_issue_details(items)

            except Exception as e:
                console.print(f"[red]Error loading project: {e}[/red]")

            console.print("\n" + "="*80 + "\n")


def main():
    # Get GitHub token from environment
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        console.print("[red]Error: GITHUB_TOKEN environment variable not set![/red]")
        console.print("Please set it with: export GITHUB_TOKEN=your_token_here")
        return

    client = GitHubProjectsClient(token)
    cli = GitHubProjectsCLI(client)
    cli.run()


if __name__ == "__main__":
    main()
