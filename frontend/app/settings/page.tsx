"use client";

import { useState, useEffect } from "react";
import { config } from '@/lib/config';

const API = config.apiBaseUrl;
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

// ── Broker Config Panel ────────────────────────────────────────────────────────
function BrokerPanel({ broker }: { broker: string }) {
    const [credentials, setCredentials] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

    useEffect(() => {
        fetchCredentials(broker);
    }, [broker]);

    const getAuthHeader = () => {
        const token = localStorage.getItem("access_token") || localStorage.getItem("sc_token");
        return token ? { Authorization: `Bearer ${token}` } : {};
    };

    const fetchCredentials = async (b: string) => {
        setLoading(true);
        setMessage(null);
        setCredentials({});
        try {
            const res = await fetch(`${API}/api/settings/broker/${b}`, { headers: getAuthHeader() });
            if (res.ok) {
                const data = await res.json();
                if (data.credentials) setCredentials(data.credentials);
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
            const res = await fetch(`${API}/api/settings/broker`, {
                method: "POST",
                headers: { "Content-Type": "application/json", ...getAuthHeader() },
                body: JSON.stringify({ broker, credentials }),
            });
            if (res.ok) {
                setMessage({ text: `Credentials for ${broker} updated successfully!`, type: "success" });
                fetchCredentials(broker);
            } else {
                const err = await res.json();
                setMessage({ text: err.detail || "Failed to save credentials", type: "error" });
            }
        } catch {
            setMessage({ text: "Network error saving credentials.", type: "error" });
        } finally {
            setLoading(false);
        }
    };

    return (
        <>
            <h2 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 800, color: T.navy }}>{broker} Configuration</h2>
            <p style={{ margin: '0 0 24px', fontSize: 13, color: T.textMuted, lineHeight: 1.5 }}>
                Configure API keys for algorithmic trading through {broker}. Credentials are encrypted per-user.
            </p>
            {message && (
                <div style={{
                    padding: '12px 16px', borderRadius: 8, marginBottom: 24, fontSize: 13, fontWeight: 600,
                    display: 'flex', alignItems: 'center', gap: 8,
                    border: `1px solid ${message.type === 'success' ? T.greenMid : T.redMid}`,
                    background: message.type === 'success' ? T.greenLight : T.redLight,
                    color: message.type === 'success' ? T.green : T.red,
                }}>
                    {message.type === 'success' ? '✓' : '⚠'} {message.text}
                </div>
            )}
            <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 480 }}>
                {BROKER_FIELDS[broker]?.map((field) => (
                    <div key={field.key}>
                        <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: T.textMid, marginBottom: 6 }}>
                            {field.label}
                        </label>
                        <input
                            type={field.type}
                            value={credentials[field.key] || ""}
                            onChange={(e) => setCredentials(prev => ({ ...prev, [field.key]: e.target.value }))}
                            placeholder={`Enter ${field.label}`}
                            style={{
                                width: '100%', padding: '10px 14px', border: `1px solid ${T.borderStrong}`,
                                borderRadius: 8, fontSize: 14, outline: 'none',
                                background: T.surface, color: T.text,
                                fontFamily: field.type === 'password' ? 'inherit' : "'DM Mono', monospace",
                            }}
                            onFocus={e => e.target.style.borderColor = T.blue}
                            onBlur={e => e.target.style.borderColor = T.borderStrong}
                        />
                    </div>
                ))}
                <div style={{ marginTop: 16, paddingTop: 20, borderTop: `1px solid ${T.border}` }}>
                    <button type="submit" disabled={loading} style={{
                        padding: '10px 20px', background: T.blue, color: '#fff', border: 'none',
                        borderRadius: 8, fontSize: 14, fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
                        opacity: loading ? 0.7 : 1,
                    }}>
                        {loading ? "Saving..." : "Save Configuration"}
                    </button>
                </div>
            </form>
        </>
    );
}

