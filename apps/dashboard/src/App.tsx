import { useEffect, useState } from "react";

export default function App() {
  const [health, setHealth] = useState<string>("checking coordinator…");

  useEffect(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((j) => setHealth(JSON.stringify(j)))
      .catch((e) => setHealth(`unreachable: ${e}`));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: 24 }}>
      <h1>CreatorLab Dashboard — Sprint 0 stub</h1>
      <p>Full contributor + network views land in Sprint 16.</p>
      <p>
        Coordinator /health: <code>{health}</code>
      </p>
    </main>
  );
}
