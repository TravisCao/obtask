from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import frontmatter

VAULT = Path(os.environ.get("OBSIDIAN_VAULT", "~/obsidian-notes")).expanduser().resolve()
TASKS_DIR = VAULT / "_system" / "tasks"
ARCHIVE_DIR = TASKS_DIR / "archive"

VALID_STATUSES = {"todo", "in-progress", "blocked", "done", "cancelled"}


@dataclass
class SubTask:
    text: str
    done: bool
    in_progress: bool  # [→]

    @property
    def marker(self) -> str:
        if self.done:
            return "x"
        if self.in_progress:
            return "→"
        return " "


@dataclass
class Task:
    path: Path
    title: str
    status: str
    priority: str | None
    due: date | None
    created: date | None
    completed_date: date | None
    tags: list[str]
    project: str | None
    blocked_reason: str | None
    subtasks: list[SubTask] = field(default_factory=list)
    body: str = ""

    @property
    def slug(self) -> str:
        return self.path.stem

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def is_overdue(self) -> bool:
        if self.due is None or self.status in ("done", "cancelled"):
            return False
        return self.due < date.today()

    @property
    def subtasks_total(self) -> int:
        return len(self.subtasks)

    @property
    def subtasks_done(self) -> int:
        return sum(1 for s in self.subtasks if s.done)


# Regex for checkbox lines: - [ ], - [x], - [→], numbered variants
_CHECKBOX_RE = re.compile(r"^[\s]*(?:[-*]|\d+\.)\s+\[([ x→X✓])\]\s+(.+)", re.MULTILINE)


def _parse_date(val) -> date | None:
    if val is None or val == "" or str(val).strip().upper() == "TBD":
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val).strip())
    except (ValueError, TypeError):
        return None


def _parse_title(content: str, fallback: str) -> str:
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return fallback


def _parse_subtasks(content: str) -> list[SubTask]:
    results = []
    for m in _CHECKBOX_RE.finditer(content):
        marker = m.group(1)
        text = m.group(2).strip()
        done = marker in ("x", "X", "✓")
        in_progress = marker == "→"
        results.append(SubTask(text=text, done=done, in_progress=in_progress))
    return results


def _parse_tags(val) -> list[str]:
    if isinstance(val, list):
        return [str(t) for t in val]
    if isinstance(val, str) and val.strip():
        return [t.strip() for t in val.split(",")]
    return []


def load_task(path: Path) -> Task | None:
    try:
        post = frontmatter.load(str(path))
    except Exception:
        import sys
        print(f"Warning: could not parse {path.name}", file=sys.stderr)
        return None

    meta = post.metadata
    content = post.content

    return Task(
        path=path,
        title=_parse_title(content, path.stem),
        status=str(meta.get("status", "todo")).strip(),
        priority=meta.get("priority") if meta.get("priority") else None,
        due=_parse_date(meta.get("due")),
        created=_parse_date(meta.get("created")),
        completed_date=_parse_date(meta.get("completed_date")),
        tags=_parse_tags(meta.get("tags", [])),
        project=meta.get("project") if meta.get("project") else None,
        blocked_reason=meta.get("blocked_reason") if meta.get("blocked_reason") else None,
        subtasks=_parse_subtasks(content),
        body=content,
    )


def load_tasks(include_archive: bool = False) -> list[Task]:
    tasks = []
    paths = list(TASKS_DIR.glob("*.md"))
    if include_archive and ARCHIVE_DIR.is_dir():
        paths.extend(ARCHIVE_DIR.glob("*.md"))
    for p in paths:
        task = load_task(p)
        if task is not None:
            tasks.append(task)
    return tasks


_PRIORITY_ORDER = {"p1": 0, "p2": 1, "p3": 2, "p4": 3}


def sort_tasks(tasks: list[Task]) -> list[Task]:
    def sort_key(t: Task):
        # Due date: no-date last (use far-future sentinel)
        due_key = t.due if t.due else date(9999, 12, 31)
        # Priority: None sorts after p4
        pri_key = _PRIORITY_ORDER.get(t.priority, 99) if t.priority else 99
        return (due_key, pri_key, t.title.lower())
    return sorted(tasks, key=sort_key)


def filter_tasks(
    tasks: list[Task],
    *,
    status: str | None = None,
    priority: str | None = None,
    tag: str | None = None,
    project: str | None = None,
    overdue: bool = False,
    due_before: date | None = None,
    due_after: date | None = None,
    include_done: bool = False,
) -> list[Task]:
    result = tasks
    if not include_done:
        result = [t for t in result if t.status not in ("done", "cancelled")]
    if status:
        result = [t for t in result if t.status == status]
    if priority:
        result = [t for t in result if t.priority == priority]
    if tag:
        result = [t for t in result if tag in t.tags]
    if project:
        result = [t for t in result if t.project and project.lower() in t.project.lower()]
    if overdue:
        result = [t for t in result if t.is_overdue]
    if due_before:
        result = [t for t in result if t.due and t.due <= due_before]
    if due_after:
        result = [t for t in result if t.due and t.due >= due_after]
    return result