// ── Telegram Config Panel ──────────────────────────────────────────────────────
function TelegramPanel() {
    const [botToken, setBotToken] = useState('');
    const [chatId, setChatId] = useState('');
    const [configured, setConfigured] = useState(false);
    const [source, setSource] = useState('none');
    const [loading, setLoading] = useState(false);
    const [testing, setTesting] = useState(false);
    const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

    const getAuthHeader = () => {
        const token = localStorage.getItem("access_token") || localStorage.getItem("sc_token");
        return token ? { Authorization: `Bearer ${token}` } : {};
    };

    useEffect(() => {
        fetchConfig();
    }, []);

    const fetchConfig = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API}/api/settings/telegram`, { headers: getAuthHeader() });
            if (res.ok) {
                const data = await res.json();
                setBotToken(data.bot_token || '');
                setChatId(data.chat_id || '');
                setConfigured(data.configured);
                setSource(data.source);
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
            const res = await fetch(`${API}/api/settings/telegram`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
                body: JSON.stringify({ bot_token: botToken, chat_id: chatId }),
            });
            const data = await res.json();
            if (res.ok) {
                setMessage({ text: 'Telegram configuration saved!', type: 'success' });
                fetchConfig();
            } else {
                setMessage({ text: data.detail || 'Failed to save', type: 'error' });
            }
        } catch {
            setMessage({ text: 'Network error.', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    const handleTest = async () => {
        setTesting(true);
        setMessage(null);
        try {
            const res = await fetch(`${API}/api/settings/telegram/test`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
            });
            const data = await res.json();
            if (res.ok) {
                setMessage({ text: '✅ ' + data.message, type: 'success' });
            } else {
                setMessage({ text: '❌ ' + (data.detail || 'Test failed'), type: 'error' });
            }
        } catch {
            setMessage({ text: '❌ Network error during test.', type: 'error' });
        } finally {
            setTesting(false);
        }
    };

    return (
        <>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: T.navy }}>Telegram Notifications</h2>
                <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 12px',
                    borderRadius: 20, fontSize: 12, fontWeight: 700,
                    background: configured ? T.greenLight : T.redLight,
                    color: configured ? T.green : T.red,
                    border: `1px solid ${configured ? T.greenMid : T.redMid}`,
                }}>
                    <span style={{ width: 7, height: 7, borderRadius: '50%', background: configured ? T.green : T.red, display: 'inline-block' }} />
                    {configured ? 'Connected' : 'Not Configured'}
                </span>
            </div>
            <p style={{ margin: '0 0 6px', fontSize: 13, color: T.textMuted, lineHeight: 1.6 }}>
                Receive real-time alerts on trade entries, exits, stop-losses, and risk limit hits.
            </p>
            {source === 'env' && (
                <div style={{
                    padding: '10px 14px', background: T.amberLight, borderRadius: 8,
                    border: `1px solid #FDE68A`, color: T.amber, fontSize: 12, fontWeight: 600, marginBottom: 20,
                }}>
                    🔑 Bot token loaded from <code style={{ fontFamily: 'monospace' }}>.env</code> file. 
                    Enter your Chat ID below to complete setup.
                </div>
            )}

            {message && (
                <div style={{
                    padding: '12px 16px', borderRadius: 8, marginBottom: 20, fontSize: 13, fontWeight: 600,
                    display: 'flex', alignItems: 'center', gap: 8,
                    border: `1px solid ${message.type === 'success' ? T.greenMid : T.redMid}`,
                    background: message.type === 'success' ? T.greenLight : T.redLight,
                    color: message.type === 'success' ? T.green : T.red,
                }}>
                    {message.text}
                </div>
            )}

            <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 480 }}>
                <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: T.textMid, marginBottom: 6 }}>
                        Bot Token
                    </label>
                    <input
                        type="password"
                        value={botToken}
                        onChange={e => setBotToken(e.target.value)}
                        placeholder="e.g. 8586995056:AAH..."
                        style={{
                            width: '100%', padding: '10px 14px', border: `1px solid ${T.borderStrong}`,
                            borderRadius: 8, fontSize: 14, outline: 'none',
                            background: T.surface, color: T.text,
                        }}
                        onFocus={e => e.target.style.borderColor = T.blue}
                        onBlur={e => e.target.style.borderColor = T.borderStrong}
                    />
                    <p style={{ margin: '4px 0 0', fontSize: 11, color: T.textMuted }}>
                        Create a bot via <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" style={{ color: T.blue }}>@BotFather</a> on Telegram.
                    </p>
                </div>

                <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: T.textMid, marginBottom: 6 }}>
                        Chat ID
                    </label>
                    <input
                        type="text"
                        value={chatId}
                        onChange={e => setChatId(e.target.value)}
                        placeholder="e.g. 123456789"
                        style={{
                            width: '100%', padding: '10px 14px', border: `1px solid ${T.borderStrong}`,
                            borderRadius: 8, fontSize: 14, outline: 'none',
                            background: T.surface, color: T.text, fontFamily: "'DM Mono', monospace",
                        }}
                        onFocus={e => e.target.style.borderColor = T.blue}
                        onBlur={e => e.target.style.borderColor = T.borderStrong}
                    />
                    <p style={{ margin: '4px 0 0', fontSize: 11, color: T.textMuted }}>
                        Message your bot, then visit{' '}
                        <code style={{ fontSize: 10, background: T.bg, padding: '1px 4px', borderRadius: 3 }}>
                            api.telegram.org/bot{'<TOKEN>'}/getUpdates
                        </code>{' '}
                        and find <strong>chat.id</strong>.
                    </p>
                </div>

                {/* What you'll receive */}
                <div style={{ background: T.bg, borderRadius: 10, border: `1px solid ${T.border}`, padding: '14px 16px' }}>
                    <p style={{ margin: '0 0 8px', fontSize: 12, fontWeight: 700, color: T.navy }}>You'll receive alerts for:</p>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, fontSize: 12, color: T.textMid }}>
                        {['🟢 Trade entry orders', '🔴 Trade exits & P&L', '🛑 Stop-loss triggers', '⚠️ Daily risk limit hits', '❌ Order placement failures', '🚨 Urgent: position errors'].map(item => (
                            <span key={item}>{item}</span>
                        ))}
                    </div>
                </div>

                <div style={{ display: 'flex', gap: 10, paddingTop: 4 }}>
                    <button type="submit" disabled={loading} style={{
                        flex: 1, padding: '10px 20px', background: T.blue, color: '#fff', border: 'none',
                        borderRadius: 8, fontSize: 14, fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
                        opacity: loading ? 0.7 : 1,
                    }}>
                        {loading ? 'Saving...' : 'Save Configuration'}
                    </button>
                    <button
                        type="button"
                        onClick={handleTest}
                        disabled={testing}
                        style={{
                            padding: '10px 18px', background: configured ? T.greenLight : T.bg,
                            color: configured ? T.green : T.textMuted,
                            border: `1px solid ${configured ? T.greenMid : T.border}`,
                            borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: testing ? 'wait' : 'pointer',
                            whiteSpace: 'nowrap',
                        }}
                    >
                        {testing ? '⏳ Sending...' : '📨 Send Test'}
                    </button>
                </div>
            </form>
        </>
    );
}

