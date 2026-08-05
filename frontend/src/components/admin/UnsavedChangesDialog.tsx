import type { useBlocker } from "react-router-dom";
import ConfirmDialog from "../ui/ConfirmDialog";

type NavigationBlocker = ReturnType<typeof useBlocker>;

export default function UnsavedChangesDialog({
  blocker,
}: {
  blocker: NavigationBlocker;
}) {
  return (
    <ConfirmDialog
      open={blocker.state === "blocked"}
      title="Ungespeicherte Änderungen"
      message="Beim Verlassen gehen deine noch nicht gespeicherten Änderungen verloren."
      confirmText="Änderungen verwerfen"
      variant="danger"
      onConfirm={() => blocker.proceed?.()}
      onCancel={() => blocker.reset?.()}
    />
  );
}
