"""
Interactive TUI for the autonomous server healing system.
Requires: pip install textual

Run alongside the main pipeline in a second terminal:
  Pane 1:  POLL_INTERVAL_SECONDS=3 python -m pipeline.main_loop
  Pane 2:  python tui.py

Controls: ↑/↓ to browse incidents, detail panel updates live. q to quit.
"""
import sqlite3, os
from datetime import datetime
from dotenv import load_dotenv

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, DataTable, Static, RichLog
from textual.reactive import reactive
from rich.text import Text

load_dotenv()
DB_PATH = os.getenv("SQLITE_PATH", "data/incidents.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class StatsBar(Static):
    total = reactive(0)
    actioned = reactive(0)
    escalated = reactive(0)
    hardware = reactive(0)

    def render(self) -> Text:
        t = Text()
        t.append("  ● LIVE  ", style="bold white on dark_green")
        t.append("   Total: ", style="dim"); t.append(f"{self.total}", style="bold white")
        t.append("   Auto-remediated: ", style="dim"); t.append(f"{self.actioned}", style="bold green")
        t.append("   Escalated: ", style="dim"); t.append(f"{self.escalated}", style="bold yellow")
        t.append("   Hardware faults: ", style="dim"); t.append(f"{self.hardware}", style="bold red")
        t.append(f"   {datetime.now().strftime('%H:%M:%S')}", style="dim")
        return t


class DetailPanel(Static):
    content = reactive(None)

    def render(self):
        return self.content or Text("Select an incident above to view full details...", style="dim italic")


class HealingApp(App):
    CSS = """
    #stats { height: 1; background: $panel; padding: 0 1; }
    #body { height: 1fr; }
    #incidents { width: 55%; border: round cyan; }
    #right { width: 45%; }
    #detail { height: 60%; border: round magenta; padding: 1; }
    #audit { height: 40%; border: round yellow; }
    """
    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield StatsBar(id="stats")
        with Horizontal(id="body"):
            yield DataTable(id="incidents")
            with Vertical(id="right"):
                yield VerticalScroll(DetailPanel(id="detail_inner"), id="detail")
                yield RichLog(id="audit", markup=True, wrap=True)
        yield Footer()

    def on_mount(self):
        table = self.query_one("#incidents", DataTable)
        table.add_columns("Time", "Root Cause", "Conf", "Category", "HW", "Outcome")
        table.cursor_type = "row"
        table.zebra_stripes = True
        self._last_audit_id = 0
        self.set_interval(1.0, self.refresh_data)
        self.refresh_data()

    def refresh_data(self):
        conn = get_conn()
        stats = self.query_one("#stats", StatsBar)
        stats.total     = conn.execute("SELECT COUNT(*) c FROM incidents").fetchone()["c"]
        stats.actioned  = conn.execute("SELECT COUNT(*) c FROM incidents WHERE action_taken IS NOT NULL").fetchone()["c"]
        stats.escalated = conn.execute("SELECT COUNT(*) c FROM incidents WHERE escalated=1").fetchone()["c"]
        stats.hardware  = conn.execute("SELECT COUNT(*) c FROM incidents WHERE hardware_involved=1").fetchone()["c"]

        table = self.query_one("#incidents", DataTable)

        # remember which incident was selected before rebuilding
        selected_id = None
        if table.row_count > 0 and table.cursor_row is not None:
            try:
                row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
                selected_id = row_key.value
            except Exception:
                selected_id = None

        rows = conn.execute(
            "SELECT id, detected_at, root_cause, confidence, fault_category, "
            "hardware_involved, action_taken, escalated FROM incidents "
            "ORDER BY detected_at DESC LIMIT 30"
        ).fetchall()

        table.clear()
        new_cursor_index = 0
        for i, r in enumerate(rows):
            t = r["detected_at"][11:19] if r["detected_at"] else "—"
            cause = (r["root_cause"] or "")[:38]
            conf = f"{r['confidence']:.2f}" if r["confidence"] is not None else "—"
            hw = Text("YES", style="bold red") if r["hardware_involved"] else Text("no", style="dim")
            if r["action_taken"]:
                outcome = Text(f"✔ {r['action_taken']}", style="bold green")
            elif r["escalated"]:
                outcome = Text("⚠ escalated", style="bold yellow")
            else:
                outcome = Text("pending", style="dim")
            table.add_row(t, cause, conf, r["fault_category"] or "—", hw, outcome, key=r["id"])
            if r["id"] == selected_id:
                new_cursor_index = i

        if table.row_count > 0:
            table.cursor_coordinate = (new_cursor_index, 0)
            row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
            self.show_detail(row_key.value, conn)

        audit = self.query_one("#audit", RichLog)
        style_map = {"incident_created": "cyan", "action_starting": "yellow", "action_complete": "green",
                     "escalation": "red", "gate_passed": "green", "gate_failed": "red"}
        for e in conn.execute("SELECT id, timestamp, event_type, detail FROM audit_log WHERE id > ? ORDER BY id ASC",
                               (self._last_audit_id,)).fetchall():
            t = e["timestamp"][11:19] if e["timestamp"] else "—"
            style = style_map.get(e["event_type"], "white")
            audit.write(f"[dim]{t}[/dim]  [{style}]{e['event_type']:<18}[/{style}] {e['detail'][:70]}")
            self._last_audit_id = e["id"]
        conn.close()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        conn = get_conn()
        self.show_detail(event.row_key.value, conn)
        conn.close()

    def show_detail(self, incident_id, conn):
        row = conn.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
        if not row:
            return
        txt = Text()
        txt.append("Root Cause\n", style="bold underline")
        txt.append(f"{row['root_cause']}\n\n")

        txt.append("Confidence: ", style="bold"); txt.append(f"{row['confidence']:.2f}   ", style="cyan")
        txt.append("Category: ", style="bold"); txt.append(f"{row['fault_category']}   ", style="cyan")
        txt.append("Hardware: ", style="bold")
        txt.append(f"{'YES' if row['hardware_involved'] else 'No'}\n", style="red" if row["hardware_involved"] else "green")
        txt.append(f"Detected: {row['detected_at']}\n\n", style="dim")

        if row["action_taken"]:
            txt.append("✔ AUTO-REMEDIATED\n", style="bold green")
            txt.append(f"Action: {row['action_taken']}   Outcome: {row['action_outcome']}\n\n", style="green")
        elif row["escalated"]:
            txt.append("⚠ ESCALATED TO HUMAN\n\n", style="bold yellow")

        import json as _json
        try:
            chain = _json.loads(row["causal_chain"]) if row["causal_chain"] else []
        except Exception:
            chain = []
        if chain:
            txt.append("Causal Chain\n", style="bold underline")
            for i, step in enumerate(chain):
                txt.append(f"  [{i+1}] {step.get('component','?')}: {step.get('event','?')}\n")
            txt.append("\n")

        if row["reasoning_chain"]:
            txt.append("LLM Reasoning\n", style="bold underline")
            txt.append(f"{row['reasoning_chain']}\n\n", style="italic")

        if row["human_report"]:
            txt.append("── Full Report ──\n", style="bold magenta")
            txt.append(row["human_report"])

        self.query_one("#detail_inner", DetailPanel).content = txt


if __name__ == "__main__":
    HealingApp().run()