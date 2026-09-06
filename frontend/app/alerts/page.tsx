"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Avatar } from "@/components/ds/Avatar";
import { Button } from "@/components/ds/Button";
import { glassCard } from "@/components/ds/glass";
import { Switch } from "@/components/ds/Switch";
import { useAlerts, useCreateAlert, useDeleteAlert, useWatchlist } from "@/lib/hooks";

export default function AlertsPage() {
  return (
    <Suspense fallback={<p style={{ color: "var(--text-tertiary)" }}>Loading…</p>}>
      <AlertsPageInner />
    </Suspense>
  );
}

function AlertsPageInner() {
  const searchParams = useSearchParams();
  const { data: watchlist } = useWatchlist();
  const { data: alerts, isLoading } = useAlerts();
  const createMutation = useCreateAlert();
  const deleteMutation = useDeleteAlert();

  const [instrumentId, setInstrumentId] = useState(searchParams.get("instrument") ?? "");
  const [smart, setSmart] = useState(true);
  const [manualOpen, setManualOpen] = useState(false);
  const [targetPrice, setTargetPrice] = useState("");

  useEffect(() => {
    const fromQuery = searchParams.get("instrument");
    if (fromQuery) setInstrumentId(fromQuery);
  }, [searchParams]);

  const canSubmit = instrumentId && (smart || targetPrice.trim() !== "");

  return (
    <div style={{ fontFamily: "var(--font-body)", maxWidth: 560, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        {instrumentId && <Avatar label={instrumentId} size="sm" shape="square" />}
        <span style={{ fontWeight: 800, fontSize: 18, fontFamily: "var(--font-display)" }}>
          Set alert{instrumentId ? ` · ${instrumentId}` : ""}
        </span>
      </div>

      <select
        value={instrumentId}
        onChange={(e) => setInstrumentId(e.target.value)}
        style={{ width: "100%", padding: "10px 12px", borderRadius: "var(--radius-md)", fontFamily: "var(--font-body)", fontSize: 14, marginBottom: 16, ...glassCard }}
      >
        <option value="">Select a watched instrument…</option>
        {(watchlist ?? []).map((item) => (
          <option key={item.instrument_id} value={item.instrument_id}>
            {item.instrument_id}
          </option>
        ))}
      </select>

      <div style={{ padding: 20, borderRadius: "var(--radius-lg)", boxShadow: "0 0 0 2px var(--text-positive)", background: "var(--green-50)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 800, color: "var(--text-positive)", letterSpacing: 0.5 }}>RECOMMENDED</span>
            <span style={{ fontSize: 16, fontWeight: 800 }}>Notify me on significant change</span>
            <span style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 500 }}>
              Alerts only when the move is unusual for this instrument — reuses the same significance engine behind the Attention Feed, not a flat threshold.
            </span>
          </div>
          <Switch checked={smart} onChange={setSmart} />
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <div
          onClick={() => setManualOpen(!manualOpen)}
          style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 4px", cursor: "pointer", opacity: 0.75 }}
        >
          <span style={{ fontSize: 14, color: "var(--text-secondary)" }}>Set a manual target price instead</span>
          <span style={{ fontSize: 13, color: "var(--text-tertiary)" }}>{manualOpen ? "▲" : "▼"}</span>
        </div>
        {manualOpen && (
          <div style={{ marginTop: 8, padding: 16, borderRadius: "var(--radius-md)", display: "flex", flexDirection: "column", gap: 10, ...glassCard }}>
            <span style={{ fontSize: 13, color: "var(--text-secondary)", fontWeight: 600 }}>Alert me when price crosses</span>
            <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "12px 14px", borderRadius: "var(--radius-md)", background: "var(--surface-sunken)" }}>
              <span style={{ fontWeight: 700, fontSize: 16 }}>₹</span>
              <input
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value)}
                placeholder="300.00"
                type="number"
                step="0.01"
                style={{ border: "none", outline: "none", flex: 1, fontFamily: "var(--font-body)", fontWeight: 500, fontSize: 16, background: "transparent" }}
              />
            </div>
          </div>
        )}
      </div>

      <Button
        variant="primary"
        size="lg"
        fullWidth
        disabled={!canSubmit || createMutation.isPending}
        onClick={() => {
          if (!canSubmit) return;
          createMutation.mutate(
            { instrument_id: instrumentId, target_price: targetPrice.trim() === "" ? null : Number(targetPrice), notify_on_significant_change: smart },
            { onSuccess: () => setTargetPrice("") }
          );
        }}
      >
        Save alert
      </Button>

      <div style={{ marginTop: 32 }}>
        <span style={{ fontSize: 14, fontWeight: 500, color: "var(--text-secondary)" }}>Existing alerts</span>
        {isLoading && <p style={{ color: "var(--text-tertiary)", fontSize: 13 }}>Loading…</p>}
        {alerts && alerts.length === 0 && <p style={{ color: "var(--text-tertiary)", fontSize: 13 }}>No alerts set up yet.</p>}
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
          {(alerts ?? []).map((alert) => (
            <div key={alert.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", borderRadius: "var(--radius-md)", ...glassCard }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{alert.instrument_id}</div>
                <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>
                  {alert.condition.target_price !== null && `Target ₹${alert.condition.target_price}`}
                  {alert.condition.target_price !== null && alert.condition.notify_on_significant_change && " · "}
                  {alert.condition.notify_on_significant_change && "Significant change"}
                </div>
              </div>
              <span onClick={() => deleteMutation.mutate(alert.id)} style={{ fontSize: 13, color: "var(--text-tertiary)", cursor: "pointer" }}>
                Remove
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
