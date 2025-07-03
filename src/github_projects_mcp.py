"""
GitHub Projects MCP Server

Navigation: user → project → issue
- github://user/{username} - List projects for user
- github://org/{org} - List projects for org  
- github://project/{username}/{project} - Show issues by name/ID/number
- github://org-project/{org}/{project} - Show org project issues by name/ID/number  
- github://issue/{owner}/{repo}/{number} - Show issue details + comments
"""
import json
from typing import Dict, Any
from fastmcp import FastMCP
from github_client import GitHubProjectsClient

# Initialize FastMCP server
mcp = FastMCP(
    name="GitHub Projects",
    instructions="Navigate GitHub Projects: user → project → issue hierarchy"
)

# Initialize GitHub client
client = GitHubProjectsClient()

@mcp.resource(
    uri="github://user/{username}",
    name="User Projects",
    description="List all projects for a GitHub user",
    mime_type="application/json"
)
def get_user_projects(username: str) -> Dict[str, Any]:
    """Get projects for a user"""
    projects = client.get_user_projects(username)
    return {
        "type": "user_projects",
        "username": username,
        "projects": projects,
        "count": len(projects)
    }

@mcp.resource(
    uri="github://org/{org}",
    name="Organization Projects", 
    description="List all projects for a GitHub organization",
    mime_type="application/json"
)
def get_org_projects(org: str) -> Dict[str, Any]:
    """Get projects for an organization"""
    projects = client.get_org_projects(org)
    return {
        "type": "org_projects",
        "organization": org,
        "projects": projects,
        "count": len(projects)
    }

@mcp.resource(
    uri="github://project/{username}/{project_identifier}",
    name="Project Issues",
    description="Show all issues in a project by name, ID, or number (e.g. 'github_projects_mcp' or 'PVT_xyz' or '#10')",
    mime_type="application/json"
)
def get_project_issues(username: str, project_identifier: str) -> Dict[str, Any]:
    """Get issues in a project by name, ID, or number"""
    try:
        # Find the actual project ID
        project_id = client.find_project_id(username, project_identifier)
        project_data = client.get_project_items(project_id)
    except ValueError as e:
        return {
            "type": "error",
            "message": str(e),
            "available_projects": [
                {
                    "title": p.get("title"),
                    "id": p.get("id"), 
                    "number": p.get("number")
                }
                for p in client.get_user_projects(username)
            ]
        }
    
    # Organize issues by status
    items = project_data.get("items", {}).get("nodes", [])
    issues_by_status = {}
    
    for item in items:
        content = item.get("content", {})
        if not content or not content.get("number"):  # Skip draft issues
            continue
            
        # Find status
        status = "No Status"
        for field_value in item.get("fieldValues", {}).get("nodes", []):
            field = field_value.get("field")
            if field and field.get("name", "").lower() == "status":
                status = field_value.get("name", "No Status")
                break
        
        if status not in issues_by_status:
            issues_by_status[status] = []
        
        # Extract owner/repo from URL for navigation
        url = content.get("url", "")
        owner, repo = "", ""
        if "/issues/" in url:
            parts = url.split("/")
            owner, repo = parts[3], parts[4]
        
        issue_data = {
            "number": content.get("number"),
            "title": content.get("title"),
            "state": content.get("state"),
            "author": content.get("author", {}).get("login"),
            "url": url,
            "owner": owner,
            "repo": repo,
            "status": status
        }
        issues_by_status[status].append(issue_data)
    
    return {
        "type": "project_issues",
        "project": {
            "id": project_id,
            "title": project_data.get("title"),
            "description": project_data.get("shortDescription"),
            "matched_by": project_identifier
        },
        "issues_by_status": issues_by_status,
        "total_issues": sum(len(issues) for issues in issues_by_status.values())
    }

@mcp.resource(
    uri="github://org-project/{org}/{project_identifier}",
    name="Organization Project Issues",
    description="Show all issues in an org project by name, ID, or number",
    mime_type="application/json"
)
def get_org_project_issues(org: str, project_identifier: str) -> Dict[str, Any]:
    """Get issues in an org project by name, ID, or number"""
    try:
        # Find the actual project ID
        project_id = client.find_org_project_id(org, project_identifier)
        project_data = client.get_project_items(project_id)
    except ValueError as e:
        return {
            "type": "error",
            "message": str(e),
            "available_projects": [
                {
                    "title": p.get("title"),
                    "id": p.get("id"), 
                    "number": p.get("number")
                }
                for p in client.get_org_projects(org)
            ]
        }
    
    # Organize issues by status (same logic as user projects)
    items = project_data.get("items", {}).get("nodes", [])
    issues_by_status = {}
    
    for item in items:
        content = item.get("content", {})
        if not content or not content.get("number"):  # Skip draft issues
            continue
            
        # Find status
        status = "No Status"
        for field_value in item.get("fieldValues", {}).get("nodes", []):
            field = field_value.get("field")
            if field and field.get("name", "").lower() == "status":
                status = field_value.get("name", "No Status")
                break
        
        if status not in issues_by_status:
            issues_by_status[status] = []
        
        # Extract owner/repo from URL for navigation
        url = content.get("url", "")
        owner, repo = "", ""
        if "/issues/" in url:
            parts = url.split("/")
            owner, repo = parts[3], parts[4]
        
        issue_data = {
            "number": content.get("number"),
            "title": content.get("title"),
            "state": content.get("state"),
            "author": content.get("author", {}).get("login"),
            "url": url,
            "owner": owner,
            "repo": repo,
            "status": status
        }
        issues_by_status[status].append(issue_data)
    
    return {
        "type": "project_issues",
        "project": {
            "id": project_id,
            "title": project_data.get("title"),
            "description": project_data.get("shortDescription"),
            "matched_by": project_identifier,
            "organization": org
        },
        "issues_by_status": issues_by_status,
        "total_issues": sum(len(issues) for issues in issues_by_status.values())
    }

@mcp.resource(
    uri="github://issue/{owner}/{repo}/{number}",
    name="Issue Details",
    description="Show complete issue details with all comments",
    mime_type="application/json"
)
def get_issue_details(owner: str, repo: str, number: str) -> Dict[str, Any]:
    """Get complete issue details with comments"""
    issue_number = int(number)
    comments = client.get_issue_comments(owner, repo, issue_number)
    
    # Get issue details from the first comment query result
    issue_query = f"""
    query {{
        repository(owner: "{owner}", name: "{repo}") {{
            issue(number: {issue_number}) {{
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
        }}
    }}
    """
    
    result = client.execute_query(issue_query)
    issue = result.get("data", {}).get("repository", {}).get("issue", {})
    
    if not issue:
        return {
            "type": "error",
            "message": f"Issue #{issue_number} not found in {owner}/{repo}"
        }
    
    return {
        "type": "issue_details",
        "repository": {
            "owner": owner,
            "name": repo
        },
        "issue": issue,
        "comments": comments,
        "total_comments": len(comments)
    }


if __name__ == "__main__":
    mcp.run()