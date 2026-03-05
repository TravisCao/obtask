from __future__ import annotations

import sys
from datetime import date
from typing import Annotated, Optional

import typer

from .core import (
    TASKS_DIR,
    VALID_STATUSES,
    AmbiguousMatchError,
    NoMatchError,
    add_comment,
    filter_tasks,
    load_tasks,
    mark_cancelled,
    mark_done,
    resolve_task,
    sort_tasks,
    update_status,
)
from .display import console, render_json, render_table, render_task_detail

app = typer.Typer(
    name="obtask",
    help="CLI for managing Obsidian task files in _system/tasks/. "
    "Tasks have YAML frontmatter (status, due, priority, tags, project) "
    "and Markdown body with checkboxes.",
    no_args_is_help=True,
)


def _validate_tasks_dir() -> None:
    if not TASKS_DIR.is_dir():
        console.print(f"[red]Error:[/red] Tasks directory not found: {TASKS_DIR}")
        console.print("Set OBSIDIAN_VAULT env var or check that ~/obsidian-notes exists.")
        raise typer.Exit(1)


def _handle_resolve(query: str, strict: bool = False, active_only: bool = False):
    try:
        return resolve_task(query, strict=strict, active_only=active_only)
    except AmbiguousMatchError as e:
        console.print(f"[yellow]Ambiguous query '{e.query}'. Did you mean:[/yellow]")
        for c in e.candidates:
            console.print(f"  - {c}")
        raise typer.Exit(1)
    except NoMatchError as e:
        console.print(f"[red]No task matching '{e.query}'[/red]")
        raise typer.Exit(1)


@app.command("list")
def list_tasks(
    status: Annotated[Optional[str], typer.Option("-s", "--status", help="Filter by status (todo, in-progress, blocked, done, cancelled)")] = None,
    priority: Annotated[Optional[str], typer.Option("-p", "--priority", help="Filter by priority (p1-p4)")] = None,
    tag: Annotated[Optional[str], typer.Option("--tag", help="Filter by tag")] = None,
    project: Annotated[Optional[str], typer.Option("--project", help="Filter by project (substring match)")] = None,
    overdue: Annotated[bool, typer.Option("--overdue", help="Show only overdue tasks")] = False,
    due_before: Annotated[Optional[str], typer.Option("--due-before", help="Due on or before date (YYYY-MM-DD)")] = None,
    due_after: Annotated[Optional[str], typer.Option("--due-after", help="Due on or after date (YYYY-MM-DD)")] = None,
    all_tasks: Annotated[bool, typer.Option("--all", help="Include done/cancelled tasks")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON (for programmatic use)")] = False,
) -> None:
    """List active tasks, sorted by due date then priority. Excludes done/cancelled by default."""
    _validate_tasks_dir()

    tasks = load_tasks(include_archive=all_tasks)

    # Parse date filters
    db = None
    da = None
    if due_before:
        try:
            db = date.fromisoformat(due_before)
        except ValueError:
            console.print(f"[red]Invalid date format: {due_before}. Use YYYY-MM-DD.[/red]")
            raise typer.Exit(1)
    if due_after:
        try:
            da = date.fromisoformat(due_after)
        except ValueError:
            console.print(f"[red]Invalid date format: {due_after}. Use YYYY-MM-DD.[/red]")
            raise typer.Exit(1)

    tasks = filter_tasks(
        tasks,
        status=status,
        priority=priority,
        tag=tag,
        project=project,
        overdue=overdue,
        due_before=db,
        due_after=da,
        include_done=all_tasks,
    )
    tasks = sort_tasks(tasks)

    if json_output:
        render_json(tasks)
    else:
        render_table(tasks)


@app.command()
def show(
    query: Annotated[str, typer.Argument(help="Filename slug or fuzzy search term. E.g. 'itf' matches '2026-02-25-itf-resilience-assessment.md'")],
) -> None:
    """Show full task detail: metadata, context, subtasks, and notes."""
    _validate_tasks_dir()
    task = _handle_resolve(query)
    render_task_detail(task)


@app.command()
def comment(
    query: Annotated[str, typer.Argument(help="Task slug (strict match for safety)")],
    text: Annotated[str, typer.Argument(help="Comment text to append")],
) -> None:
    """Append a timestamped comment to a task's Notes section."""
    _validate_tasks_dir()
    task = _handle_resolve(query, strict=True, active_only=True)
    add_comment(task, text)
    console.print(f"[green]Comment added to[/green] {task.slug}")


@app.command()
def done(
    query: Annotated[str, typer.Argument(help="Task slug (strict match)")],
) -> None:
    """Mark task as done, set completed_date, and move to archive/."""
    _validate_tasks_dir()
    task = _handle_resolve(query, strict=True, active_only=True)

    if task.status == "done":
        console.print(f"[yellow]Task already done:[/yellow] {task.slug}")
        raise typer.Exit(0)

    try:
        mark_done(task)
        console.print(f"[green]Done![/green] {task.slug} → archive/{task.filename}")
    except (FileExistsError, OSError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@app.command()
def status(
    query: Annotated[str, typer.Argument(help="Task slug (strict match)")],
    new_status: Annotated[str, typer.Argument(help="One of: todo, in-progress, blocked")],
) -> None:
    """Update a task's status field. For terminal states, use 'obtask done' or 'obtask cancel'."""
    _validate_tasks_dir()

    if new_status in ("done", "cancelled"):
        cmd = "obtask done" if new_status == "done" else "obtask cancel"
        console.print(f"[yellow]Use '{cmd}' to {new_status} tasks (also archives them).[/yellow]")
        raise typer.Exit(1)

    task = _handle_resolve(query, strict=True, active_only=True)

    try:
        update_status(task, new_status)
        console.print(f"[green]{task.slug}[/green] status → [bold]{new_status}[/bold]")
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)


@app.command()
def cancel(
    query: Annotated[str, typer.Argument(help="Task slug (strict match)")],
) -> None:
    """Mark task as cancelled and move to archive/."""
    _validate_tasks_dir()
    task = _handle_resolve(query, strict=True, active_only=True)

    if task.status == "cancelled":
        console.print(f"[yellow]Task already cancelled:[/yellow] {task.slug}")
        raise typer.Exit(0)

    try:
        archive_path = mark_cancelled(task)
        console.print(f"[green]Cancelled.[/green] {task.slug} → archive/{task.filename}")
    except (FileExistsError, OSError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
