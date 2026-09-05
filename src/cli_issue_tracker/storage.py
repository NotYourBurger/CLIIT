import os

ISSUES_DIR = ".issues"

def issues_dir() -> str:
    return os.path.join(os.getcwd(), ISSUES_DIR)

def require_issue_dir() -> str | None:
    path = issues_dir()
    if not os.path.isdir(path):
        print("Please Run - issue init - to initialize the project first")
        return None
    return path

def parse_issue(file_path: str) -> dict | None:
    """Read one issue file back into a dict. Returns None if it isn't a valid issue."""
    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.read().splitlines()

    # Frontmatter is only ever the block at the very top, fenced by the first
    # two --- lines. Find where it ends, then never look at those markers again -
    # a --- further down is a horizontal rule in the description, not a fence.
    if not lines or lines[0] != "---":
        return None
    try:
        fence = lines.index("---", 1)
    except ValueError:
        return None

    issue = {}
    for line in lines[1:fence]:
        key, _, value = line.partition(":")
        issue[key.strip()] = value.strip()

    # body is the file minus the frontmatter, verbatim - that is what the viewer
    # shows. title is pulled out separately because the list needs it as a column.
    body = lines[fence + 1 :]
    issue["body"] = "\n".join(body).strip()
    for i, line in enumerate(body):
        if line.startswith("# "):
            issue["title"] = line[2:].strip()
            break

    # A file missing any of these isn't an issue we wrote - skip it.
    if not all(k in issue for k in ("id", "status", "created_at", "title")):
        return None
    return issue

def write_issue(issue: dict) -> str | None:
    """Write an issue dict to .issues/<id>.md. Returns the path, or None if no .issues."""
    path = require_issue_dir()
    if path is None:
        return None

    # The exact inverse of parse_issue - every frontmatter key back out, same
    # fence, same body. Change one and you must change the other, which is why
    # they live together. The three known keys keep their documented order;
    # anything else a human added to the file follows, rather than being
    # dropped on the next rewrite. "title" is derived from the body heading,
    # not a frontmatter field, so it is not written back.
    fields = [f"{key}: {issue[key]}" for key in ("id", "status", "created_at")]
    fields += [
        f"{key}: {value}"
        for key, value in issue.items()
        if key not in ("id", "status", "created_at", "title", "body")
    ]
    frontmatter = "\n".join(fields)

    content = f"""---
{frontmatter}
---

{issue["body"]}
"""

    file_path = os.path.join(path, f"{issue['id']}.md")
    with open(file_path, "w", encoding="utf-8") as md_file:
        md_file.write(content)
    return file_path


def read_issue(id: str) -> dict | None:
    path = require_issue_dir()
    if path is None:
        return None
    file_name = f"{id}.md"
    file_path = os.path.join(path,file_name)
    if os.path.isfile(file_path):
        return parse_issue(file_path)
    else:
        return None
       