// ── Main Settings Page ─────────────────────────────────────────────────────────
export default function SettingsPage() {
    const [selected, setSelected] = useState<string>(BROKERS[0]);

    type NavItem = { id: string; label: string; icon: string; section: 'broker' | 'telegram' };
    const NAV: NavItem[] = [
        ...BROKERS.map(b => ({ id: b, label: b, icon: '🔗', section: 'broker' as const })),
        { id: 'telegram', label: 'Telegram', icon: '✈️', section: 'telegram' as const },
    ];

    const active = NAV.find(n => n.id === selected)!;

    return (
        <div style={{ padding: 24, fontFamily: "'DM Sans', sans-serif", background: T.bg, minHeight: "100vh" }}>
            <div style={{ marginBottom: 20 }}>
                <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800, color: T.navy, letterSpacing: '-0.5px' }}>
                    Settings
                </h1>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: T.textMuted }}>
                    Manage broker connections, API credentials, and notification preferences
                </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: 24 }}>
                {/* Sidebar */}
                <div style={{
                    background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`,
                    boxShadow: '0 1px 3px rgba(0,0,0,0.04)', overflow: 'hidden', alignSelf: 'start',
                }}>
                    <div style={{ padding: '16px 20px', borderBottom: `1px solid ${T.border}`, fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: '0.6px', textTransform: 'uppercase' }}>
                        Brokers
                    </div>
                    <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 2 }}>
                        {BROKERS.map(broker => (
                            <button key={broker} onClick={() => setSelected(broker)} style={{
                                width: '100%', padding: '10px 14px', border: 'none', borderRadius: 8,
                                background: selected === broker ? T.blueLight : 'transparent',
                                color: selected === broker ? T.blue : T.textMid,
                                fontSize: 14, fontWeight: selected === broker ? 700 : 500,
                                cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s',
                            }}>
                                🔗 {broker}
                            </button>
                        ))}
                    </div>

                    {/* Notifications section */}
                    <div style={{ padding: '16px 20px 8px', borderTop: `1px solid ${T.border}`, fontSize: 11, fontWeight: 700, color: T.textMuted, letterSpacing: '0.6px', textTransform: 'uppercase' }}>
                        Notifications
                    </div>
                    <div style={{ padding: '0 8px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <button onClick={() => setSelected('telegram')} style={{
                            width: '100%', padding: '10px 14px', border: 'none', borderRadius: 8,
                            background: selected === 'telegram' ? T.blueLight : 'transparent',
                            color: selected === 'telegram' ? T.blue : T.textMid,
                            fontSize: 14, fontWeight: selected === 'telegram' ? 700 : 500,
                            cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s',
                        }}>
                            ✈️ Telegram
                        </button>
                    </div>
                </div>

                {/* Main Content */}
                <div style={{
                    background: T.surface, borderRadius: 12, border: `1px solid ${T.border}`,
                    boxShadow: '0 1px 3px rgba(0,0,0,0.04)', padding: 28,
                }}>
                    {selected === 'telegram' ? (
                        <TelegramPanel />
                    ) : (
                        <BrokerPanel broker={selected} />
                    )}
                </div>
            </div>
        </div>
    );
}
