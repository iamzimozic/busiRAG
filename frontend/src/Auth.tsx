import { useState } from "react";
import { loginUser, registerUser } from "./api/rag";
import {
  DEMO_EMAIL,
  DEMO_MODE,
  DEMO_PASSWORD,
  HAS_DEMO_LOGIN,
} from "./config";

type AuthMode = "login" | "register";

type AuthProps = {
  onAuthenticated: () => void;
};

function Auth({ onAuthenticated }: AuthProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function signIn(
    signInEmail: string,
    signInPassword: string,
    register: boolean,
  ) {
    setLoading(true);
    setError(null);

    try {
      if (register) {
        await registerUser(signInEmail, signInPassword);
      }

      const result = await loginUser(signInEmail, signInPassword);

      localStorage.setItem("access_token", result.access_token);

      onAuthenticated();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong.",
      );
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    signIn(email, password, mode === "register");
  }

  return (
    <main className="auth-page">
      <div className="auth-card">
        <div className="logo">BusiRAG</div>

        <p className="auth-tagline">
          Answers from financial filings, with citations to the exact source
          passage.
        </p>

        {HAS_DEMO_LOGIN && (
          <>
            <button
              type="button"
              className="send-button auth-demo-button"
              onClick={() => signIn(DEMO_EMAIL, DEMO_PASSWORD, false)}
              disabled={loading}
            >
              {loading ? "Signing in…" : "Try the demo"}
            </button>

            <p className="auth-demo-note">
              Read-only workspace with Apple, Microsoft, NVIDIA and JPMorgan
              Chase annual reports.
            </p>

            <div className="auth-divider">
              <span>or sign in</span>
            </div>
          </>
        )}

        {!HAS_DEMO_LOGIN && (
          <h1 className="auth-title">
            {mode === "login" ? "Sign in" : "Create your account"}
          </h1>
        )}

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            <span>Email</span>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>

          <label>
            <span>Password</span>
            <input
              type="password"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={8}
              required
            />
          </label>

          {error && (
            <p className="auth-error" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            className={
              HAS_DEMO_LOGIN ? "auth-secondary-button" : "send-button"
            }
            disabled={loading}
          >
            {loading
              ? "Please wait…"
              : mode === "login"
                ? "Sign in"
                : "Create account"}
          </button>
        </form>

        {!DEMO_MODE && (
          <button
            type="button"
            className="auth-switch"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
          >
            {mode === "login"
              ? "Create an account"
              : "Already have an account? Sign in"}
          </button>
        )}
      </div>
    </main>
  );
}

export default Auth;
