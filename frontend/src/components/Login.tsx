import React from "react";
import { KeyRound, LogIn, ShieldCheck } from "lucide-react";
import { apiPost, errorMessage } from "../api";
import { AUTH_MODE, AZURE_CONFIG, clearSignedOut, setSession, signInWithAzure } from "../auth";
import type { DevUser } from "../types";
import { Modal } from "./Modal";
import { Field, FormStatus, TextInput } from "./ui";

/**
 * Sign-in and the forced password change.
 *
 * Entra ID is the way in; the password form beside it is the emergency door
 * for the day the app registration is wrong or the tenant unreachable. Both
 * end in the same place, so the rest of the application never has to ask which
 * one was used.
 */

type LoginResult = { token: string; expires_at: string; must_change_password: boolean };

export function SignInScreen({
  error,
  devUsers = [],
  passwordLoginEnabled = true,
  onSignedIn,
  onSelectUser,
  onRetry,
}: {
  error: string | null;
  devUsers?: DevUser[];
  passwordLoginEnabled?: boolean;
  onSignedIn: () => void;
  onSelectUser?: (userId: string) => void;
  onRetry: () => void;
}) {
  const [busy, setBusy] = React.useState(false);
  const [problem, setProblem] = React.useState<string | null>(null);
  const [showPassword, setShowPassword] = React.useState(AUTH_MODE !== "azure_ad");

  async function signInWithPassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setProblem(null);
    try {
      const result = await apiPost<LoginResult>("/api/auth/login", {
        email: String(data.get("email") || "").trim(),
        password: String(data.get("password") || ""),
      });
      setSession({ token: result.token, expiresAt: result.expires_at });
      onSignedIn();
    } catch (caught) {
      setProblem(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function signInWithMicrosoft() {
    setBusy(true);
    setProblem(null);
    try {
      await signInWithAzure();
      onSignedIn();
    } catch (caught) {
      setProblem(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ops-signin">
      <section className="pds-card ops-login">
        <div className="ops-row">
          <span className="pds-logo">BS</span>
          <h1 className="pds-page__title" style={{ fontSize: 20 }}>
            Anmeldung
          </h1>
        </div>
        <p className="pds-meta">
          Ops-Plattform der Niederlassungen. Der Zugang laeuft ueber das Firmenkonto.
        </p>

        {(problem || error) && (
          <div className="pds-banner pds-banner--danger">{problem ?? error}</div>
        )}

        {AUTH_MODE === "azure_ad" && (
          <button
            type="button"
            className="pds-btn pds-btn--primary"
            disabled={busy}
            onClick={signInWithMicrosoft}
          >
            <ShieldCheck size={16} /> Mit Microsoft anmelden
          </button>
        )}

        {AUTH_MODE === "dev" && (
          <>
            <div className="pds-banner">
              Entwicklungsmodus: die Identitaet wird sonst oben rechts ausgewaehlt. Mit Passwort
              meldet sich der Notfallzugang an.
            </div>
            {devUsers.length > 0 && onSelectUser && (
              <button
                type="button"
                className="pds-btn pds-btn--outline"
                onClick={() => {
                  clearSignedOut();
                  onSelectUser(devUsers[0].id);
                }}
              >
                Ohne Anmeldung fortfahren (Entwicklungsmodus)
              </button>
            )}
          </>
        )}

        {passwordLoginEnabled && !showPassword && (
          <button
            type="button"
            className="pds-btn pds-btn--link"
            onClick={() => setShowPassword(true)}
          >
            <KeyRound size={14} /> Stattdessen mit Passwort anmelden
          </button>
        )}

        {passwordLoginEnabled && showPassword && (
          <form className="ops-stack" onSubmit={signInWithPassword}>
            <Field label="E-Mail" span>
              <TextInput name="email" type="email" required autoComplete="username" autoFocus />
            </Field>
            <Field label="Passwort" span>
              <TextInput
                name="password"
                type="password"
                required
                autoComplete="current-password"
              />
            </Field>
            <button type="submit" className="pds-btn pds-btn--primary" disabled={busy}>
              <LogIn size={16} /> {busy ? "Anmeldung laeuft..." : "Anmelden"}
            </button>
            <p className="pds-meta">
              Der Notfallzugang ist fuer den Fall gedacht, dass die Microsoft-Anmeldung nicht
              funktioniert. Das Startpasswort muss bei der ersten Anmeldung geaendert werden.
            </p>
          </form>
        )}

        {error && (
          <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onRetry}>
            Erneut versuchen
          </button>
        )}
      </section>
    </div>
  );
}

/**
 * Changing one's own password.
 *
 * `forced` is the first login with a handed-over start password: the dialog
 * cannot be closed, because the API answers nothing else until it is done.
 */
export function PasswordDialog({
  forced,
  onClose,
  onChanged,
}: {
  forced: boolean;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [busy, setBusy] = React.useState(false);
  const [problem, setProblem] = React.useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const next = String(data.get("new_password") || "");
    if (next !== String(data.get("repeat") || "")) {
      setProblem("Die beiden neuen Passwoerter stimmen nicht ueberein.");
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      const result = await apiPost<LoginResult>("/api/auth/change-password", {
        current_password: String(data.get("current_password") || ""),
        new_password: next,
      });
      // The change retires every earlier token, including the one that sent
      // this request - the response carries the replacement.
      setSession({ token: result.token, expiresAt: result.expires_at });
      onChanged();
    } catch (caught) {
      setProblem(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      size="sm"
      title={forced ? "Startpasswort aendern" : "Passwort aendern"}
      subtitle={
        forced
          ? "Solange das Startpasswort gilt, ist sonst nichts moeglich."
          : "Gilt sofort; alle offenen Sitzungen werden beendet."
      }
      onClose={forced ? () => undefined : onClose}
      closeGuard={forced ? () => false : undefined}
      footer={
        <>
          {!forced && (
            <button type="button" className="pds-btn pds-btn--outline pds-btn--sm" onClick={onClose}>
              Abbrechen
            </button>
          )}
          <span className="ops-spacer" />
          <button
            type="submit"
            form="password-form"
            className="pds-btn pds-btn--primary pds-btn--sm"
            disabled={busy}
          >
            {busy ? "Wird gespeichert..." : "Passwort setzen"}
          </button>
        </>
      }
    >
      <form id="password-form" className="ops-dialog__body" onSubmit={submit}>
        <FormStatus error={problem} busy={false} />
        <Field label="Aktuelles Passwort" span>
          <TextInput
            name="current_password"
            type="password"
            required
            autoComplete="current-password"
            autoFocus
          />
        </Field>
        <Field label="Neues Passwort" span>
          <TextInput name="new_password" type="password" required autoComplete="new-password" />
        </Field>
        <Field label="Neues Passwort wiederholen" span>
          <TextInput name="repeat" type="password" required autoComplete="new-password" />
        </Field>
        <p className="pds-meta">
          Mindestens 12 Zeichen und drei der vier Arten: Kleinbuchstaben, Grossbuchstaben, Ziffern,
          Sonderzeichen. Nicht der eigene Name und nicht das Startpasswort.
        </p>
      </form>
    </Modal>
  );
}
