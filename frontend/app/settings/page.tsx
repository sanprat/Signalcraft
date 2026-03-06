"use client";

import { useState, useEffect } from "react";

const BROKERS = ["Dhan", "Shoonya", "Flattrade", "Zerodha"];

const BROKER_FIELDS: Record<string, { key: string; label: string; type: string }[]> = {
    Dhan: [
        { key: "client_id", label: "Client ID", type: "text" },
        { key: "access_token", label: "Access Token", type: "password" },
    ],
    Shoonya: [
        { key: "userid", label: "User ID", type: "text" },
        { key: "password", label: "Password", type: "password" },
        { key: "totp_secret", label: "TOTP Secret", type: "password" },
        { key: "vendor_code", label: "Vendor Code", type: "text" },
        { key: "api_secret", label: "API Key / Secret", type: "password" },
        { key: "imei", label: "IMEI (Optional)", type: "text" },
    ],
    Flattrade: [
        { key: "userid", label: "User ID", type: "text" },
        { key: "password", label: "Password", type: "password" },
        { key: "totp_secret", label: "TOTP Secret", type: "password" },
        { key: "vendor_code", label: "Vendor Code", type: "text" },
        { key: "api_secret", label: "API Key / Secret", type: "password" },
    ],
    Zerodha: [
        { key: "api_key", label: "API Key", type: "password" },
        { key: "access_token", label: "Access Token", type: "password" },
    ],
};

// ── Colour tokens ─────────────────────────────────────────────────────────────
const T = {
    bg: '#F8FAFC', surface: '#FFFFFF', surfaceHover: '#F1F5F9',
    border: '#E2E8F0', borderStrong: '#CBD5E1',
    navy: '#0F2744', blue: '#1D4ED8', blueLight: '#EFF6FF', blueMid: '#BFDBFE',
    green: '#059669', greenLight: '#ECFDF5', greenMid: '#A7F3D0',
    red: '#DC2626', redLight: '#FEF2F2', redMid: '#FECACA',
    amber: '#D97706', amberLight: '#FFFBEB',
    teal: '#0D9488', tealLight: '#F0FDFA',
    text: '#0F172A', textMid: '#475569', textMuted: '#94A3B8', pill: '#F1F5F9',
}

