import { useEffect, useState } from "react";
import ContributorView from "./components/ContributorView";
import MyNodeView from "./components/MyNodeView";
import NetworkView from "./components/NetworkView";

type Tab = "mynode" | "workers" | "network";

export default function App() {
  const [tab, setTab] = useState<Tab>("mynode");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setTick((t) => t + 1), 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <h1>CommunityCompute Dashboard</h1>
      <nav>
        <button disabled={tab === "mynode"} onClick={() => setTab("mynode")}>
          My node
        </button>{" "}
        <button disabled={tab === "workers"} onClick={() => setTab("workers")}>
          Workers
        </button>{" "}
        <button disabled={tab === "network"} onClick={() => setTab("network")}>
          Network
        </button>
      </nav>
      <hr />
      {tab === "mynode" && <MyNodeView refreshTick={tick} />}
      {tab === "workers" && <ContributorView refreshTick={tick} />}
      {tab === "network" && <NetworkView refreshTick={tick} />}
      <style>{`
        .card { border: 1px solid #ccc; border-radius: 8px; padding: 12px 16px; margin: 12px 0; }
        .card header { display: flex; gap: 12px; align-items: center; }
        .pill { color: #fff; padding: 2px 10px; border-radius: 999px; font-size: 12px; }
        .card dl div { display: flex; gap: 8px; margin: 4px 0; }
        .card dt { min-width: 120px; font-weight: 600; }
        .error { color: #b71c1c; }
        .statgrid { display: flex; gap: 12px; flex-wrap: wrap; }
        .stat { border: 1px solid #ccc; border-radius: 8px; padding: 8px 14px; min-width: 120px; }
        .stat span { display: block; font-size: 12px; color: #555; }
        .stat small { display: block; font-size: 11px; color: #777; }
        .bar { height: 8px; background: #eee; border-radius: 4px; margin: 4px 0; max-width: 400px; }
        .fill { height: 100%; background: #2e7d32; border-radius: 4px; }
      `}</style>
    </main>
  );
}
