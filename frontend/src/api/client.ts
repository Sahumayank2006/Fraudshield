/**
 * FraudShield Frontend API Client (src/api/client.ts)
 * Typed fetch wrappers and SSE connection management.
 */

const BASE_URL = "/api";

export interface TransactionData {
  txn_id: string;
  ts: number;
  account_id: string;
  merchant_id: string;
  merchant_category: string;
  amount: number;
  channel: string;
  fraud_probability: number;
  anomaly_score: number;
  decision: "APPROVE" | "REVIEW" | "BLOCK";
  model_version: string;
  latency_ms: number;
  top_reasons: Array<{
    feature: string;
    headline: string;
    description: string;
    shap_value: number;
    feature_value: number;
    severity: "HIGH" | "MEDIUM" | "LOW";
    icon: string;
  }>;
  waterfall?: Array<{
    step: string;
    delta: number;
    start_value?: number;
    end_value: number;
    type: string;
  }>;
  thresholds: { t1: number; t2: number };
  is_attack_burst?: boolean;
  attack_typology?: string;
  session_stats?: Record<string, any>;
}

export async function fetchHealth() {
  const res = await fetch(`${BASE_URL}/health`);
  return res.json();
}

export async function fetchOverview() {
  const res = await fetch(`${BASE_URL}/overview`);
  return res.json();
}

export async function scoreTransaction(payload: any) {
  const res = await fetch(`${BASE_URL}/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return res.json();
}

export async function fetchCases(status: string = "ALL", limit: number = 50) {
  const res = await fetch(`${BASE_URL}/cases?status=${encodeURIComponent(status)}&limit=${limit}`);
  return res.json();
}

export async function fetchCase(caseId: string) {
  const res = await fetch(`${BASE_URL}/cases/${encodeURIComponent(caseId)}`);
  return res.json();
}

export async function updateCase(caseId: string, status?: string, notes?: string) {
  const res = await fetch(`${BASE_URL}/cases/${encodeURIComponent(caseId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, notes }),
  });
  return res.json();
}

export async function fetchExperiments() {
  const res = await fetch(`${BASE_URL}/experiments`);
  return res.json();
}

export async function fetchCurves() {
  const res = await fetch(`${BASE_URL}/curves`);
  return res.json();
}

export async function fetchGlobalShap() {
  const res = await fetch(`${BASE_URL}/explain/global`);
  return res.json();
}

export async function fetchThresholdSim(t1?: number, t2?: number, costMode: string = "amount_weighted") {
  const params = new URLSearchParams();
  if (t1 !== undefined) params.append("t1", t1.toString());
  if (t2 !== undefined) params.append("t2", t2.toString());
  params.append("cost_mode", costMode);
  const res = await fetch(`${BASE_URL}/threshold/sim?${params.toString()}`);
  return res.json();
}

export async function fetchDrift() {
  const res = await fetch(`${BASE_URL}/drift`);
  return res.json();
}

export async function triggerRetrain() {
  const res = await fetch(`${BASE_URL}/retrain`, { method: "POST" });
  return res.json();
}

export async function triggerRollback() {
  const res = await fetch(`${BASE_URL}/rollback`, { method: "POST" });
  return res.json();
}

export async function fetchFairness() {
  const res = await fetch(`${BASE_URL}/fairness`);
  return res.json();
}

export async function uploadBatchCsv(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BASE_URL}/score/batch`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw errorBody;
  }
  return res.json();
}

export const BATCH_SAMPLE_CSV_URL = `${BASE_URL}/score/batch/sample`;
export const BATCH_DOWNLOAD_FLAGGED_URL = `${BASE_URL}/score/batch/download`;

export async function fetchDatasets() {
  const res = await fetch(`${BASE_URL}/datasets`);
  return res.json();
}

export async function fetchHypotheses() {
  const res = await fetch(`${BASE_URL}/hypotheses`);
  return res.json();
}

export async function controlStream(action: string, speed?: number, attackType?: string) {
  const res = await fetch(`${BASE_URL}/stream/control`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, speed, attack_type: attackType }),
  });
  return res.json();
}

export async function triggerAttack(attackType: string, count: number = 15) {
  const res = await fetch(`${BASE_URL}/stream/attack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ attack_type: attackType, count }),
  });
  return res.json();
}

/**
 * React hook to connect to the Server-Sent Events (SSE) live replay stream.
 */
import { useEffect, useRef, useState } from "react";

export function useSseStream(
  onTransaction: (tx: TransactionData) => void,
  speed: number = 2.0,
  enabled: boolean = true
) {
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        setIsConnected(false);
      }
      return;
    }

    const sseUrl = `${BASE_URL}/stream?speed=${speed}`;
    const es = new EventSource(sseUrl);
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
    };

    es.onmessage = (event) => {
      try {
        if (!event.data || event.data.startsWith(":")) return; // Heartbeat
        const parsed = JSON.parse(event.data);
        if (parsed.type === "TRANSACTION" && parsed.data) {
          onTransaction(parsed.data);
        }
      } catch (err) {
        console.error("Error parsing SSE event:", err);
      }
    };

    es.onerror = () => {
      setIsConnected(false);
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    };
  }, [enabled, speed, onTransaction]);

  return { isConnected };
}