export default function SettingsPage() {
    const [selectedBroker, setSelectedBroker] = useState(BROKERS[0]);
    const [credentials, setCredentials] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

    useEffect(() => {
        fetchCredentials(selectedBroker);
    }, [selectedBroker]);

    const fetchCredentials = async (broker: string) => {
        setLoading(true);
        setMessage(null);
        try {
            setCredentials({});
            const token = localStorage.getItem("access_token") || localStorage.getItem("sc_token");
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001"}/api/settings/broker/${broker}`, {
                headers: {
                    Authorization: `Bearer ${token}`
                }
            });
            if (res.ok) {
                const data = await res.json();
                if (data.credentials) {
                    setCredentials(data.credentials);
                }
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setMessage(null);

        try {
            const token = localStorage.getItem("access_token") || localStorage.getItem("sc_token");
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001"}/api/settings/broker`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({
                    broker: selectedBroker,
                    credentials: credentials
                })
            });

            if (res.ok) {
                setMessage({ text: `Credentials for ${selectedBroker} updated successfully!`, type: "success" });
                fetchCredentials(selectedBroker); // reload to get masked passwords
            } else {
                const err = await res.json();
                setMessage({ text: err.detail || "Failed to save credentials", type: "error" });
            }
        } catch (error) {
            setMessage({ text: "Network error saving credentials.", type: "error" });
        } finally {
            setLoading(false);
        }
    };

    const handleChange = (key: string, val: string) => {
        setCredentials((prev) => ({ ...prev, [key]: val }));
    };

    return (
        <div style={{ padding: 24, fontFamily: "'DM Sans', sans-serif", background: T.bg, minHeight: "100vh" }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: T.navy, letterSpacing: '-0.5px' }}>
                        Settings
                    </h1>
                    <p style={{ margin: '4px 0 0', fontSize: 13, color: T.textMuted }}>
                        Manage your broker API connections and credentials
                    </p>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: 24 }}>
                {/* Sidebar */}
                <div style={{
                    background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`,
                    boxShadow: '0 1px 3px rgba(0,0,0,0.04)', overflow: 'hidden'
                }}>
                    <div style={{ padding: '16px 20px', borderBottom: `1px solid ${T.border}`, fontSize: 13, fontWeight: 700, color: T.textMid, letterSpacing: '0.6px', textTransform: 'uppercase' }}>
                        Brokers
                    </div>
                    <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {BROKERS.map((broker) => (
                            <button
                                key={broker}
                                onClick={() => setSelectedBroker(broker)}
                                style={{
                                    width: '100%', padding: '10px 14px', border: 'none', borderRadius: 8,
                                    background: selectedBroker === broker ? T.blueLight : 'transparent',
                                    color: selectedBroker === broker ? T.blue : T.textMid,
                                    fontSize: 14, fontWeight: selectedBroker === broker ? 700 : 500,
                                    cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s'
                                }}
                            >
                                {broker}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Main Content */}
                <div style={{
                    background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`,
                    boxShadow: '0 1px 3px rgba(0,0,0,0.04)', padding: 24
                }}>
                    <h2 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 800, color: T.navy, letterSpacing: '-0.5px' }}>
                        {selectedBroker} Configuration
                    </h2>
                    <p style={{ margin: '0 0 24px', fontSize: 13, color: T.textMuted, lineHeight: 1.5 }}>
                        Configure API keys and credentials for algorithmic trading through {selectedBroker}. Credentials are encrypted and saved securely down to the user-level.
                    </p>

                    {message && (
                        <div style={{
                            padding: '12px 16px', borderRadius: 8, marginBottom: 24, fontSize: 13, fontWeight: 600,
                            display: 'flex', alignItems: 'center', gap: 8, border: `1px solid ${message.type === 'success' ? T.greenMid : T.redMid}`,
                            background: message.type === 'success' ? T.greenLight : T.redLight, color: message.type === 'success' ? T.green : T.red
                        }}>
                            {message.type === 'success' ? '✓' : '⚠'} {message.text}
                        </div>
                    )}

                    <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 480 }}>
                        {BROKER_FIELDS[selectedBroker]?.map((field) => (
                            <div key={field.key}>
                                <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: T.textMid, marginBottom: 6, letterSpacing: '0.5px' }}>
                                    {field.label}
                                </label>
                                <input
                                    type={field.type}
                                    value={credentials[field.key] || ""}
                                    onChange={(e) => handleChange(field.key, e.target.value)}
                                    placeholder={`Enter ${field.label}`}
                                    style={{
                                        width: '100%', padding: '10px 14px', border: `1px solid ${T.borderStrong}`,
                                        borderRadius: 8, fontSize: 14, outline: 'none', transition: 'border 0.2s',
                                        background: T.surface, color: T.text, fontFamily: field.type === 'password' ? 'inherit' : "'DM Mono', monospace"
                                    }}
                                    onFocus={e => e.target.style.borderColor = T.blue}
                                    onBlur={e => e.target.style.borderColor = T.borderStrong}
                                />
                            </div>
                        ))}

                        <div style={{ marginTop: 16, paddingTop: 20, borderTop: `1px solid ${T.border}`, display: 'flex' }}>
                            <button
                                type="submit"
                                disabled={loading}
                                style={{
                                    padding: '10px 20px', background: T.blue, color: '#fff', border: 'none',
                                    borderRadius: 8, fontSize: 14, fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
                                    opacity: loading ? 0.7 : 1, transition: 'background 0.2s'
                                }}
                            >
                                {loading ? "Saving..." : "Save Configuration"}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
}
