"use client";
import { useState, useEffect, useCallback, Fragment } from "react";

const API = "http://localhost:8000";

type ImageAnalysis = {
  result: "PASS" | "FAIL" | "RECHECK";
  anomaly_score: number;
  defect_type: string | null;
  confidence: number;
  component: string | null;
  explanation: string;
  heatmap_b64: string;
  mode: string;
  image_id?: string;
};

type Defect = { type: string; camera: number; angle: number; confidence: number };
type InspectionResult = {
  inspection_id: number;
  cooler_serial: string;
  result: "PASS" | "FAIL" | "RECHECK";
  defects: Defect[];
  duration_seconds: number;
  frames_analysed: number;
  fail_reasons: string[];
};
type Stats = {
  total: number; passed: number; failed: number;
  recheck: number; unsynced: number; pass_rate_percent: number;
};
type HistoryRow = {
  id: number; cooler_serial: string; result: string;
  started_at: string; duration_seconds: number | null; synced_cloud: boolean;
};

const BADGE: Record<string, string> = {
  PASS:    "bg-green-600 text-white",
  FAIL:    "bg-red-600 text-white",
  RECHECK: "bg-yellow-500 text-black",
};

function ResultBadge({ result }: { result: string }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-bold ${BADGE[result] ?? "bg-gray-500 text-white"}`}>
      {result}
    </span>
  );
}

function StatCard({ label, value, sub, color }: { label: string; value: number | string; sub?: string; color?: string }) {
  return (
    <div className="bg-gray-800 rounded-xl p-4 text-center border border-gray-700">
      <div className={`text-3xl font-bold ${color ?? "text-white"}`}>{value}</div>
      <div className="text-gray-400 text-sm mt-1">{label}</div>
      {sub && <div className="text-gray-500 text-xs mt-0.5">{sub}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [serial, setSerial]       = useState("");
  const [running, setRunning]     = useState(false);
  const [lastResult, setLast]     = useState<InspectionResult | null>(null);
  const [imgFile, setImgFile]     = useState<File | null>(null);
  const [imgPreview, setImgPreview] = useState<string | null>(null);
  const [imgAnalysis, setImgAnalysis] = useState<ImageAnalysis | null>(null);
  const [imgRunning, setImgRunning] = useState(false);
  const [dragOver, setDragOver]   = useState(false);
  // Feedback state
  const [fbState, setFbState]     = useState<"idle"|"wrong_pick"|"done">("idle");
  const [fbActual, setFbActual]   = useState<"PASS"|"FAIL"|null>(null);
  const [fbType, setFbType]       = useState("");
  const [fbSending, setFbSending] = useState(false);
  const [stats, setStats]         = useState<Stats | null>(null);
  const [history, setHistory]     = useState<HistoryRow[]>([]);
  const [filter, setFilter]       = useState<"ALL" | "PASS" | "FAIL" | "RECHECK">("ALL");
  const [online, setOnline]       = useState(true);
  const [aiMode, setAiMode]       = useState<string>("–");
  const [expanded, setExpanded]   = useState<number | null>(null);
  const [lastRefresh, setRefresh] = useState<Date | null>(null);

  const checkOnline = useCallback(async () => {
    try {
      const r = await fetch(`${API}/health`);
      const d = await r.json();
      setOnline(true);
      setAiMode(d.ai_engine === "ready" ? "ready" : "offline");
    } catch {
      setOnline(false);
      setAiMode("offline");
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const r = await fetch(`${API}/stats`);
      setStats(await r.json());
      setRefresh(new Date());
    } catch {}
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const url = filter === "ALL"
        ? `${API}/history?limit=20`
        : `${API}/history?limit=20&result_filter=${filter}`;
      const r = await fetch(url);
      const d = await r.json();
      setHistory(d.items ?? []);
    } catch {}
  }, [filter]);

  useEffect(() => {
    checkOnline(); fetchStats(); fetchHistory();
    const id = setInterval(() => { checkOnline(); fetchStats(); }, 6000);
    return () => clearInterval(id);
  }, [checkOnline, fetchStats]);

  useEffect(() => { fetchHistory(); }, [filter, fetchHistory]);

  const onImageDrop = (file: File) => {
    setImgFile(file);
    setImgAnalysis(null);
    const reader = new FileReader();
    reader.onload = e => setImgPreview(e.target?.result as string);
    reader.readAsDataURL(file);
  };

  const analyseImage = async () => {
    if (!imgFile) return;
    setImgRunning(true); setImgAnalysis(null); setFbState("idle"); setFbActual(null); setFbType("");
    try {
      const form = new FormData();
      form.append("file", imgFile);
      const r = await fetch(`${API}/analyse-image`, { method: "POST", body: form });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setImgAnalysis(await r.json());
    } catch (e: any) {
      alert(`Analysis failed: ${e.message}`);
    }
    setImgRunning(false);
  };

  const submitFeedback = async (correct: boolean) => {
    if (!imgAnalysis) return;
    if (correct) {
      setFbState("done");
      return;
    }
    if (!fbActual) return;
    setFbSending(true);
    try {
      await fetch(`${API}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_id: imgAnalysis.image_id ?? "unknown",
          predicted: imgAnalysis.result,
          actual: fbActual,
          correct_type: fbType || null,
          anomaly_score: imgAnalysis.anomaly_score,
        }),
      });
      setFbState("done");
    } catch (e: any) {
      alert(`Feedback failed: ${e.message}`);
    }
    setFbSending(false);
  };

  const startInspection = async () => {
    if (!serial.trim()) return;
    setRunning(true); setLast(null);
    try {
      const r = await fetch(`${API}/inspection/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cooler_serial: serial.trim().toUpperCase() }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setLast(d);
      fetchStats(); fetchHistory();
    } catch (e: any) {
      alert(`Inspection failed: ${e.message}\nIs the backend running on port 8000?`);
    }
    setRunning(false);
  };

  const filtered = filter === "ALL" ? history : history.filter(r => r.result === filter);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Brize Glacier 110</h1>
          <p className="text-gray-500 text-xs mt-0.5">Air Cooler Inspection System</p>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-gray-500 text-xs hidden sm:block">
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <span className={`text-xs px-2 py-1 rounded font-medium ${
            aiMode === "ready" ? "bg-blue-900 text-blue-300" : "bg-gray-700 text-gray-400"
          }`}>
            AI {aiMode}
          </span>
          <span className={`text-xs px-2 py-1 rounded font-medium ${
            online ? "bg-green-900 text-green-300" : "bg-red-900 text-red-400"
          }`}>
            {online ? "ONLINE" : "OFFLINE"}
          </span>
        </div>
      </header>

      <main className="p-6 max-w-5xl mx-auto space-y-6">

        {/* Stats row */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <StatCard label="Total" value={stats.total} />
            <StatCard label="Passed"   value={stats.passed}  color="text-green-400" />
            <StatCard label="Failed"   value={stats.failed}  color="text-red-400" />
            <StatCard label="Recheck"  value={stats.recheck} color="text-yellow-400" />
            <StatCard
              label="Pass Rate"
              value={`${stats.pass_rate_percent}%`}
              sub={`${stats.unsynced} unsynced`}
              color={stats.pass_rate_percent >= 80 ? "text-green-400" : "text-yellow-400"}
            />
          </div>
        )}

        {/* ── Image Analyser ─────────────────────────────────────── */}
        <section className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-base font-semibold mb-4">
            Analyse Image
            <span className="ml-2 text-xs text-gray-500 font-normal">Upload a cooler photo to inspect it</span>
          </h2>

          {/* Drop zone */}
          <div
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => {
              e.preventDefault(); setDragOver(false);
              const f = e.dataTransfer.files[0];
              if (f && f.type.startsWith("image/")) onImageDrop(f);
            }}
            onClick={() => document.getElementById("img-upload")?.click()}
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
              dragOver ? "border-blue-500 bg-blue-950/30" : "border-gray-700 hover:border-gray-500"
            }`}
          >
            <input
              id="img-upload" type="file" accept="image/*" className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) onImageDrop(f); }}
            />
            {imgPreview ? (
              <p className="text-sm text-gray-400">{imgFile?.name} — click to change</p>
            ) : (
              <>
                <div className="text-3xl mb-2">📷</div>
                <p className="text-gray-400 text-sm">Drag & drop an image here, or <span className="text-blue-400">click to browse</span></p>
                <p className="text-gray-600 text-xs mt-1">JPG, PNG — any cooler photo</p>
              </>
            )}
          </div>

          {imgPreview && (
            <div className="mt-4 flex flex-col sm:flex-row gap-4">
              {/* Original or heatmap image */}
              <div className="flex-1 relative">
                <img
                  src={imgAnalysis?.heatmap_b64 || imgPreview}
                  alt="Cooler analysis"
                  className="w-full rounded-lg object-contain max-h-80 bg-black"
                />
                {imgAnalysis && (
                  <div className={`absolute top-2 left-2 px-3 py-1 rounded font-bold text-sm shadow ${
                    BADGE[imgAnalysis.result] ?? "bg-gray-500 text-white"
                  }`}>
                    {imgAnalysis.result}
                  </div>
                )}
                {imgAnalysis?.heatmap_b64 && (
                  <div className="absolute top-2 right-2 text-xs bg-black/70 text-gray-300 px-2 py-0.5 rounded">
                    Heatmap overlay
                  </div>
                )}
              </div>

              {/* Analysis result panel */}
              <div className="sm:w-56 space-y-3">
                {!imgAnalysis ? (
                  <button
                    onClick={analyseImage}
                    disabled={imgRunning}
                    className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 px-4 py-3 rounded-lg font-semibold text-sm"
                  >
                    {imgRunning ? (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="15 45"/>
                        </svg>
                        Analysing…
                      </span>
                    ) : "Analyse Image"}
                  </button>
                ) : (
                  <>
                    <div className={`rounded-lg p-3 ${
                      imgAnalysis.result === "PASS"    ? "bg-green-900/40 border border-green-700" :
                      imgAnalysis.result === "FAIL"    ? "bg-red-900/40 border border-red-700"     :
                                                         "bg-yellow-900/30 border border-yellow-700"
                    }`}>
                      <div className="text-lg font-bold">{imgAnalysis.result}</div>
                      <div className="text-xs text-gray-400 mt-1">
                        Score: {(imgAnalysis.anomaly_score * 100).toFixed(1)}%
                      </div>
                    </div>

                    {imgAnalysis.defect_type && (
                      <div className="bg-red-900/30 border border-red-800 rounded-lg p-3">
                        <div className="text-xs text-red-400 font-semibold uppercase tracking-wide mb-1">Defect</div>
                        <div className="text-sm font-medium capitalize">
                          {imgAnalysis.defect_type.replace(/_/g, " ")}
                        </div>
                        {imgAnalysis.component && (
                          <div className="text-xs text-gray-400 mt-1 capitalize">
                            Part: {imgAnalysis.component.replace(/_/g, " ")}
                          </div>
                        )}
                      </div>
                    )}

                    <div className="bg-gray-800 rounded-lg p-3">
                      <div className="text-xs text-gray-500 mb-1">Explanation</div>
                      <div className="text-xs text-gray-300">{imgAnalysis.explanation}</div>
                      <div className="text-xs text-gray-600 mt-2">Mode: {imgAnalysis.mode}</div>
                    </div>

                    {/* Feedback buttons */}
                    {fbState === "idle" && (
                      <div className="bg-gray-800 rounded-lg p-3">
                        <div className="text-xs text-gray-500 mb-2">Was this correct?</div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => submitFeedback(true)}
                            className="flex-1 bg-green-700 hover:bg-green-600 text-white text-xs py-1.5 rounded font-medium"
                          >✓ Yes</button>
                          <button
                            onClick={() => setFbState("wrong_pick")}
                            className="flex-1 bg-red-800 hover:bg-red-700 text-white text-xs py-1.5 rounded font-medium"
                          >✗ Wrong</button>
                        </div>
                      </div>
                    )}

                    {fbState === "wrong_pick" && (
                      <div className="bg-red-900/30 border border-red-800 rounded-lg p-3 space-y-2">
                        <div className="text-xs text-red-300 font-semibold">What was it actually?</div>
                        <div className="flex gap-2">
                          {(["PASS", "FAIL"] as const).map(v => (
                            <button
                              key={v}
                              onClick={() => setFbActual(v)}
                              className={`flex-1 text-xs py-1.5 rounded font-medium border ${
                                fbActual === v
                                  ? v === "PASS" ? "bg-green-700 border-green-500 text-white"
                                                 : "bg-red-700 border-red-500 text-white"
                                  : "bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700"
                              }`}
                            >{v}</button>
                          ))}
                        </div>
                        {fbActual === "FAIL" && (
                          <input
                            className="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-white placeholder-gray-500"
                            placeholder="Correct defect type (optional)"
                            value={fbType}
                            onChange={e => setFbType(e.target.value)}
                          />
                        )}
                        <button
                          disabled={!fbActual || fbSending}
                          onClick={() => submitFeedback(false)}
                          className="w-full bg-orange-700 hover:bg-orange-600 disabled:bg-gray-700 text-white text-xs py-2 rounded font-semibold"
                        >{fbSending ? "Saving…" : "Save Correction"}</button>
                      </div>
                    )}

                    {fbState === "done" && (
                      <div className="bg-green-900/30 border border-green-700 rounded-lg p-3 text-xs text-green-300 text-center">
                        ✓ Feedback saved — model will improve after retraining
                      </div>
                    )}

                    <button
                      onClick={() => { setImgAnalysis(null); setImgPreview(null); setImgFile(null); setFbState("idle"); }}
                      className="w-full bg-gray-800 hover:bg-gray-700 text-gray-400 px-4 py-2 rounded-lg text-sm"
                    >
                      Clear
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </section>

        {/* New inspection */}
        <section className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <h2 className="text-base font-semibold mb-4">New Inspection</h2>
          <div className="flex gap-3">
            <input
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:border-blue-500 focus:outline-none text-sm"
              placeholder="Cooler serial — e.g. COOL-001"
              value={serial}
              onChange={e => setSerial(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !running && startInspection()}
              disabled={running}
            />
            <button
              onClick={startInspection}
              disabled={running || !serial.trim()}
              className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 px-5 py-2.5 rounded-lg font-semibold text-sm transition-colors min-w-[140px]"
            >
              {running ? (
                <span className="flex items-center gap-2 justify-center">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeDasharray="15 45" />
                  </svg>
                  Inspecting…
                </span>
              ) : "Start Inspection"}
            </button>
          </div>

          {/* Last result */}
          {lastResult && (
            <div className="mt-5 rounded-lg border border-gray-700 overflow-hidden">
              <div className={`px-4 py-3 flex items-center gap-4 ${
                lastResult.result === "PASS"    ? "bg-green-900/40" :
                lastResult.result === "FAIL"    ? "bg-red-900/40"   :
                                                  "bg-yellow-900/30"
              }`}>
                <span className={`text-2xl font-bold px-4 py-1 rounded ${
                  BADGE[lastResult.result] ?? ""
                }`}>
                  {lastResult.result}
                </span>
                <div>
                  <div className="font-semibold">{lastResult.cooler_serial}</div>
                  <div className="text-gray-400 text-xs">
                    {lastResult.frames_analysed} frames · {lastResult.duration_seconds?.toFixed(1)}s
                  </div>
                </div>
              </div>
              {lastResult.defects?.length > 0 ? (
                <div className="px-4 py-3 bg-gray-800/50">
                  <div className="text-red-400 text-xs font-semibold uppercase tracking-wide mb-2">
                    {lastResult.defects.length} defect{lastResult.defects.length > 1 ? "s" : ""} detected
                  </div>
                  <div className="space-y-1">
                    {lastResult.defects.map((d, i) => (
                      <div key={i} className="flex items-center gap-3 text-sm">
                        <span className="text-red-400 font-medium capitalize">{d.type?.replace(/_/g, " ")}</span>
                        <span className="text-gray-500 text-xs">Cam {d.camera} · {d.angle}°</span>
                        <span className="ml-auto text-gray-400 text-xs">{(d.confidence * 100).toFixed(0)}% conf</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : lastResult.result === "PASS" ? (
                <div className="px-4 py-3 text-green-400 text-sm bg-gray-800/30">
                  ✓ All {lastResult.frames_analysed} frames clean — no defects
                </div>
              ) : (
                <div className="px-4 py-3 text-yellow-400 text-sm bg-gray-800/30">
                  {lastResult.fail_reasons?.join(", ") || "Needs manual review"}
                </div>
              )}
            </div>
          )}
        </section>

        {/* History */}
        <section className="bg-gray-900 rounded-xl border border-gray-800 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold">Inspection History</h2>
            <div className="flex gap-1">
              {(["ALL", "PASS", "FAIL", "RECHECK"] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`text-xs px-3 py-1 rounded font-medium transition-colors ${
                    filter === f
                      ? f === "PASS"    ? "bg-green-700 text-white"
                      : f === "FAIL"    ? "bg-red-700 text-white"
                      : f === "RECHECK" ? "bg-yellow-600 text-black"
                      :                   "bg-blue-700 text-white"
                      : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          {filtered.length === 0 ? (
            <div className="text-gray-500 text-sm py-6 text-center">No inspections yet</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase tracking-wide border-b border-gray-800">
                    <th className="text-left py-2 pr-4">ID</th>
                    <th className="text-left py-2 pr-4">Serial</th>
                    <th className="text-left py-2 pr-4">Result</th>
                    <th className="text-left py-2 pr-4">Time</th>
                    <th className="text-left py-2 pr-4">Duration</th>
                    <th className="text-left py-2">Sync</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(row => (
                    <Fragment key={row.id}>
                      <tr
                        onClick={() => setExpanded(expanded === row.id ? null : row.id)}
                        className="border-b border-gray-800/60 hover:bg-gray-800/40 cursor-pointer transition-colors"
                      >
                        <td className="py-2.5 pr-4 text-gray-500">#{row.id}</td>
                        <td className="py-2.5 pr-4 font-medium">{row.cooler_serial}</td>
                        <td className="py-2.5 pr-4"><ResultBadge result={row.result} /></td>
                        <td className="py-2.5 pr-4 text-gray-400 text-xs">
                          {new Date(row.started_at).toLocaleString()}
                        </td>
                        <td className="py-2.5 pr-4 text-gray-400 text-xs">
                          {row.duration_seconds ? `${row.duration_seconds.toFixed(1)}s` : "–"}
                        </td>
                        <td className="py-2.5 text-gray-500 text-xs">
                          {row.synced_cloud ? "✓" : "–"}
                        </td>
                      </tr>
                      {expanded === row.id && (
                        <tr className="bg-gray-800/30">
                          <td colSpan={6} className="px-4 py-3 text-xs text-gray-400">
                            Inspection #{row.id} · {row.cooler_serial} · {row.result}
                            <br />Started: {new Date(row.started_at).toLocaleString()}
                            <br />Cloud sync: {row.synced_cloud ? "synced" : "pending"}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
