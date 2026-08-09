import React from "react";
import { X } from "lucide-react";

/**
 * Dialog on top of the native `<dialog>` element.
 *
 * `showModal()` brings the focus trap, Escape handling, the backdrop, body
 * scroll locking and top-layer stacking with it - all of which a hand-rolled
 * overlay gets subtly wrong, and none of which is worth a dependency.
 */
export function Modal({
  open,
  title,
  subtitle,
  size = "md",
  onClose,
  children,
  footer,
  closeGuard,
}: {
  open: boolean;
  title: string;
  subtitle?: React.ReactNode;
  size?: "sm" | "md" | "lg";
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  /** Returns false to keep the dialog open, e.g. for unsaved changes. */
  closeGuard?: () => boolean;
}) {
  const ref = React.useRef<HTMLDialogElement>(null);

  React.useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  React.useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    // Escape and the backdrop close the element directly; without this the
    // React state would still believe the dialog is open.
    const onNativeClose = () => onClose();
    const onCancel = (event: Event) => {
      if (closeGuard && !closeGuard()) event.preventDefault();
    };
    dialog.addEventListener("close", onNativeClose);
    dialog.addEventListener("cancel", onCancel);
    return () => {
      dialog.removeEventListener("close", onNativeClose);
      dialog.removeEventListener("cancel", onCancel);
    };
  }, [onClose, closeGuard]);

  function requestClose() {
    if (closeGuard && !closeGuard()) return;
    onClose();
  }

  return (
    <dialog
      ref={ref}
      className={`ops-dialog${size === "md" ? "" : ` ops-dialog--${size}`}`}
      aria-label={title}
      onClick={(event) => {
        // A click on the element itself is a click on the backdrop; the frame
        // below stops propagation for everything inside.
        if (event.target === ref.current) requestClose();
      }}
    >
      <div className="ops-dialog__frame" onClick={(event) => event.stopPropagation()}>
        <div className="ops-dialog__head">
          <div style={{ minWidth: 0, flex: 1 }}>
            <h2 className="ops-dialog__title">{title}</h2>
            {subtitle && <p className="pds-meta" style={{ margin: "4px 0 0" }}>{subtitle}</p>}
          </div>
          <button type="button" className="pds-icon-btn" onClick={requestClose} aria-label="Schliessen">
            <X size={15} />
          </button>
        </div>
        {children}
        {footer && <div className="ops-dialog__foot">{footer}</div>}
      </div>
    </dialog>
  );
}

/**
 * Confirmation dialog, replacing `window.confirm`.
 *
 * The browser prompt cannot be formatted, so it could not say what a delete
 * actually takes with it.
 */
export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = "Loeschen",
  busy = false,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  body: React.ReactNode;
  confirmLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal open={open} title={title} size="sm" onClose={onCancel}>
      <div className="ops-dialog__body">{body}</div>
      <div className="ops-dialog__foot">
        <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onCancel}>
          Abbrechen
        </button>
        <span className="ops-spacer" />
        <button
          type="button"
          className="pds-btn pds-btn--danger pds-btn--sm"
          disabled={busy}
          onClick={onConfirm}
        >
          {busy ? "Wird geloescht..." : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
