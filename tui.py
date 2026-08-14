"""
Live terminal dashboard for the autonomous server healing system.
Run alongside the main pipeline in a second terminal:

  Pane 1:  POLL_INTERVAL_SECONDS=3 python -m pipeline.main_loop
  Pane 2:  python tui.py
"""
import sqlite3, os, time, json
from datetime import datetime
from dotenv import load_dotenv
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Console

load_dotenv()
DB_PATH = os.getenv("SQLITE_PATH", "data/incidents.db")
console = Console()


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def build_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="incidents", ratio=2),
        Layout(name="audit", ratio=2),
    )
    return layout


def render_header() -> Panel:
    return Panel(
        Text("AUTONOMOUS SERVER HEALING SYSTEM  —  LIVE MONITOR", style="bold white on blue", justify="center"),
        style="blue"
    )


def render_incidents(conn) -> Panel:
    table = Table(expand=True, show_lines=False)
    table.add_column("Time", style="dim", width=10)
    table.add_column("Root Cause", ratio=3)
    table.add_column("Conf", width=6, justify="center")
    table.add_column("Category", width=10)
    table.add_column("HW", width=4, justify="center")
    table.add_column("Outcome", width=14)

    rows = conn.execute(
        "SELECT detected_at, root_cause, confidence, fault_category, "
        "hardware_involved, action_taken, escalated FROM incidents "
        "ORDER BY detected_at DESC LIMIT 12"
    ).fetchall()

    for r in rows:
        t = r["detected_at"][11:19] if r["detected_at"] else "—"
        cause = (r["root_cause"] or "")[:48]
        conf = f"{r['confidence']:.2f}" if r["confidence"] is not None else "—"
        cat = r["fault_category"] or "—"
        hw = Text("YES", style="bold red") if r["hardware_involved"] else Text("no", style="dim")

        if r["action_taken"]:
            outcome = Text(f"✔ {r['action_taken']}", style="bold green")
        elif r["escalated"]:
            outcome = Text("⚠ escalated", style="bold yellow")
        else:
            outcome = Text("pending", style="dim")

        table.add_row(t, cause, conf, cat, hw, outcome)

    if not rows:
        return Panel(Text("Waiting for first incident...", style="dim italic"), title="Incidents", border_style="cyan")

    return Panel(table, title=f"Incidents  ({len(rows)} shown)", border_style="cyan")


def render_audit(conn) -> Panel:
    rows = conn.execute(
        "SELECT timestamp, event_type, detail FROM audit_log "
        "ORDER BY timestamp DESC LIMIT 14"
    ).fetchall()

    lines = []
    style_map = {
        "incident_created": "cyan",
        "action_starting": "yellow",
        "action_complete": "green",
        "escalation": "red",
        "gate_passed": "green",
        "gate_failed": "red",
        "llm_call_failed": "red",
        "parse_failed": "red",
    }

    for r in rows:
        t = r["timestamp"][11:19] if r["timestamp"] else "—"
        style = style_map.get(r["event_type"], "white")
        detail = (r["detail"] or "")[:60]
        lines.append(Text.assemble(
            (f"{t}  ", "dim"),
            (f"{r['event_type']:<18}", style),
            (detail, "white")
        ))

    if not lines:
        return Panel(Text("No audit events yet...", style="dim italic"), title="Audit Trail", border_style="magenta")

    body = Text("\n").join(lines)
    return Panel(body, title="Audit Trail (live)", border_style="magenta")


def render_footer(conn) -> Panel:
    total = conn.execute("SELECT COUNT(*) c FROM incidents").fetchone()["c"]
    escalated = conn.execute("SELECT COUNT(*) c FROM incidents WHERE escalated=1").fetchone()["c"]
    actioned = conn.execute("SELECT COUNT(*) c FROM incidents WHERE action_taken IS NOT NULL").fetchone()["c"]
    now = datetime.now().strftime("%H:%M:%S")

    text = Text.assemble(
        (f"  Total incidents: ", "dim"), (f"{total}", "bold white"),
        (f"   Auto-remediated: ", "dim"), (f"{actioned}", "bold green"),
        (f"   Escalated: ", "dim"), (f"{escalated}", "bold yellow"),
        (f"   |   {now}  ", "dim"),
        ("Ctrl+C to exit", "dim italic"),
    )
    return Panel(text, style="on grey11")


def main():
    layout = build_layout()
    with Live(layout, refresh_per_second=2, screen=True) as live:
        while True:
            try:
                conn = get_conn()
                layout["header"].update(render_header())
                layout["incidents"].update(render_incidents(conn))
                layout["audit"].update(render_audit(conn))
                layout["footer"].update(render_footer(conn))
                conn.close()
            except Exception as e:
                layout["footer"].update(Panel(Text(f"  Error: {e}", style="red"), style="on grey11"))
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold cyan]TUI stopped.[/bold cyan]")