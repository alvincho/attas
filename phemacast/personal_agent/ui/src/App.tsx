export function App() {
  return (
    <main style={{ padding: "2rem", fontFamily: "\"Avenir Next\", sans-serif" }}>
      <h1>Phemacast Personal Agent UI</h1>
      <p>
        The live early-development runtime is currently served from
        {" "}
        <code>phemacast/personal_agent/static/personal_agent.jsx</code>
        {" "}
        so the React rebuild can run without waiting on package installation.
      </p>
      <p>
        Once frontend dependencies are available, this Vite entrypoint can be promoted
        to the main source of truth and built into <code>../static</code>.
      </p>
    </main>
  );
}
