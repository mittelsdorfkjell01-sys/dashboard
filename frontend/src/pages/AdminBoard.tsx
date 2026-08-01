// Kanban board (Sprint 8): a lightweight two-column task board for the team.
// The board body lives in BoardPanel so it can also be embedded on the
// Übersicht; this page just adds the standalone heading.

import BoardPanel from "../components/admin/BoardPanel";

export default function AdminBoard() {
  return (
    <div>
      <h1 className="text-ui font-semibold text-ink sm:text-editorial-4">Board</h1>
      <p className="mt-1 text-label text-muted">
        Aufgaben fürs Team — ziehe Karten zwischen den Spalten oder nutze die
        Pfeile.
      </p>
      <div className="mt-6">
        <BoardPanel />
      </div>
    </div>
  );
}
