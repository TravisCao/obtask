from __future__ import annotations

import json
from datetime import date

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .core import Task

console = Console()

_PRI_STYLES = {
    "p1": "bold red",
    "p2": "yellow",
    "p3": "dim",
    "p4": "dim",
}

_STATUS_STYLES = {
    "blocked": "yellow",
    "in-progress": "cyan",
    "done": "green",
    "cancelled": "dim strike",
    "todo": "",
}


def render_table(tasks: list[Task]) -> None:
    if not tasks:
        console.print("[dim]No tasks found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("PRI", width=3, justify="center")
    table.add_column("STATUS", width=12)
    table.add_column("DUE", width=10)
    table.add_column("TITLE", min_width=20, max_width=50)
    table.add_column("FILE", style="dim")

    today = date.today()

    for t in tasks:
        # Priority
        pri_text = Text(t.priority or "-", style=_PRI_STYLES.get(t.priority, ""))

        # Status
        st_style = _STATUS_STYLES.get(t.status, "")
        status_text = Text(t.status, style=st_style)

        # Due date
        if t.due is None:
            due_text = Text("-", style="dim")
        elif t.due < today and t.status not in ("done", "cancelled"):
            due_text = Text(t.due.isoformat(), style="bold red")
        elif t.due == today:
            due_text = Text(t.due.isoformat(), style="bold")
        else:
            due_text = Text(t.due.isoformat())

        # Title (truncate if needed)
        title_str = t.title
        if len(title_str) > 50:
            title_str = title_str[:47] + "..."

        # Subtask progress
        if t.subtasks_total > 0:
            title_str += f" [{t.subtasks_done}/{t.subtasks_total}]"

        title_text = Text(title_str)

        table.add_row(pri_text, status_text, due_text, title_text, t.slug)

    console.print(table)


def render_task_detail(task: Task) -> None:
    lines = []

    # Metadata
    lines.append(f"[bold]Status:[/bold]  {task.status}")
    lines.append(f"[bold]Priority:[/bold] {task.priority or '-'}")
    lines.append(f"[bold]Due:[/bold]      {task.due.isoformat() if task.due else '-'}")
    lines.append(f"[bold]Created:[/bold]  {task.created.isoformat() if task.created else '-'}")
    if task.completed_date:
        lines.append(f"[bold]Completed:[/bold] {task.completed_date.isoformat()}")
    if task.tags:
        lines.append(f"[bold]Tags:[/bold]     {', '.join(task.tags)}")
    if task.project:
        lines.append(f"[bold]Project:[/bold]  {task.project}")
    if task.blocked_reason:
        lines.append(f"[bold yellow]Blocked:[/bold yellow]  {task.blocked_reason}")

    lines.append("")

    # Subtasks
    if task.subtasks:
        lines.append("[bold]Subtasks:[/bold]")
        for st in task.subtasks:
            if st.done:
                lines.append(f"  [green][x][/green] [strike]{st.text}[/strike]")
            elif st.in_progress:
                lines.append(f"  [yellow][→][/yellow] {st.text}")
            else:
                lines.append(f"  [dim][ ][/dim] {st.text}")
        lines.append("")

    # Body (show the markdown content)
    lines.append("[bold]Content:[/bold]")
    lines.append(task.body)

    panel = Panel(
        "\n".join(lines),
        title=f"[bold]{task.title}[/bold]",
        subtitle=f"[dim]{task.filename}[/dim]",
        expand=False,
        width=min(console.width, 100),
    )
    console.print(panel)


def render_json(tasks: list[Task]) -> None:
    today = date.today()
    data = []
    for t in tasks:
        data.append({
            "slug": t.slug,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "due": t.due.isoformat() if t.due else None,
            "overdue": t.is_overdue,
            "tags": t.tags,
            "project": t.project,
            "subtasks_total": t.subtasks_total,
            "subtasks_done": t.subtasks_done,
            "file": t.filename,
        })
    print(json.dumps(data, ensure_ascii=False, indent=2))