class AmbiguousMatchError(Exception):
    def __init__(self, query: str, candidates: list[str]):
        self.query = query
        self.candidates = candidates
        super().__init__(f"Ambiguous query '{query}': {candidates}")


class NoMatchError(Exception):
    def __init__(self, query: str):
        self.query = query
        super().__init__(f"No task matching '{query}'")


def resolve_task(query: str, tasks: list[Task] | None = None, strict: bool = False, active_only: bool = False) -> Task:
    if tasks is None:
        tasks = load_tasks(include_archive=not active_only)

    q = query.lower().strip()

    # Level 1: exact stem match
    for t in tasks:
        if t.slug.lower() == q:
            return t

    # Level 2: substring match on slug
    matches = [t for t in tasks if q in t.slug.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        if strict:
            raise AmbiguousMatchError(query, [t.slug for t in matches])
        # In non-strict mode, also raise to let user disambiguate
        raise AmbiguousMatchError(query, [t.slug for t in matches])

    # Level 3 (non-strict only): token-based match
    if not strict:
        tokens = q.split()
        if tokens:
            matches = [t for t in tasks if all(tok in t.slug.lower() for tok in tokens)]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise AmbiguousMatchError(query, [t.slug for t in matches])

    # Level 4 (non-strict only): match against title
    if not strict:
        matches = [t for t in tasks if q in t.title.lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise AmbiguousMatchError(query, [t.slug for t in matches])

    raise NoMatchError(query)


def add_comment(task: Task, text: str) -> None:
    content = task.path.read_text(encoding="utf-8")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    comment_line = f"- [{now}] {text}\n"

    # Find ## Notes or ## 备注
    notes_pattern = re.compile(r"^(## Notes|## 备注)\s*$", re.MULTILINE)
    m = notes_pattern.search(content)
    if m:
        # Insert after the heading line
        insert_pos = m.end()
        # Skip any blank line immediately after the heading
        if insert_pos < len(content) and content[insert_pos] == "\n":
            insert_pos += 1
        new_content = content[:insert_pos] + comment_line + content[insert_pos:]
    else:
        # Append ## Notes section at end
        new_content = content.rstrip("\n") + "\n\n## Notes\n" + comment_line

    _atomic_write(task.path, new_content)


def _atomic_write(path: Path, content: str) -> None:
    fd, tmp_path = tempfile.mkstemp(suffix=".md", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


def _split_frontmatter(content: str) -> tuple[str, str, str]:
    """Split file into (opening ---, frontmatter, rest including closing ---)."""
    if not content.startswith("---"):
        raise ValueError("File has no YAML frontmatter")
    end = content.find("\n---", 3)
    if end == -1:
        raise ValueError("File has no closing --- for frontmatter")
    # opening "---\n", frontmatter body, "\n---" + rest
    fm_start = 4  # after "---\n"
    fm_end = end
    rest_start = end  # includes "\n---\n..."
    return content[:fm_start], content[fm_start:fm_end], content[fm_end:]


def update_status(task: Task, new_status: str) -> None:
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{new_status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}")

    content = task.path.read_text(encoding="utf-8")
    opener, fm, rest = _split_frontmatter(content)

    # Replace status field within frontmatter only
    fm, n = re.subn(
        r"^(status:\s*)(.*)$",
        rf"\g<1>{new_status}",
        fm,
        count=1,
        flags=re.MULTILINE,
    )
    if n == 0:
        raise ValueError(f"Could not find 'status:' field in frontmatter of {task.path.name}")

    # Set completed_date if marking done
    if new_status == "done":
        today_str = date.today().isoformat()
        if re.search(r"^completed_date:\s*$", fm, re.MULTILINE):
            fm = re.sub(
                r"^(completed_date:)\s*$",
                rf"\1 {today_str}",
                fm,
                count=1,
                flags=re.MULTILINE,
            )
        elif not re.search(r"^completed_date:", fm, re.MULTILINE):
            fm = re.sub(
                r"^(status:\s*.+)$",
                rf"\1\ncompleted_date: {today_str}",
                fm,
                count=1,
                flags=re.MULTILINE,
            )

    # Clear completed_date when cancelling (R3 fix)
    if new_status == "cancelled":
        fm = re.sub(
            r"^(completed_date:)\s*.+$",
            r"\1",
            fm,
            count=1,
            flags=re.MULTILINE,
        )

    _atomic_write(task.path, opener + fm + rest)


def _archive_task(task: Task, new_status: str) -> Path:
    """Update status and move task to archive. Returns new path."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE_DIR / task.path.name

    if archive_path.exists():
        raise FileExistsError(f"Archive collision: {archive_path.name} already exists in archive/")

    original_content = task.path.read_text(encoding="utf-8")
    try:
        update_status(task, new_status)
        shutil.move(str(task.path), str(archive_path))
    except Exception:
        if task.path.exists():
            task.path.write_text(original_content, encoding="utf-8")
        raise
    return archive_path


def mark_done(task: Task) -> Path:
    """Mark task done and move to archive. Returns the new path."""
    return _archive_task(task, "done")


def mark_cancelled(task: Task) -> Path:
    """Mark task cancelled and move to archive. Returns the new path."""
    return _archive_task(task, "cancelled")
