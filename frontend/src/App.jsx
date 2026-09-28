import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import { api } from "./api";

const nextMorning = () => {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(7, 0, 0, 0);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};

const nextQuarter = () => {
  const date = new Date(Math.ceil(Date.now() / (15 * 60 * 1000)) * 15 * 60 * 1000);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

const navigation = [
  ["overview", "Overview"],
  ["plan", "Plan charging"],
  ["v2g", "V2G offers"],
  ["ai", "Smart assistant"],
  ["vehicles", "My vehicles"],
  ["rewards", "Rewards"],
  ["operator", "Operator dashboard"],
  ["settings", "Settings"],
];

function BrandMark() {
  return <span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path className="brand-car" d="M4 14.5v-2.2c0-.9.6-1.7 1.5-1.9l1.2-.3 1.5-3h7.6l1.6 3 1.1.3c.9.2 1.5 1 1.5 1.9v2.2" /><path className="brand-car" d="M5 14.5h14M7.5 10h9" /><circle className="brand-wheel" cx="7" cy="15.5" r="1.5" /><circle className="brand-wheel" cx="17" cy="15.5" r="1.5" /><path className="brand-bolt" d="m12.8 7.8-2.5 4h2.1l-1.2 3.4 3-4.5h-2.1l.7-2.9Z" /></svg></span>;
}

function SidebarIcon({ name }) {
  const paths = {
    overview: <><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /></>,
    plan: <path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z" />,
    v2g: <><path d="M7 7h10v10H7z" /><path d="m10 13 4-4M11 9h3v3M4 12H2m20 0h-2M12 4V2m0 20v-2" /></>,
    ai: <><path d="M9.5 4.5A3.5 3.5 0 0 0 6 8v.4A3.5 3.5 0 0 0 5.5 15 3.5 3.5 0 0 0 9 19.5" /><path d="M14.5 4.5A3.5 3.5 0 0 1 18 8v.4a3.5 3.5 0 0 1 .5 6.6 3.5 3.5 0 0 1-3.5 4.5" /><path d="M9.5 4.5V20M14.5 4.5V20M9.5 9H7M14.5 9H17M9.5 15H7.5M14.5 15H17" /></>,
    vehicles: <><path d="M5 16h14l-1.3-5.2A2.4 2.4 0 0 0 15.4 9H8.6a2.4 2.4 0 0 0-2.3 1.8L5 16Z" /><path d="M3 16v3h2m16-3v3h-2M7 19h10M8 13h.01M16 13h.01" /></>,
    rewards: <><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.5" /><path d="m10.5 12 1 1 2.5-2.5" /></>,
    operator: <><path d="M3 20h18M5 20V8l7-4 7 4v12M9 20v-6h6v6" /><path d="M8 10h.01M12 10h.01M16 10h.01" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M12 2.8v2M12 19.2v2M2.8 12h2M19.2 12h2M5.5 5.5l1.4 1.4M17.1 17.1l1.4 1.4M18.5 5.5l-1.4 1.4M6.9 17.1l-1.4 1.4" /></>,
  };
  return <svg className="sidebar-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

const modeCopy = {
  normal: ["Normal", "Charge immediately"],
  v1g: ["Smart V1G", "Shift demand intelligently"],
  v2g: ["V2G", "Charge and support the grid"],
};

function AuthScreen({ onAuthenticated }) {
  const params = new URLSearchParams(window.location.search);
  const [mode, setMode] = useState(params.get("reset_token") ? "reset" : "login");
  const [tokenValue, setTokenValue] = useState(params.get("reset_token") || "");
  const [form, setForm] = useState({ name: "", email: "", password: "", confirmPassword: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const verificationToken = params.get("verify_token");
    if (!verificationToken) return;
    api.post("/auth/verify-email", { token: verificationToken })
      .then((result) => { setMessage(result.message); window.history.replaceState({}, "", window.location.pathname); })
      .catch((requestError) => setError(requestError.message));
  }, []);

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "forgot") {
        const response = await api.post("/auth/forgot-password", { email: form.email });
        setMessage(response.message);
        if (response.development_token) { setTokenValue(response.development_token); setMode("reset"); }
      } else if (mode === "reset") {
        const response = await api.post("/auth/reset-password", { token: tokenValue, new_password: form.password, confirm_password: form.confirmPassword });
        setMessage(response.message); setMode("login");
        setForm({ ...form, password: "", confirmPassword: "" });
        window.history.replaceState({}, "", window.location.pathname);
      } else {
        const payload = mode === "register" ? { name: form.name, email: form.email, password: form.password } : { email: form.email, password: form.password };
        const response = await api.post(`/auth/${mode}`, payload);
        if (mode === "register") {
          setTokenValue(response.development_token || "");
          setMessage(response.development_token ? "Account created. Verify locally, then sign in." : response.message);
          setMode("verify");
        } else onAuthenticated(response);
      }
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-story">
        <a className="brand brand--light" href="#top"><BrandMark /><span>Smart EV</span></a>
        <div>
          <p className="kicker">SMART CHARGING. REAL VALUE.</p>
          <h1>Your EV can do more than <em>charge.</em></h1>
          <p>Plan around grid demand, use cleaner energy, and earn rewards when your battery supports the network.</p>
        </div>
        <div className="auth-benefits">
          <span>01 <b>Lower charging cost</b></span>
          <span>02 <b>V2G wallet rewards</b></span>
          <span>03 <b>Your vehicles, one account</b></span>
        </div>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <p className="eyebrow">WELCOME TO SMART EV</p>
          <h2>{mode === "login" ? "Sign in to your account" : mode === "register" ? "Create your account" : mode === "forgot" ? "Reset your password" : mode === "verify" ? "Verify your email" : "Choose a new password"}</h2>
          <p className="muted">Your vehicles, plans and rewards stay connected to you.</p>

          {!['forgot', 'reset', 'verify'].includes(mode) && <div className="auth-tabs">
            <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Login</button>
            <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Register</button>
          </div>}

          {mode === "verify" ? <div className="auth-verify-panel"><p className="success-message">{message}</p>{tokenValue ? <button className="primary-button" onClick={async () => { setLoading(true); setError(""); try { await api.post("/auth/verify-email", { token: tokenValue }); onAuthenticated(await api.post("/auth/login", { email: form.email, password: form.password })); } catch (requestError) { setError(requestError.message); } finally { setLoading(false); } }}>Verify locally and continue<span>→</span></button> : <p className="muted">Open the link sent to {form.email}, then return to login.</p>}{error && <p className="error-message">{error}</p>}<button type="button" className="text-button auth-help" onClick={() => setMode("login")}>Back to login</button></div> : <form onSubmit={submit}>
            {mode === "register" && (
              <Field label="Full name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} required />
            )}
            {mode !== "reset" && <Field label="Email address" type="email" value={form.email} onChange={(value) => setForm({ ...form, email: value })} required />}
            {mode !== "forgot" && <Field label={mode === "reset" ? "New password" : "Password"} type="password" value={form.password} onChange={(value) => setForm({ ...form, password: value })} minLength="8" required />}
            {mode === "reset" && <Field label="Confirm new password" type="password" value={form.confirmPassword} onChange={(value) => setForm({ ...form, confirmPassword: value })} minLength="8" required />}
            {error && <p className="error-message">{error}</p>}
            {message && <p className="success-message">{message}</p>}
            <button className="primary-button" disabled={loading}>
              {loading ? "Please wait…" : mode === "login" ? "Login" : mode === "register" ? "Create account" : mode === "forgot" ? "Send reset link" : "Reset password"}<span>→</span>
            </button>
            {mode === "login" && <button type="button" className="text-button auth-help" onClick={() => { setMode("forgot"); setError(""); setMessage(""); }}>Forgot password?</button>}
            {['forgot', 'reset'].includes(mode) && <button type="button" className="text-button auth-help" onClick={() => { setMode("login"); setError(""); }}>Back to login</button>}
          </form>
          }
        </div>
      </section>
    </main>
  );
}

function VehicleForm({ catalog, onSubmit, busy, buttonLabel }) {
  const [form, setForm] = useState({ catalog_id: catalog[0]?.id ?? "", vehicle_age: 0 });

  useEffect(() => {
    if (!form.catalog_id && catalog[0]) {
      setForm((current) => ({ ...current, catalog_id: catalog[0].id }));
    }
  }, [catalog, form.catalog_id]);

  const selected = catalog.find((vehicle) => vehicle.id === Number(form.catalog_id));
  return (
    <form onSubmit={(event) => { event.preventDefault(); onSubmit({ catalog_id: Number(form.catalog_id), vehicle_age: Number(form.vehicle_age) }); }}>
      <Field label="Vehicle model">
        <select value={form.catalog_id} onChange={(event) => setForm({ ...form, catalog_id: event.target.value })} required>
          {catalog.length ? catalog.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.model}</option>) : <option value="">No model available</option>}
        </select>
      </Field>
      <Field label="Battery capacity"><input value={selected ? `${selected.battery_capacity} kWh` : "Select a model"} disabled /></Field>
      <Field label="Compatible connectors"><input value={selected?.connector_types || "Select a model"} disabled /></Field>
      <Field label="Vehicle age (years)" type="number" value={form.vehicle_age} onChange={(value) => setForm({ ...form, vehicle_age: value })} min="0" max="100" required />
      <button className="primary-button" disabled={busy || !form.catalog_id}>{busy ? "Saving…" : buttonLabel}<span>→</span></button>
    </form>
  );
}

function Onboarding({ user, token, catalog, onCompleted, logout }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (vehicle) => {
    setBusy(true); setError("");
    try {
      await api.post("/vehicles", vehicle, token);
      await onCompleted();
    } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };
  return (
    <main className="onboarding-page">
      <header className="onboarding-header"><span className="brand"><BrandMark /><span>Smart EV</span></span><button className="logout-button" onClick={logout}>Log out</button></header>
      <section className="onboarding-layout">
        <div className="onboarding-copy"><p className="kicker">WELCOME, {user.name?.toUpperCase()}</p><h1>First, connect your EV.</h1><p>Your model determines battery capacity and makes every charging plan accurate. Models are limited to the project dataset.</p><div className="onboarding-step"><b>1</b><span>Account created</span><b className="active">2</b><span>Add your vehicle</span></div></div>
        <article className="content-card onboarding-card"><div className="card-heading"><div><p className="eyebrow">REQUIRED SETUP</p><h3>Tell us about your car</h3></div><span className="step-pill">02</span></div>{error && <p className="error-message">{error}</p>}<VehicleForm catalog={catalog} onSubmit={submit} busy={busy} buttonLabel="Finish setup" /></article>
      </section>
    </main>
  );
}

function Field({ label, value, onChange, type = "text", children, ...props }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children ?? <input type={type} value={value} onChange={(event) => onChange(event.target.value)} {...props} />}
    </label>
  );
}

function Sidebar({ active, setActive, user, logout }) {
  const visibleNavigation = navigation.filter(([key]) => key !== "operator" || ["operator", "admin"].includes(user.role));
  return (
    <aside className="sidebar">
      <button className="brand brand-button" onClick={() => setActive("overview")}>
        <BrandMark /><span>Smart EV</span>
      </button>
      <nav>
        {visibleNavigation.map(([key, label]) => (
          <button key={key} className={active === key ? "active" : ""} onClick={() => setActive(key)}>
            <i><SidebarIcon name={key} /></i><span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-wallet">
        <span>Available rewards</span>
        <strong>€{user.wallet_balance.toFixed(2)}</strong>
        <small>{user.reward_points} points</small>
      </div>
      <button className="profile-mini" onClick={() => setActive("settings")}>
        <span>{user.name?.[0]?.toUpperCase() ?? "U"}</span>
        <div><b>{user.name}</b><small>{user.email}</small></div>
      </button>
      <button className="logout-button" onClick={logout}>Log out</button>
    </aside>
  );
}

function ModeCard({ result, recommended, selected, onSelect }) {
  const [name, subtitle] = modeCopy[result.mode];
  const displayedCost = result.mode === "v2g" ? result.net_cost_eur : result.cost_eur;
  const totalChargedEnergy = result.slots
    .filter((slot) => slot.action === "charge")
    .reduce((total, slot) => total + slot.energy_kwh, 0);
  const chargeMinutes = result.slots.filter((slot) => slot.action === "charge").length * 15;
  const exportMinutes = result.slots.filter((slot) => slot.action === "discharge").length * 15;
  const chooseLabel = result.mode === "v2g" ? "Accept V2G offer" : result.mode === "v1g" ? "Choose smart charging" : "Choose normal charging";
  return (
    <article className={`mode-card ${recommended ? "best" : ""} ${selected ? "selected" : ""}`} onClick={onSelect} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelect(); }} role="button" tabIndex="0">
      <div className="mode-card__top">
        <div><p className="eyebrow">{subtitle}</p><h3>{name}</h3></div>
        {recommended && <span className="best-pill">Recommended</span>}
      </div>
      {result.mode === "v2g" && <div className="v2g-offer-note"><b>Grid offer</b><span>Your car sends {result.v2g_energy_kwh.toFixed(2)} kWh to the grid and you earn €{result.v2g_reward_eur.toFixed(2)}</span></div>}
      <small className="price-caption">{result.mode === "v2g" ? "Effective cost after reward" : "Final amount to pay"}</small>
      <strong className="price">€{displayedCost.toFixed(2)}</strong>
      {result.mode === "v2g" ? <><Metric label="Grid → car (total charged)" value={`${totalChargedEnergy.toFixed(2)} kWh`} /><Metric label="Car → grid (you give)" value={`${result.v2g_energy_kwh.toFixed(2)} kWh`} /><Metric label="Battery keeps (net)" value={`${result.predicted_energy_kwh.toFixed(2)} kWh`} /></> : <Metric label="Energy added to battery" value={`${result.predicted_energy_kwh.toFixed(2)} kWh`} />}
      {result.mode !== "normal" && <Metric label="You save" value={`€${result.saving_eur.toFixed(2)}`} />}
      {result.mode === "v2g" && <Metric label="Reward credited" value={`€${result.v2g_reward_eur.toFixed(2)}`} />}
      {result.mode === "v2g" && <Metric label="Charging cost to pay" value={`€${result.cost_eur.toFixed(2)}`} />}
      <Metric label="Charge duration" value={formatDuration(chargeMinutes)} />
      <Metric label="Charge time" value={formatChargingSummary(result.slots)} />
      {result.mode === "v2g" && <Metric label="Grid export duration" value={formatDuration(exportMinutes)} />}
      {result.mode === "v2g" && <Metric label="Grid export time" value={formatChargingSummary(result.slots, "discharge")} />}
      <span className="choose-plan">{selected ? "✓ Selected" : chooseLabel}</span>
    </article>
  );
}

function Metric({ label, value }) {
  return <div className="metric-row"><span>{label}</span><b>{value}</b></div>;
}

function formatDuration(totalMinutes) {
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (!hours) return `${minutes} min`;
  return `${hours}h${minutes ? ` ${minutes} min` : ""}`;
}

const viennaDay = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Vienna", day: "2-digit", month: "short" });
const viennaTime = new Intl.DateTimeFormat("en-GB", { timeZone: "Europe/Vienna", hour: "2-digit", minute: "2-digit", hour12: false });

function formatChargingSummary(slots, action = "charge") {
  const chargingSlots = slots
    .filter((slot) => slot.action === action)
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  if (!chargingSlots.length) return "—";

  const windows = [];
  chargingSlots.forEach((slot) => {
    const start = new Date(slot.timestamp).getTime();
    const previous = windows[windows.length - 1];
    if (previous && previous.end === start) previous.end = start + 15 * 60 * 1000;
    else windows.push({ start, end: start + 15 * 60 * 1000 });
  });

  return windows.map((window, index) => {
    const date = viennaDay.format(new Date(window.start));
    const previousDate = index > 0 ? viennaDay.format(new Date(windows[index - 1].start)) : null;
    const time = `${viennaTime.format(new Date(window.start))}–${viennaTime.format(new Date(window.end))}`;
    return index === 0 || date !== previousDate ? `${date} · ${time}` : time;
  }).join(" + ");
}

function ScheduleWindows({ slots, smart }) {
  const windows = [];
  [...slots].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp)).forEach((slot) => {
    const start = new Date(slot.timestamp).getTime();
    const end = start + 15 * 60 * 1000;
    const previous = windows[windows.length - 1];
    if (previous && previous.action === slot.action && previous.end === start) previous.end = end;
    else windows.push({ action: slot.action, start, end });
  });

  const formatWindow = (window) => {
    const start = new Date(window.start);
    const end = new Date(window.end);
    const startDay = viennaDay.format(start);
    const endDay = viennaDay.format(end);
    return startDay === endDay
      ? `${startDay} · ${viennaTime.format(start)}–${viennaTime.format(end)}`
      : `${startDay} ${viennaTime.format(start)}–${endDay} ${viennaTime.format(end)}`;
  };

  return <div className="schedule-windows"><p>{smart ? "Recommended schedule" : "Charging schedule"}<small>Austria time</small></p>{windows.map((window, index) => <div key={`${window.action}-${window.start}-${index}`}><span className={window.action}>{window.action === "charge" ? "Charge" : "Grid export"}</span><b>{formatWindow(window)}</b></div>)}</div>;
}

function StationMap({ stations, selectedStationId, vehicle, onSelect, v2gOnly = false, hideIneligible = false }) {
  const elementRef = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const [tilesUnavailable, setTilesUnavailable] = useState(false);

  useEffect(() => {
    if (!elementRef.current || mapRef.current) return undefined;
    const map = L.map(elementRef.current, { scrollWheelZoom: false }).setView([47.6, 14.2], 7);
    const tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map);
    tiles.on("tileerror", () => setTilesUnavailable(true));
    tiles.on("load", () => setTilesUnavailable(false));
    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    const coordinates = [];
    stations.forEach((station) => {
      if (station.latitude == null || station.longitude == null) return;
      const connectorCompatible = connectorsAreCompatible(vehicle, station);
      const modeCompatible = !v2gOnly || station.supports_v2g;
      const available = connectorCompatible && modeCompatible && station.operational_status === "online" && station.available_chargers > 0;
      if (hideIneligible && !available) return;
      const selected = station.id === Number(selectedStationId);
      const showV2gMarker = v2gOnly && station.supports_v2g;
      const statusText = !connectorCompatible
        ? "Incompatible connector"
        : !modeCompatible
          ? "Charging only — no V2G export"
          : station.operational_status !== "online" || station.available_chargers < 1
            ? "Currently unavailable"
            : `${station.available_chargers}/${station.total_chargers} free`;
      const marker = L.marker([station.latitude, station.longitude], {
        icon: L.divIcon({
          className: "station-map-icon-wrap",
          html: `<span class="station-map-icon ${available ? "available" : "disabled"} ${selected ? "selected" : ""} ${showV2gMarker ? "v2g" : ""}">${showV2gMarker ? "↔" : "⚡"}</span>`,
          iconSize: [34, 34], iconAnchor: [17, 17],
        }),
      }).addTo(layer);
      marker.bindTooltip(`<b>${station.station_name || "Station"}</b><br>${station.city || ""} · ${statusText}${v2gOnly && station.supports_v2g ? " · V2G" : ""}`);
      if (available) marker.on("click", () => onSelect(station.id));
      coordinates.push([station.latitude, station.longitude]);
    });
    if (coordinates.length && !map._smartEvFitted) {
      map.fitBounds(coordinates, { padding: [30, 30], maxZoom: 8 });
      map._smartEvFitted = true;
    }
  }, [stations, selectedStationId, vehicle, onSelect, v2gOnly, hideIneligible]);

  return <article className="content-card station-map-card"><div className="card-heading"><div><p className="eyebrow">{v2gOnly ? "V2G STATION MAP" : "CHARGING STATION MAP"}</p><h3>{v2gOnly ? "Choose where to export energy" : "Choose where to charge"}</h3></div><span className="map-legend">{v2gOnly ? <><i className="v2g" /> V2G export available <i className="unavailable" /> Not eligible</> : <><i /> Compatible and available</>}</span></div><div className="station-map-wrap"><div className="station-map" ref={elementRef} />{tilesUnavailable && <div className="map-offline-note"><b>Map background unavailable</b><span>Station markers still show where you can charge.</span></div>}</div><p className="planning-window-note">{v2gOnly ? "Blue stations support bidirectional export and match your selected vehicle. Grey stations are charging-only, unavailable, or connector-incompatible." : "Only online stations with a free charger and a connector compatible with your selected vehicle are shown. Choose the station directly on the map."}</p></article>;
}

function NotificationCenter({ token, notifications, setNotifications }) {
  const [open, setOpen] = useState(false);
  const unread = notifications.filter((item) => !item.read_at).length;
  const readOne = async (item) => {
    if (!item.read_at) {
      const updated = await api.patch(`/notifications/${item.id}/read`, {}, token);
      setNotifications((current) => current.map((entry) => entry.id === item.id ? updated : entry));
    }
  };
  const readAll = async () => {
    await api.post("/notifications/read-all", {}, token);
    const now = new Date().toISOString();
    setNotifications((current) => current.map((item) => ({ ...item, read_at: item.read_at || now })));
  };
  return <div className="notification-center"><button className="notification-bell" onClick={() => setOpen(!open)} aria-label="Notifications">♢{unread > 0 && <b>{unread}</b>}</button>{open && <div className="notification-popover"><div className="notification-heading"><strong>Notifications</strong>{unread > 0 && <button onClick={readAll}>Mark all read</button>}</div>{notifications.length ? notifications.slice(0, 8).map((item) => <button key={item.id} className={`notification-item ${item.read_at ? "" : "unread"}`} onClick={() => readOne(item)}><span>{item.title}</span><small>{item.message}</small></button>) : <p className="empty-copy">No notifications yet.</p>}</div>}</div>;
}

function VerificationBanner({ user, verificationToken, setVerificationToken, refreshProfile }) {
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  if (user.email_verified) return null;
  const verify = async () => {
    if (!verificationToken) return;
    setBusy(true);
    try { const result = await api.post("/auth/verify-email", { token: verificationToken }); setMessage(result.message); await refreshProfile(); }
    catch (error) { setMessage(error.message); } finally { setBusy(false); }
  };
  const resend = async () => {
    setBusy(true);
    try { const result = await api.post("/auth/resend-verification", { email: user.email }); setVerificationToken(result.development_token || ""); setMessage(result.development_token ? "Development verification link generated. Click Verify now." : result.message); }
    catch (error) { setMessage(error.message); } finally { setBusy(false); }
  };
  return <div className="verification-banner"><div><b>Verify your email address</b><span>{message || `A verification link was issued for ${user.email}.`}</span></div><div>{verificationToken && <button onClick={verify} disabled={busy}>Verify now</button>}<button onClick={resend} disabled={busy}>Resend link</button></div></div>;
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("smartEvToken"));
  const [user, setUser] = useState(null);
  const [vehicles, setVehicles] = useState([]);
  const [stations, setStations] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [paymentMethod, setPaymentMethod] = useState(null);
  const [requests, setRequests] = useState([]);
  const [rewards, setRewards] = useState([]);
  const [reservations, setReservations] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [payments, setPayments] = useState([]);
  const [stripeMessage, setStripeMessage] = useState("");
  const [verificationToken, setVerificationToken] = useState("");
  const [active, setActive] = useState("overview");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(Boolean(token));
  const [error, setError] = useState("");

  const loadData = async (activeToken) => {
    const [profile, ownedVehicles, availableStations, vehicleCatalog, rewardHistory, requestHistory, savedPaymentMethod, reservationHistory, notificationHistory, paymentHistory] = await Promise.all([
      api.get("/me", activeToken),
      api.get("/vehicles", activeToken),
      api.get("/stations", activeToken),
      api.get("/catalog/vehicles", activeToken),
      api.get("/me/rewards", activeToken),
      api.get("/charging-requests", activeToken),
      api.get("/me/payment-method", activeToken),
      api.get("/reservations", activeToken),
      api.get("/notifications", activeToken),
      api.get("/payments", activeToken),
    ]);
    setUser(profile);
    setVehicles(ownedVehicles);
    setStations(availableStations);
    setCatalog(vehicleCatalog);
    setRewards(rewardHistory);
    setRequests(requestHistory);
    setPaymentMethod(savedPaymentMethod);
    setReservations(reservationHistory);
    setNotifications(notificationHistory);
    setPayments(paymentHistory);
  };

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    loadData(token).catch(() => logout()).finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const query = new URLSearchParams(window.location.search);
    const sessionId = query.get("stripe_session_id");
    const emailToken = query.get("verify_token");
    if (sessionId) {
      api.post(`/payments/stripe/confirm/${encodeURIComponent(sessionId)}`, {}, token)
        .then((receipt) => { setStripeMessage(`Stripe test payment ${receipt.reference} confirmed. Your invoice is ready.`); setActive("rewards"); return loadData(token); })
        .catch((requestError) => setError(requestError.message))
        .finally(() => window.history.replaceState({}, "", window.location.pathname));
    } else if (emailToken) {
      api.post("/auth/verify-email", { token: emailToken })
        .then((result) => { setStripeMessage(result.message); return loadData(token); })
        .catch((requestError) => setError(requestError.message))
        .finally(() => window.history.replaceState({}, "", window.location.pathname));
    }
  }, [token]);

  useEffect(() => {
    if (!token) return undefined;
    const interval = window.setInterval(() => {
      Promise.all([api.get("/stations", token), api.get("/notifications", token)])
        .then(([stationData, notificationData]) => { setStations(stationData); setNotifications(notificationData); })
        .catch(() => {});
    }, 5000);
    return () => window.clearInterval(interval);
  }, [token]);

  useEffect(() => {
    if (!user) return undefined;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = () => {
      const theme = user.theme === "system" ? (media.matches ? "dark" : "light") : user.theme;
      document.documentElement.dataset.theme = theme;
    };
    applyTheme();
    media.addEventListener("change", applyTheme);
    return () => media.removeEventListener("change", applyTheme);
  }, [user?.theme]);

  const authenticated = (response) => {
    localStorage.setItem("smartEvToken", response.access_token);
    setUser(response.user);
    setVerificationToken(response.verification_token || "");
    setToken(response.access_token);
  };

  const logout = () => {
    localStorage.removeItem("smartEvToken");
    setToken(null);
    setUser(null);
    setResults([]);
    document.documentElement.dataset.theme = "light";
  };

  if (!token) return <AuthScreen onAuthenticated={authenticated} />;
  if (loading || !user) return <div className="app-loader"><BrandMark /><p>Loading Smart EV…</p></div>;

  if (!user.onboarding_completed) {
    return <Onboarding user={user} token={token} catalog={catalog} onCompleted={() => loadData(token)} logout={logout} />;
  }

  const refreshProfile = async () => {
    const [profile, rewardHistory, requestHistory, reservationHistory, notificationHistory, paymentHistory] = await Promise.all([
      api.get("/me", token),
      api.get("/me/rewards", token),
      api.get("/charging-requests", token),
      api.get("/reservations", token),
      api.get("/notifications", token),
      api.get("/payments", token),
    ]);
    setUser(profile);
    setRewards(rewardHistory);
    setRequests(requestHistory);
    setReservations(reservationHistory);
    setNotifications(notificationHistory);
    setPayments(paymentHistory);
  };

  return (
    <div className="app-shell">
      <Sidebar active={active} setActive={setActive} user={user} logout={logout} />
      <main className="app-main">
        <header className="app-header">
          <div><p className="kicker">SMART EV CONTROL CENTER</p><h1>{navigation.find(([key]) => key === active)?.[1]}</h1></div>
          <div className="header-actions"><div className="live-status"><i /> Grid connected</div><NotificationCenter token={token} notifications={notifications} setNotifications={setNotifications} /></div>
        </header>

        <VerificationBanner user={user} verificationToken={verificationToken} setVerificationToken={setVerificationToken} refreshProfile={refreshProfile} />

        {error && <p className="error-message global-error">{error}</p>}
        {stripeMessage && <p className="success-message global-success">{stripeMessage}</p>}
        {active === "overview" && <Overview user={user} vehicles={vehicles} stations={stations} requests={requests} rewards={rewards} reservations={reservations} setActive={setActive} />}
        {active === "plan" && <PlanView token={token} vehicles={vehicles} stations={stations} paymentMethod={paymentMethod} rewardPoints={user.reward_points} results={results} setResults={setResults} setError={setError} refreshProfile={refreshProfile} />}
        {active === "v2g" && <V2GOffersView token={token} vehicles={vehicles} stations={stations} setError={setError} refreshProfile={refreshProfile} />}
        {active === "ai" && <AIView token={token} stations={stations} />}
        {active === "vehicles" && <VehiclesView token={token} catalog={catalog} vehicles={vehicles} setVehicles={setVehicles} setResults={setResults} setError={setError} />}
        {active === "rewards" && <RewardsView token={token} user={user} rewards={rewards} payments={payments} />}
        {active === "operator" && ["operator", "admin"].includes(user.role) && <OperatorDashboard token={token} stations={stations} setError={setError} />}
        {active === "settings" && <SettingsView token={token} user={user} setUser={setUser} paymentMethod={paymentMethod} setPaymentMethod={setPaymentMethod} setError={setError} />}
      </main>
    </div>
  );
}

function Overview({ user, vehicles, stations, requests, rewards, reservations, setActive }) {
  return (
    <section className="view-stack">
      <article className="welcome-card">
        <div><p className="eyebrow">GOOD ENERGY STARTS HERE</p><h2>Welcome back, {user.name?.split(" ")[0]}.</h2><p>Your account is ready to plan a cleaner, lower-cost charging session.</p></div>
        <button className="light-button" onClick={() => setActive("plan")}>Plan a charge <span>→</span></button>
      </article>
      <div className="stat-grid">
        <StatCard label="Reward wallet" value={`€${user.wallet_balance.toFixed(2)}`} detail="Earned through V2G" accent />
        <StatCard label="Smart points" value={user.reward_points} detail="V1G savings + V2G demo export" />
        <StatCard label="My vehicles" value={vehicles.length} detail="Connected to this account" />
        <StatCard label="Charging plans" value={requests.length} detail="Saved sessions" />
      </div>
      <article className="content-card"><div className="card-heading"><div><p className="eyebrow">RESERVATIONS</p><h3>Your charging slots</h3></div><button className="text-button" onClick={() => setActive("plan")}>Reserve another →</button></div>{reservations.length ? reservations.slice(0, 4).map((reservation) => { const station = stations.find((item) => item.id === reservation.station_id); return <div className="list-row" key={reservation.id}><span className="list-icon">P</span><div><b>{station?.station_name || `Station #${reservation.station_id}`}</b><small>{station?.city ? `${station.city} · ` : ""}{new Date(reservation.start_time).toLocaleString()} → {new Date(reservation.end_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</small></div><em className={`status-${reservation.status}`}>{reservation.status}</em></div>; }) : <EmptyCopy text="A confirmed reservation will appear automatically after payment." />}</article>
      <div className="split-grid">
        <article className="content-card">
          <div className="card-heading"><div><p className="eyebrow">GARAGE</p><h3>Your vehicles</h3></div><button className="text-button" onClick={() => setActive("vehicles")}>Manage →</button></div>
          {vehicles.length ? vehicles.slice(0, 3).map((vehicle) => <VehicleRow key={vehicle.id} vehicle={vehicle} />) : <EmptyCopy text="Add your first EV to start planning." />}
        </article>
        <article className="content-card">
          <div className="card-heading"><div><p className="eyebrow">RECENT VALUE</p><h3>V2G rewards</h3></div><button className="text-button" onClick={() => setActive("rewards")}>View all →</button></div>
          {rewards.length ? rewards.slice(0, 3).map((reward) => <RewardRow key={reward.id} reward={reward} />) : <EmptyCopy text="Your first Smart V1G or V2G reward will appear here." />}
        </article>
      </div>
    </section>
  );
}

function StatCard({ label, value, detail, accent = false }) {
  return <article className={`stat-card ${accent ? "accent" : ""}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

function VehicleRow({ vehicle, onRemove, removing = false }) {
  return <div className="list-row"><span className="list-icon">EV</span><div><b>{vehicle.model}</b><small>{vehicle.battery_capacity} kWh battery · {vehicle.connector_types || "Connector unknown"}</small></div><em>{vehicle.vehicle_age} yr</em>{onRemove && <button type="button" className="remove-vehicle-button" onClick={() => onRemove(vehicle)} disabled={removing}>{removing ? "Removing…" : "Remove"}</button>}</div>;
}

function RewardRow({ reward }) {
  const isV1G = reward.reward_type === "v1g_saving";
  return <div className="list-row"><span className="list-icon reward">↗</span><div><b>{isV1G ? "Smart V1G saving" : "Demo grid support"}</b><small>{isV1G ? `€${reward.saving_eur.toFixed(2)} saved` : `${reward.energy_returned?.toFixed(2)} kWh simulated export`}</small></div><em>+{reward.points} pts{!isV1G && reward.reward > 0 ? ` · +€${reward.reward.toFixed(2)}` : ""}</em></div>;
}

function EmptyCopy({ text }) { return <p className="empty-copy">{text}</p>; }

function PaymentPanel({ plan, token, payment, onPaid, savedPaymentMethod, availablePoints }) {
  const [form, setForm] = useState({ cardholder: "", cardNumber: "", expiry: "", cvc: "" });
  const [useSaved, setUseSaved] = useState(Boolean(savedPaymentMethod));
  const [redeemPoints, setRedeemPoints] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [stripeConfigured, setStripeConfigured] = useState(false);
  const [name] = modeCopy[plan.mode];
  const redeemablePoints = Math.min(Math.floor(availablePoints / 100), Math.floor(Math.max(plan.cost_eur, 0))) * 100;
  const estimatedDiscount = redeemPoints ? redeemablePoints / 100 : 0;
  const estimatedTotal = Math.max(0, plan.cost_eur - estimatedDiscount);
  const chargeTime = formatChargingSummary(plan.slots);
  const exportTime = plan.mode === "v2g" ? formatChargingSummary(plan.slots, "discharge") : null;
  const totalChargedEnergy = plan.slots
    .filter((slot) => slot.action === "charge")
    .reduce((total, slot) => total + slot.energy_kwh, 0);

  useEffect(() => { api.get("/payments/stripe/status", token).then((result) => setStripeConfigured(result.configured)).catch(() => {}); }, [token]);

  const payWithStripe = async () => {
    setBusy(true); setError("");
    try {
      const session = await api.post("/payments/stripe/checkout-session", { schedule_id: plan.schedule_id, redeem_points: redeemPoints }, token);
      window.location.assign(session.checkout_url);
    } catch (requestError) { setError(requestError.message); setBusy(false); }
  };

  const pay = async (event) => {
    event.preventDefault(); setError("");
    if (useSaved && savedPaymentMethod) {
      setBusy(true);
      try {
        const receipt = await api.post("/payments/checkout", { schedule_id: plan.schedule_id, payment_method: "saved_card", payment_method_id: savedPaymentMethod.id, redeem_points: redeemPoints }, token);
        onPaid(receipt);
      } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
      return;
    }
    const digits = form.cardNumber.replace(/\D/g, "");
    if (digits.length !== 16 || !/^\d{2}\/\d{2}$/.test(form.expiry) || !/^\d{3,4}$/.test(form.cvc)) {
      setError("Use demo card format: 16 digits, MM/YY and a 3–4 digit CVC.");
      return;
    }
    setBusy(true);
    try {
      const receipt = await api.post("/payments/checkout", { schedule_id: plan.schedule_id, payment_method: "test_card", card_last4: digits.slice(-4), redeem_points: redeemPoints }, token);
      setForm({ cardholder: "", cardNumber: "", expiry: "", cvc: "" });
      onPaid(receipt);
    } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };

  if (payment) return <article className="payment-success"><span>✓</span><div><p className="eyebrow">PAYMENT & RESERVATION CONFIRMED</p><h3>{name} charging slot reserved</h3><p>€{payment.amount.toFixed(2)} simulated for card ending {payment.card_last4}.</p>{payment.points_redeemed > 0 && <p className="points-used">{payment.points_redeemed} points used · €{payment.points_discount_eur.toFixed(2)} discount from €{payment.original_amount.toFixed(2)}</p>}<small>Your selected station and exact charging time are reserved. Reference: {payment.reference}</small></div></article>;

  return <article className="payment-card"><div className="payment-summary"><div><p className="eyebrow">CONFIRM SELECTED PLAN</p><h3>{name}</h3><p>Your final charging time is shown below before payment.</p><div className="plan-confirmation-details"><span><b>Charge</b>{chargeTime}</span>{plan.mode === "v2g" ? <><span><b>Grid → car</b>{totalChargedEnergy.toFixed(2)} kWh</span><span><b>Car → grid</b>{plan.v2g_energy_kwh.toFixed(2)} kWh · {exportTime}</span><span><b>Battery keeps</b>{plan.predicted_energy_kwh.toFixed(2)} kWh net</span><span><b>You earn</b>€{plan.v2g_reward_eur.toFixed(2)} credited to wallet</span></> : <span><b>Battery energy</b>{plan.predicted_energy_kwh.toFixed(2)} kWh</span>}</div></div><div><small>FINAL AMOUNT TO PAY</small>{estimatedDiscount > 0 && <small className="original-price">€{plan.cost_eur.toFixed(2)}</small>}<strong>€{estimatedTotal.toFixed(2)}</strong></div></div><form onSubmit={pay}>{redeemablePoints >= 100 && <label className="points-redemption"><input type="checkbox" checked={redeemPoints} onChange={(event) => setRedeemPoints(event.target.checked)} /><span><b>Use {redeemablePoints} points</b><small>Save €{(redeemablePoints / 100).toFixed(2)} · 100 points = €1</small></span></label>}{stripeConfigured && <div className="stripe-checkout"><b>Stripe test mode</b><p>Use Stripe's secure checkout. Try card 4242 4242 4242 4242 with a future date and any CVC.</p><button type="button" className="stripe-button" onClick={payWithStripe} disabled={busy}>Pay €{estimatedTotal.toFixed(2)} with Stripe test</button><span>or use the local academic payment below</span></div>}{savedPaymentMethod && <button type="button" className={`saved-card-choice ${useSaved ? "active" : ""}`} onClick={() => setUseSaved(true)}><span>{savedPaymentMethod.brand}</span><b>•••• {savedPaymentMethod.last4}</b><small>Expires {String(savedPaymentMethod.expiry_month).padStart(2, "0")}/{String(savedPaymentMethod.expiry_year).slice(-2)}</small></button>}{useSaved && savedPaymentMethod ? <button type="button" className="text-button another-card" onClick={() => setUseSaved(false)}>Use another card</button> : <><Field label="Local demo card number" value={form.cardNumber} onChange={(value) => setForm({ ...form, cardNumber: value })} inputMode="numeric" placeholder="4242 4242 4242 4242" required /><div className="field-grid"><Field label="Expiry" value={form.expiry} onChange={(value) => setForm({ ...form, expiry: value })} placeholder="MM/YY" required /><Field label="CVC" type="password" value={form.cvc} onChange={(value) => setForm({ ...form, cvc: value })} inputMode="numeric" required /></div></>}{error && <p className="error-message">{error}</p>}<p className="payment-note">Stripe receives card data only on its hosted test page. The local fallback stores only the last four digits.</p><button className="primary-button" disabled={busy}>{busy ? "Confirming…" : `Confirm local demo payment €${estimatedTotal.toFixed(2)}`}<span>→</span></button></form></article>;
}

function PlanResults({ results, best, selectedPlan, setSelectedPlan, setPayment, token, payment, paymentMethod, rewardPoints, refreshProfile }) {
  const plans = results.filter((result) => result.mode === "normal" || result.mode === "v1g");
  return <section className="results-block"><div className="card-heading"><div><p className="eyebrow">2 CHARGING MODES</p><h3>Choose how you want to charge</h3></div><span className="step-pill">02</span></div><div className="mode-grid two">{plans.map((result) => <ModeCard key={`${result.mode}-${result.schedule_id}`} result={result} recommended={result === best} selected={selectedPlan?.schedule_id === result.schedule_id} onSelect={() => { setSelectedPlan(result); setPayment(null); }} />)}</div>{selectedPlan ? <PaymentPanel key={selectedPlan.schedule_id} plan={selectedPlan} token={token} payment={payment} onPaid={(receipt) => { setPayment(receipt); refreshProfile().catch(() => {}); }} savedPaymentMethod={paymentMethod} availablePoints={rewardPoints} /> : <p className="choose-prompt">Select one plan above to review its exact time before payment.</p>}</section>;
}

function connectorsAreCompatible(vehicle, station) {
  if (!vehicle?.connector_types || !station?.charger_type) return true;
  const canonical = (value) => value.toLowerCase().replace(/[^a-z0-9]/g, "");
  const stationConnector = canonical(station.charger_type);
  return vehicle.connector_types.split(",").some((connector) => {
    const vehicleConnector = canonical(connector);
    return vehicleConnector && (
      vehicleConnector.includes(stationConnector) || stationConnector.includes(vehicleConnector)
    );
  });
}

function PlanView({ token, vehicles, stations, paymentMethod, rewardPoints, results, setResults, setError, refreshProfile }) {
  const rankedStations = useMemo(() => [...stations].sort((a, b) => {
    const aUsable = a.operational_status === "online" && a.available_chargers > 0;
    const bUsable = b.operational_status === "online" && b.available_chargers > 0;
    if (aUsable !== bUsable) return bUsable - aUsable;
    if (a.available_chargers !== b.available_chargers) return b.available_chargers - a.available_chargers;
    return b.power_kw - a.power_kw;
  }), [stations]);
  const firstVehicle = vehicles[0];
  const initialStation = rankedStations.find((station) => station.operational_status === "online" && station.available_chargers > 0 && connectorsAreCompatible(firstVehicle, station));
  const [form, setForm] = useState({ vehicleId: firstVehicle?.id ?? "", stationId: initialStation?.id ?? "", currentSoc: 30, targetSoc: 80, startTime: nextQuarter(), departureTime: nextMorning() });
  const [busy, setBusy] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [payment, setPayment] = useState(null);
  const best = useMemo(() => { const visible = results.filter((result) => result.mode === "normal" || result.mode === "v1g"); return visible.length ? [...visible].sort((a, b) => a.cost_eur - b.cost_eur)[0] : null; }, [results]);
  const selectedVehicle = vehicles.find((vehicle) => vehicle.id === Number(form.vehicleId)) || firstVehicle;
  const recommendedStation = rankedStations.find((station) => station.operational_status === "online" && station.available_chargers > 0 && connectorsAreCompatible(selectedVehicle, station));
  const selectedStation = stations.find((station) => station.id === Number(form.stationId));

  useEffect(() => {
    const currentVehicle = vehicles.find((vehicle) => vehicle.id === Number(form.vehicleId));
    if (!currentVehicle) setForm((current) => ({ ...current, vehicleId: firstVehicle?.id ?? "" }));
    const currentStation = stations.find((station) => station.id === Number(form.stationId));
    const stationCannotBeUsed = !currentStation
      || currentStation.operational_status !== "online"
      || currentStation.available_chargers < 1
      || !connectorsAreCompatible(selectedVehicle, currentStation);
    if (stationCannotBeUsed) {
      setForm((current) => ({ ...current, stationId: recommendedStation?.id ?? "" }));
    }
  }, [vehicles, stations, form.vehicleId, form.stationId, recommendedStation, selectedVehicle]);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    if (!vehicles.length) { setError("Add a vehicle before planning a charging session."); return; }
    setBusy(true);
    setSelectedPlan(null);
    setPayment(null);
    try {
      const stationId = Number(form.stationId);
      if (!stationId) throw new Error("No Austrian charging station is available.");
      const startTime = new Date(form.startTime);
      const departureTime = new Date(form.departureTime);
      if (departureTime <= startTime) throw new Error("Ready by must be after Start charging after.");
      const chargingRequest = await api.post("/charging-requests", { vehicle_id: Number(form.vehicleId), station_id: stationId, current_soc: Number(form.currentSoc), target_soc: Number(form.targetSoc), earliest_start_time: startTime.toISOString(), departure_time: departureTime.toISOString() }, token);
      const optionRequests = [
        ["normal", "balanced"],
        ["v1g", "balanced"],
      ];
      const comparison = await Promise.all(optionRequests.map(([mode, variant]) => api.post(`/optimization/${chargingRequest.id}`, { mode, variant }, token)));
      setResults(comparison);
      await refreshProfile();
    } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };

  return (
    <section className="view-stack">
      <StationMap stations={stations} selectedStationId={form.stationId} vehicle={selectedVehicle} onSelect={(stationId) => setForm((current) => ({ ...current, stationId }))} hideIneligible />
      <div className="planner-grid">
        <form className="content-card planner-card" onSubmit={submit}>
          <div className="card-heading"><div><p className="eyebrow">NEW SESSION</p><h3>Charging preferences</h3></div><span className="step-pill">01</span></div>
          <Field label="Vehicle"><select value={form.vehicleId} onChange={(e) => setForm({ ...form, vehicleId: e.target.value })}>{vehicles.length ? vehicles.map((v) => <option key={v.id} value={v.id}>{v.model} · {v.battery_capacity} kWh · {v.connector_types}</option>) : <option value="">No vehicle added</option>}</select></Field>
          <Field label="Station selected on map"><input value={selectedStation ? `${selectedStation.station_name} · ${selectedStation.city}` : "Choose an available station on the map"} disabled /></Field>
          {selectedStation && <div className="station-status available"><i /><div><b>{selectedStation.available_chargers} of {selectedStation.total_chargers} chargers available</b><small>{selectedStation.power_kw} kW · {selectedStation.charger_type} · {selectedStation.availability_source === "simulated" ? "Demo estimate, not live occupancy" : `${selectedStation.availability_source} status · updated ${selectedStation.last_status_at ? new Date(selectedStation.last_status_at).toLocaleString() : "unknown"}`}</small></div></div>}
          <div className="field-grid"><Field label="Current SoC (%)" type="number" value={form.currentSoc} onChange={(v) => setForm({ ...form, currentSoc: v })} min="0" max="99" /><Field label="Target SoC (%)" type="number" value={form.targetSoc} onChange={(v) => setForm({ ...form, targetSoc: v })} min="1" max="100" /></div>
          <div className="field-grid planning-dates"><Field label="Car available from (you choose)" type="datetime-local" value={form.startTime} onChange={(v) => setForm({ ...form, startTime: v })} /><Field label="Car must be ready by (you choose)" type="datetime-local" value={form.departureTime} onChange={(v) => setForm({ ...form, departureTime: v })} /></div>
          <p className="planning-window-note">You choose the dates. Smart EV chooses one exact continuous charging time inside this window and shows it before payment.</p>
          <button className="primary-button" disabled={busy || !form.stationId}>{busy ? "Optimizing…" : "Build my smart plan"}<span>→</span></button>
        </form>
        <article className="insight-card"><p className="eyebrow">{results[0]?.forecast_source === "machine_learning" ? "SMART FORECAST READY" : "AUSTRIAN ENERGY DATA"}</p><h3>A better time<br />to charge.</h3><p>Smart EV compares the available times before your departure and recommends a period with a better price, less grid pressure and more clean energy.</p><div className="formula"><span>Price</span><span>Grid activity</span><span>Clean energy</span></div>{results[0] && <small className="model-label">Recommendation calculated automatically</small>}</article>
      </div>
      {results.length > 0 && <PlanResults results={results} best={best} selectedPlan={selectedPlan} setSelectedPlan={setSelectedPlan} setPayment={setPayment} token={token} payment={payment} paymentMethod={paymentMethod} rewardPoints={rewardPoints} refreshProfile={refreshProfile} />}
    </section>
  );
}

function V2GOffersView({ token, vehicles, stations, setError, refreshProfile }) {
  const v2gVehicles = vehicles.filter((vehicle) => vehicle.supports_v2g);
  const compatibleStations = stations.filter((station) => station.supports_v2g && station.operational_status === "online" && station.available_chargers > 0);
  const [form, setForm] = useState({ vehicleId: v2gVehicles[0]?.id ?? "", stationId: compatibleStations[0]?.id ?? "", currentSoc: 80, minimumSoc: 60, availableUntil: nextMorning() });
  const [offer, setOffer] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!v2gVehicles.some((vehicle) => vehicle.id === Number(form.vehicleId))) {
      setForm((current) => ({ ...current, vehicleId: v2gVehicles[0]?.id ?? "" }));
    }
    const selectedVehicle = v2gVehicles.find((vehicle) => vehicle.id === Number(form.vehicleId));
    const eligible = compatibleStations.filter((station) => connectorsAreCompatible(selectedVehicle, station));
    if (!eligible.some((station) => station.id === Number(form.stationId))) {
      setForm((current) => ({ ...current, stationId: eligible[0]?.id ?? "" }));
    }
  }, [vehicles, stations, form.vehicleId, form.stationId]);

  const findOffer = async (event) => {
    event.preventDefault(); setError(""); setBusy(true); setOffer(null);
    try {
      const result = await api.post("/v2g-offers", {
        vehicle_id: Number(form.vehicleId),
        station_id: Number(form.stationId),
        current_soc: Number(form.currentSoc),
        minimum_soc: Number(form.minimumSoc),
        available_until: new Date(form.availableUntil).toISOString(),
      }, token);
      setOffer(result);
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  const answerOffer = async (answer) => {
    setError(""); setBusy(true);
    try {
      const updated = await api.post(`/v2g-offers/${offer.id}/${answer}`, {}, token);
      setOffer(updated);
      await refreshProfile();
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  const simulateDelivery = async () => {
    setError(""); setBusy(true);
    try {
      const completed = await api.post(`/v2g-offers/${offer.id}/simulate-delivery`, {}, token);
      setOffer(completed);
      await refreshProfile();
    } catch (requestError) { setError(requestError.message); }
    finally { setBusy(false); }
  };

  const selectedVehicle = v2gVehicles.find((vehicle) => vehicle.id === Number(form.vehicleId));
  const selectableStations = compatibleStations.filter((station) => connectorsAreCompatible(selectedVehicle, station));
  const selectedStation = selectableStations.find((station) => station.id === Number(form.stationId));
  const offerStation = offer ? stations.find((station) => station.id === offer.station_id) : null;
  return <section className="view-stack"><article className="v2g-hero"><div><p className="eyebrow">SEPARATE GRID SERVICE</p><h2>Earn from spare battery energy.</h2><p>Only a vehicle and station explicitly configured for bidirectional V2G can create an offer.</p></div><div className="v2g-flow"><span>Compatible car</span><b>→</b><span>V2G station</span><b>→</b><span>Meter verification</span><b>→</b><span>Wallet reward</span></div></article><StationMap stations={stations} selectedStationId={form.stationId} vehicle={selectedVehicle} onSelect={(stationId) => setForm((current) => ({ ...current, stationId }))} v2gOnly /><div className="split-grid v2g-offers-layout"><form className="content-card" onSubmit={findOffer}><div className="card-heading"><div><p className="eyebrow">COMPATIBILITY CHECK</p><h3>Check for a V2G offer</h3></div></div><Field label="V2G-compatible vehicle"><select value={form.vehicleId} onChange={(event) => setForm({ ...form, vehicleId: event.target.value })}>{v2gVehicles.length ? v2gVehicles.map((vehicle) => <option key={vehicle.id} value={vehicle.id}>{vehicle.model} · V2G ready</option>) : <option value="">No V2G-compatible vehicle</option>}</select></Field><Field label="Station selected on map"><input value={selectedStation ? `${selectedStation.station_name} · ${selectedStation.city}` : "Choose a blue V2G station on the map"} disabled /></Field>{selectedStation && <div className="station-status available"><i /><div><b>{selectedStation.station_name} selected for V2G export</b><small>{selectedStation.city} · {selectedStation.power_kw} kW · {selectedStation.charger_type} · {selectedStation.available_chargers}/{selectedStation.total_chargers} free</small></div></div>}<div className="field-grid"><Field label="Battery now (%)" type="number" min="1" max="100" value={form.currentSoc} onChange={(value) => setForm({ ...form, currentSoc: value })} /><Field label="Minimum reserve to keep (%)" type="number" min="0" max="99" value={form.minimumSoc} onChange={(value) => setForm({ ...form, minimumSoc: value })} /></div><Field label="Car plugged in until" type="datetime-local" value={form.availableUntil} onChange={(value) => setForm({ ...form, availableUntil: value })} /><p className="planning-window-note">Choose a blue station directly on the map. Car, connector, availability and bidirectional V2G support are checked before an offer is calculated.</p><button className="primary-button" disabled={busy || !selectedVehicle || !form.stationId}>{busy ? "Checking grid…" : "Check grid offers"}<span>→</span></button></form><article className="content-card v2g-offer-result"><div className="card-heading"><div><p className="eyebrow">GRID NOTIFICATION</p><h3>{offer ? "Offer details" : "No offer checked yet"}</h3></div></div>{!offer && <div className="v2g-empty-offer"><b>How it works</b><p>If the grid needs energy while your compatible car is connected to a bidirectional station, you receive one offer with the export amount, time and reward.</p></div>}{offer && <div className={`v2g-live-offer ${offer.status}`}><span className="offer-status">{offer.status === "offered" ? "NEW GRID REQUEST" : offer.status.toUpperCase()}</span><h3>Send {offer.export_energy_kwh.toFixed(2)} kWh to the grid</h3><div className="offer-reward"><small>REWARD AFTER METER CONFIRMATION</small><strong>€{offer.reward_eur.toFixed(2)}</strong><span>+ {Math.round(offer.export_energy_kwh * 10)} points</span></div><div className="offer-details"><span><b>Station</b>{offerStation ? `${offerStation.station_name} · ${offerStation.city}` : `Station #${offer.station_id}`}</span><span><b>Export time</b>{viennaDay.format(new Date(offer.export_start))} · {viennaTime.format(new Date(offer.export_start))}–{viennaTime.format(new Date(offer.export_end))}</span><span><b>Battery protection</b>Never below {offer.minimum_soc}%</span></div>{offer.status === "offered" && <div className="offer-actions"><button className="primary-button" disabled={busy} onClick={() => answerOffer("accept")}>Accept offer<span>→</span></button><button className="secondary-button" disabled={busy} onClick={() => answerOffer("decline")}>Decline</button></div>}{offer.status === "accepted" && <div className="meter-pending"><p><b>Accepted — waiting for operator meter confirmation.</b><br />No reward or points have been credited yet.</p></div>}{offer.status === "completed" && <p className="success-message">Meter confirmed {offer.delivered_energy_kwh.toFixed(2)} kWh. €{offer.credited_reward_eur.toFixed(2)} and points were credited.</p>}{offer.status === "declined" && <p className="muted">Offer declined. No battery energy or reward was recorded.</p>}</div>}<p className="payment-note">Academic simulation. The operator dashboard replaces the driver-side meter simulation.</p></article></div></section>;
}

function OperatorDashboard({ token, setError }) {
  const [dashboard, setDashboard] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const load = () => api.get("/operator/dashboard", token).then(setDashboard).catch((error) => setError(error.message));
  useEffect(() => { load(); }, [token]);

  const updateReservation = async (reservation, statusValue) => {
    setBusyId(`r-${reservation.id}`); setError("");
    try { await api.patch(`/operator/reservations/${reservation.id}`, { status: statusValue }, token); await load(); }
    catch (error) { setError(error.message); } finally { setBusyId(null); }
  };
  const confirmDelivery = async (offer) => {
    const value = window.prompt("Metered energy delivered (kWh)", offer.export_energy_kwh.toFixed(2));
    if (value === null) return;
    setBusyId(`v-${offer.id}`); setError("");
    try { await api.post(`/operator/v2g-offers/${offer.id}/confirm-delivery`, { delivered_energy_kwh: Number(value) }, token); await load(); }
    catch (error) { setError(error.message); } finally { setBusyId(null); }
  };

  if (!dashboard) return <article className="content-card"><p>Loading operator dashboard…</p></article>;
  return <section className="view-stack"><article className="operator-hero"><div><p className="eyebrow">STATION OPERATIONS</p><h2>{dashboard.station.station_name}</h2><p>{dashboard.station.city} · {dashboard.station.available_chargers}/{dashboard.station.total_chargers} chargers free · {dashboard.station.supports_v2g ? "V2G enabled" : "Charging only"}</p></div><div className="operator-kpis"><StatCard label="Confirmed bookings" value={dashboard.confirmed_reservations} detail="Upcoming station slots" /><StatCard label="V2G meter checks" value={dashboard.pending_v2g_deliveries} detail="Awaiting operator proof" /></div></article><div className="split-grid operator-tables"><article className="content-card"><div className="card-heading"><div><p className="eyebrow">BOOKINGS</p><h3>Station reservations</h3></div></div>{dashboard.reservations.length ? dashboard.reservations.map((reservation) => <div className="operator-row" key={reservation.id}><div><b>Reservation #{reservation.id}</b><small>{new Date(reservation.start_time).toLocaleString()} · Vehicle #{reservation.vehicle_id}</small></div><span className={`status-${reservation.status}`}>{reservation.status}</span>{reservation.status === "confirmed" && <div className="operator-actions"><button disabled={busyId === `r-${reservation.id}`} onClick={() => updateReservation(reservation, "completed")}>Complete</button><button disabled={busyId === `r-${reservation.id}`} onClick={() => updateReservation(reservation, "cancelled")}>Cancel</button></div>}</div>) : <EmptyCopy text="No reservations for this station." />}</article><article className="content-card"><div className="card-heading"><div><p className="eyebrow">V2G METER</p><h3>Energy verification</h3></div></div>{dashboard.v2g_offers.length ? dashboard.v2g_offers.map((offer) => <div className="operator-row" key={offer.id}><div><b>Offer #{offer.id} · {offer.export_energy_kwh.toFixed(2)} kWh</b><small>{offer.status} · reward quote €{offer.reward_eur.toFixed(2)}</small></div><span className={`status-${offer.status}`}>{offer.status}</span>{offer.status === "accepted" && <button className="primary-button compact" disabled={busyId === `v-${offer.id}`} onClick={() => confirmDelivery(offer)}>Confirm meter</button>}</div>) : <EmptyCopy text="No V2G offers for this station." />}</article></div></section>;
}

function VehiclesView({ token, catalog, vehicles, setVehicles, setResults, setError }) {
  const [busy, setBusy] = useState(false);
  const [removingId, setRemovingId] = useState(null);
  const submit = async (form) => {
    setBusy(true); setError("");
    try { const vehicle = await api.post("/vehicles", form, token); setVehicles([...vehicles, vehicle]); }
    catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };
  const remove = async (vehicle) => {
    if (!window.confirm(`Remove ${vehicle.model} from your garage? Your previous charging history will be kept.`)) return;
    setRemovingId(vehicle.id); setError("");
    try {
      await api.delete(`/vehicles/${vehicle.id}`, token);
      setVehicles(vehicles.filter((item) => item.id !== vehicle.id));
      setResults([]);
    } catch (requestError) { setError(requestError.message); }
    finally { setRemovingId(null); }
  };
  return <section className="view-stack"><div className="split-grid vehicles-layout"><article className="content-card"><div className="card-heading"><div><p className="eyebrow">MY GARAGE</p><h3>Connected vehicles</h3></div><span className="count-pill">{vehicles.length}</span></div>{vehicles.length ? vehicles.map((vehicle) => <VehicleRow key={vehicle.id} vehicle={vehicle} onRemove={remove} removing={removingId === vehicle.id} />) : <EmptyCopy text="Your garage is empty." />}</article><article className="content-card"><div className="card-heading"><div><p className="eyebrow">ADD VEHICLE</p><h3>Connect another EV</h3></div></div><VehicleForm catalog={catalog} onSubmit={submit} busy={busy} buttonLabel="Add to my garage" /></article></div></section>;
}

function RewardsView({ token, user, rewards, payments }) {
  const [filter, setFilter] = useState("all");
  const filtered = rewards.filter((reward) => filter === "all" || reward.reward_type === filter);
  const earnedPoints = rewards.reduce((sum, reward) => sum + reward.points, 0);
  const v1gSavings = rewards.filter((reward) => reward.reward_type === "v1g_saving").reduce((sum, reward) => sum + reward.saving_eur, 0);
  const v2gCash = rewards.filter((reward) => reward.reward_type === "v2g_export").reduce((sum, reward) => sum + (reward.reward || 0), 0);
  const openInvoice = async (payment) => {
    const invoiceWindow = window.open("", "_blank");
    try {
      const invoice = await api.get(`/payments/${payment.id}/invoice`, token);
      if (!invoiceWindow) return;
      const safe = (value) => String(value ?? "").replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]));
      invoiceWindow.document.write(`<!doctype html><html><head><title>Invoice ${safe(invoice.reference)}</title><style>body{font:15px Arial;max-width:760px;margin:50px auto;color:#102d23}h1{font-size:34px}.row{display:flex;justify-content:space-between;border-bottom:1px solid #ddd;padding:12px 0}.total{font-size:22px;font-weight:bold}small{color:#68766f}@media print{button{display:none}}</style></head><body><h1>Smart EV invoice</h1><p><b>${safe(invoice.reference)}</b><br><small>${invoice.issued_at ? safe(new Date(invoice.issued_at).toLocaleString()) : ""}</small></p><div class="row"><span>Customer</span><b>${safe(invoice.customer_name)} · ${safe(invoice.customer_email)}</b></div><div class="row"><span>Vehicle / station</span><b>${safe(invoice.vehicle_model || "—")} · ${safe(invoice.station_name || "—")}</b></div><div class="row"><span>Charging time</span><b>${invoice.start_time ? safe(new Date(invoice.start_time).toLocaleString()) : "—"}</b></div><div class="row"><span>Original amount</span><b>€${invoice.original_amount.toFixed(2)}</b></div><div class="row"><span>Points discount</span><b>-€${invoice.points_discount_eur.toFixed(2)}</b></div><div class="row total"><span>Paid</span><b>€${invoice.amount_paid.toFixed(2)} ${safe(invoice.currency)}</b></div><p><small>Provider: ${safe(invoice.provider)}. Academic project invoice.</small></p><button onclick="window.print()">Print / Save PDF</button></body></html>`);
      invoiceWindow.document.close();
    } catch (error) { if (invoiceWindow) invoiceWindow.close(); window.alert(error.message); }
  };
  return <section className="view-stack"><article className="rewards-hero"><div><p className="eyebrow">SMART EV WALLET</p><h2>€{user.wallet_balance.toFixed(2)}</h2><p>V1G savings become points. Verified V2G export adds points and wallet credit.</p></div><div className="points-orbit"><strong>{user.reward_points}</strong><span>available points</span></div></article><div className="reward-summary"><StatCard label="Total points earned" value={earnedPoints} detail="Before redemptions" /><StatCard label="V1G savings" value={`€${v1gSavings.toFixed(2)}`} detail="Optimized charging value" /><StatCard label="V2G wallet earned" value={`€${v2gCash.toFixed(2)}`} detail="Meter-confirmed exports" /></div><article className="content-card"><div className="card-heading"><div><p className="eyebrow">REWARD LEDGER</p><h3>Where every point came from</h3></div><div className="reward-filters">{[["all","All"],["v1g_saving","V1G"],["v2g_export","V2G"]].map(([key,label]) => <button key={key} className={filter === key ? "active" : ""} onClick={() => setFilter(key)}>{label}</button>)}</div></div>{filtered.length ? filtered.map((reward) => <div className="reward-ledger-row" key={reward.id}><span className={`reward-type ${reward.reward_type}`}>{reward.reward_type === "v1g_saving" ? "V1G" : "V2G"}</span><div><b>{reward.reward_type === "v1g_saving" ? "Smart charging saving" : "Verified grid export"}</b><small>{reward.transaction_time ? new Date(reward.transaction_time).toLocaleString() : ""}{reward.energy_returned ? ` · ${reward.energy_returned.toFixed(2)} kWh exported` : ""}</small></div><strong>+{reward.points} pts</strong><em>{reward.reward_type === "v1g_saving" ? `€${reward.saving_eur.toFixed(2)} saved` : `€${(reward.reward || 0).toFixed(2)} earned`}</em></div>) : <EmptyCopy text="No reward transaction matches this filter." />}</article><article className="content-card"><div className="card-heading"><div><p className="eyebrow">PAYMENTS & INVOICES</p><h3>Billing history</h3></div></div>{payments.length ? payments.map((payment) => <div className="invoice-row" key={payment.id}><div><b>{payment.reference}</b><small>{payment.created_at ? new Date(payment.created_at).toLocaleString() : ""} · {payment.provider === "stripe_test" ? "Stripe test" : "Local demo"}</small></div><strong>€{payment.amount.toFixed(2)}</strong><button onClick={() => openInvoice(payment)}>View invoice</button>{payment.invoice_pdf && <a href={payment.invoice_pdf} target="_blank" rel="noreferrer">Stripe PDF</a>}</div>) : <EmptyCopy text="Paid charging reservations and their invoices will appear here." />}</article></section>;
}

function PasswordSettings({ token }) {
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const save = async (event) => {
    event.preventDefault(); setError(""); setMessage("");
    if (form.new_password !== form.confirm_password) { setError("New passwords do not match."); return; }
    try {
      await api.post("/me/change-password", form, token);
      setForm({ current_password: "", new_password: "", confirm_password: "" });
      setMessage("Password changed successfully.");
    } catch (requestError) { setError(requestError.message); }
  };
  return <form className="content-card" onSubmit={save}><div className="card-heading"><div><p className="eyebrow">SECURITY</p><h3>Change password</h3></div></div><Field label="Current password" type="password" value={form.current_password} onChange={(value) => setForm({ ...form, current_password: value })} minLength="8" autoComplete="current-password" required /><Field label="New password" type="password" value={form.new_password} onChange={(value) => setForm({ ...form, new_password: value })} minLength="8" autoComplete="new-password" required /><Field label="Confirm new password" type="password" value={form.confirm_password} onChange={(value) => setForm({ ...form, confirm_password: value })} minLength="8" autoComplete="new-password" required />{error && <p className="error-message">{error}</p>}<button className="primary-button">Change password<span>→</span></button>{message && <p className="success-message">{message}</p>}</form>;
}

function CardSettings({ token, paymentMethod, setPaymentMethod }) {
  const [editing, setEditing] = useState(!paymentMethod);
  const [form, setForm] = useState({ cardholder: "", cardNumber: "", expiry: "", cvc: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const save = async (event) => {
    event.preventDefault(); setError(""); setMessage("");
    const digits = form.cardNumber.replace(/\D/g, "");
    const expiry = form.expiry.match(/^(\d{2})\/(\d{2})$/);
    if (digits.length !== 16 || !expiry || !/^\d{3,4}$/.test(form.cvc)) { setError("Use 16 card digits, MM/YY and a 3–4 digit CVC."); return; }
    const brand = digits.startsWith("4") ? "Visa" : /^5[1-5]/.test(digits) ? "Mastercard" : "Other";
    try {
      const saved = await api.post("/me/payment-method", { cardholder_name: form.cardholder, brand, last4: digits.slice(-4), expiry_month: Number(expiry[1]), expiry_year: 2000 + Number(expiry[2]) }, token);
      setPaymentMethod(saved); setForm({ cardholder: "", cardNumber: "", expiry: "", cvc: "" }); setEditing(false); setMessage("Default payment card saved.");
    } catch (requestError) { setError(requestError.message); }
  };
  if (paymentMethod && !editing) return <article className="content-card"><div className="card-heading"><div><p className="eyebrow">PAYMENT</p><h3>Default card</h3></div></div><div className="settings-card-preview"><span>{paymentMethod.brand}</span><strong>•••• •••• •••• {paymentMethod.last4}</strong><div><small>{paymentMethod.cardholder_name}</small><small>{String(paymentMethod.expiry_month).padStart(2, "0")}/{String(paymentMethod.expiry_year).slice(-2)}</small></div></div>{message && <p className="success-message">{message}</p>}<button className="secondary-button" onClick={() => setEditing(true)}>Replace payment card</button><p className="payment-note">Smart EV stores only a demo token and masked card information—not the card number or CVC.</p></article>;
  return <form className="content-card" onSubmit={save}><div className="card-heading"><div><p className="eyebrow">PAYMENT</p><h3>{paymentMethod ? "Replace payment card" : "Add default card"}</h3></div></div><Field label="Cardholder name" value={form.cardholder} onChange={(value) => setForm({ ...form, cardholder: value })} autoComplete="cc-name" required /><Field label="Demo card number" value={form.cardNumber} onChange={(value) => setForm({ ...form, cardNumber: value })} inputMode="numeric" placeholder="4242 4242 4242 4242" autoComplete="cc-number" required /><div className="field-grid"><Field label="Expiry" value={form.expiry} onChange={(value) => setForm({ ...form, expiry: value })} placeholder="MM/YY" autoComplete="cc-exp" required /><Field label="CVC" type="password" value={form.cvc} onChange={(value) => setForm({ ...form, cvc: value })} inputMode="numeric" autoComplete="cc-csc" required /></div>{error && <p className="error-message">{error}</p>}<button className="primary-button">Save default card<span>→</span></button>{paymentMethod && <button type="button" className="text-button cancel-card" onClick={() => setEditing(false)}>Cancel</button>}<p className="payment-note">The full number and CVC stay in your browser and are never sent or stored.</p></form>;
}

function SettingsView({ token, user, setUser, paymentMethod, setPaymentMethod, setError }) {
  const [form, setForm] = useState({ name: user.name ?? "", email: user.email ?? "" });
  const [saved, setSaved] = useState(false);
  const save = async (event) => { event.preventDefault(); setError(""); setSaved(false); try { const updated = await api.patch("/me", form, token); setUser(updated); setSaved(true); } catch (requestError) { setError(requestError.message); } };
  const setTheme = async (theme) => { try { const updated = await api.patch("/me", { theme }, token); setUser(updated); } catch (requestError) { setError(requestError.message); } };
  return <section className="view-stack"><div className="split-grid settings-layout"><form className="content-card" onSubmit={save}><div className="card-heading"><div><p className="eyebrow">ACCOUNT</p><h3>Personal information</h3></div></div><Field label="Full name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} required /><Field label="Email" type="email" value={form.email} onChange={(value) => setForm({ ...form, email: value })} required /><button className="primary-button">Save account changes<span>→</span></button>{saved && <p className="success-message">Account updated successfully.</p>}</form><article className="content-card"><div className="card-heading"><div><p className="eyebrow">APPEARANCE</p><h3>Choose your theme</h3></div></div><div className="theme-grid">{[["light", "☀", "Light"], ["dark", "◐", "Dark"], ["system", "◒", "System"]].map(([key, icon, label]) => <button key={key} className={user.theme === key ? "active" : ""} onClick={() => setTheme(key)}><span>{icon}</span><b>{label}</b><small>{key === "system" ? "Follow your device" : `${label} all the time`}</small></button>)}</div></article></div><div className="split-grid settings-layout"><PasswordSettings token={token} /><CardSettings token={token} paymentMethod={paymentMethod} setPaymentMethod={setPaymentMethod} /></div></section>;
}

function ForecastActualChart({ samples }) {
  if (!samples.length) return <p className="muted">No held-out evaluation samples available.</p>;
  const values = samples.flatMap((sample) => [sample.actual, sample.predicted]);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const range = maximum - minimum || 1;
  const points = (key) => samples.map((sample, index) => `${(index / (samples.length - 1 || 1)) * 100},${38 - ((sample[key] - minimum) / range) * 36}`).join(" ");
  return <div className="evaluation-chart"><svg viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label="Actual and predicted values over 96 held-out quarter-hour samples"><polyline className="actual-line" points={points("actual")} /><polyline className="predicted-line" points={points("predicted")} /></svg><div className="evaluation-legend"><span><i className="actual-dot" />Actual</span><span><i className="predicted-dot" />Predicted</span></div></div>;
}

function AIView({ token, stations }) {
  const [tab, setTab] = useState("forecast");
  const [forecast, setForecast] = useState(null);
  const [benchmark, setBenchmark] = useState(null);
  const [modelInfo, setModelInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [stationId, setStationId] = useState(stations[0]?.id ?? "");
  const [stationForecast, setStationForecast] = useState(null);
  const [evaluationTarget, setEvaluationTarget] = useState("electricity_price");

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    Promise.all([
      api.get("/ai/forecast-24h", token).catch(() => null),
      api.get("/ai/benchmark", token).catch(() => null),
      api.get("/ai/model-info", token).catch(() => null),
    ])
      .then(([fc, bm, info]) => {
        if (!mounted) return;
        setForecast(fc);
        setBenchmark(bm);
        setModelInfo(info);
        if (fc?.slots?.length) {
          const preferred = fc.slots
            .filter((slot) => slot.recommendation === "V1G_CHARGE")
            .sort((a, b) => a.composite_score - b.composite_score)[0];
          setSelectedSlot(preferred || fc.slots[0]);
        }
      })
      .catch((err) => {
        if (mounted) setError(err.message);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [token]);

  useEffect(() => {
    if (!stationId) return;
    api.get(`/ai/stations/${stationId}/availability-24h`, token)
      .then(setStationForecast)
      .catch(() => setStationForecast(null));
  }, [stationId, token]);

  if (loading) {
    return (
      <div className="empty-copy">
        <p>Preparing your charging recommendations…</p>
      </div>
    );
  }

  const slots = forecast?.slots || [];
  const hourlyPrices = forecast?.hourly_prices || [];
  const bestChargingWindow = forecast?.best_charging_window;
  const maxPrice = Math.max(...slots.map((s) => s.electricity_price), 10);
  const minPrice = Math.min(...slots.map((s) => s.electricity_price), 0);
  const chargeSlots = slots.filter((slot) => slot.recommendation === "V1G_CHARGE");
  const exportSlots = slots.filter((slot) => slot.recommendation === "V2G_DISCHARGE");
  const bestChargeSlot = chargeSlots.reduce(
    (best, slot) => (!best || slot.composite_score < best.composite_score ? slot : best),
    null
  );
  const bestExportSlot = exportSlots.reduce(
    (best, slot) => (!best || slot.electricity_price > best.electricity_price ? slot : best),
    null
  );
  const cleanestSlot = slots.reduce((best, slot) => (!best || slot.renewable_total > best.renewable_total ? slot : best), null);
  const reliability = forecast?.summary?.average_confidence_pct ?? 0;
  const reliabilityLabel = reliability >= 75 ? "High" : reliability >= 50 ? "Medium" : "Low";
  const levelFor = (value, minimum, maximum) => {
    const position = maximum === minimum ? 0.5 : (value - minimum) / (maximum - minimum);
    return position < 0.34 ? "Low" : position < 0.67 ? "Medium" : "High";
  };
  const minLoad = Math.min(...slots.map((slot) => slot.grid_load), 0);
  const maxLoad = Math.max(...slots.map((slot) => slot.grid_load), 1);
  const minRenewable = Math.min(...slots.map((slot) => slot.renewable_total), 0);
  const maxRenewable = Math.max(...slots.map((slot) => slot.renewable_total), 1);
  const bestStationAvailability = stationForecast?.ready
    ? stationForecast.slots.reduce((best, slot) => (!best || slot.availability_probability_pct > best.availability_probability_pct ? slot : best), null)
    : null;
  const readableSlotTime = (slot) => slot
    ? `${viennaDay.format(new Date(slot.timestamp))} · ${viennaTime.format(new Date(slot.timestamp))}`
    : "No slot available";
  const readableWindow = (window) => window
    ? `${viennaDay.format(new Date(window.start_time))} · ${viennaTime.format(new Date(window.start_time))}–${viennaTime.format(new Date(window.end_time))}`
    : "No period available";
  const priceSourceLabel = (source) => source === "published_day_ahead"
    ? "Published Austrian day-ahead price"
    : source === "mixed"
      ? "Published price + AI forecast"
      : "AI price forecast";

  return (
    <section className="view-stack ai-view-container">
      <article className="ai-hero-card">
        <div className="ai-hero-top">
          <div>
            <div className="ai-badge">
              <i /> Smart charging assistant
            </div>
            <h2>Your simple energy guide</h2>
            <p>
              You do not need to understand AI. We check tomorrow's prices, grid activity and clean energy,
              then tell you the best time to charge. Green means charge, blue means an optional V2G opportunity, and grey means wait.
            </p>
            {forecast?.forecast_mode === "historical_demo" && (
              <p className="muted">
                Demonstration mode: these recommendations use historical Austrian data, not today's live market.
              </p>
            )}
            {forecast?.forecast_mode === "current" && (
              <p className="muted">
                Real AI forecast updated from recent Austrian energy data. {forecast.published_price_slots} of {forecast.slot_count} price periods use published day-ahead market prices. Times are shown in Austria time.
              </p>
            )}
          </div>
        </div>
        <div className="ai-tab-buttons">
          <button
            className={`ai-tab-btn ${tab === "forecast" ? "active" : ""}`}
            onClick={() => setTab("forecast")}
          >
            Simple recommendations
          </button>
          <button
            className={`ai-tab-btn ${tab === "benchmark" ? "active" : ""}`}
            onClick={() => setTab("benchmark")}
          >
            Technical details
          </button>
        </div>
      </article>

      {tab === "forecast" && (
        <div className="ai-decision-grid">
          <article className="ai-decision-card charge">
            <span>BEST 1-HOUR CHARGING PERIOD</span>
            <strong>{readableWindow(bestChargingWindow)}</strong>
            <p>{bestChargingWindow ? `Average market price €${bestChargingWindow.average_price_eur_mwh}/MWh (€${bestChargingWindow.average_price_eur_kwh}/kWh). ${priceSourceLabel(bestChargingWindow.price_source)}.` : "No preferred charging period is available yet."}</p>
          </article>
          <article className="ai-decision-card export">
            <span>OPTIONAL: EARN WITH V2G</span>
            <strong>{readableSlotTime(bestExportSlot)}</strong>
            <p>{bestExportSlot ? "If your battery has spare energy above your reserve, the grid may offer a reward around this time." : "There is no useful V2G opportunity in this forecast."}</p>
          </article>
          <article className="ai-decision-card explanation">
            <span>WHY THIS HELPS</span>
            <strong>We compare 96 time periods</strong>
            <p>The assistant checks every 15 minutes for the next day. You only choose the suggested time; the technical calculations stay in the background.</p>
          </article>
        </div>
      )}

      {tab === "forecast" && forecast?.summary && (
        <div className="stat-grid forecast-kpis">
          <StatCard
            label="Average wholesale price"
            value={`€${forecast.summary.avg_price_eur_mwh}/MWh`}
            detail={`${priceSourceLabel(forecast.price_source)} · final station price is separate`}
            accent
          />
          <StatCard
            label="Best clean-energy moment"
            value={readableSlotTime(cleanestSlot)}
            detail="More solar and wind should be available"
          />
          <StatCard
            label="Prediction reliability"
            value={reliabilityLabel}
            detail={`${reliability}% · recommendations are estimates, not guarantees`}
          />
          <StatCard
            label="Recommended charging periods"
            value={`${chargeSlots.length}`}
            detail="Each period represents 15 minutes"
          />
        </div>
      )}

      {tab === "forecast" && hourlyPrices.length > 0 && (
        <article className="content-card hourly-price-card">
          <div className="card-heading">
            <div>
              <p className="eyebrow">AUSTRIAN PRICE BY HOUR</p>
              <h3>When electricity is cheaper</h3>
            </div>
            <span className={`data-source-pill ${forecast.price_source}`}>
              {priceSourceLabel(forecast.price_source)}
            </span>
          </div>
          <p className="market-price-warning">These are wholesale market prices. The station operator's retail tariff, taxes and charging fees are not included.</p>
          <div className="hourly-price-grid">
            {hourlyPrices.map((hour) => (
              <button
                type="button"
                key={hour.austria_hour}
                className={`hourly-price-row ${hour.action.toLowerCase()} ${bestChargingWindow && new Date(hour.start_time) <= new Date(bestChargingWindow.start_time) && new Date(hour.end_time) > new Date(bestChargingWindow.start_time) ? "best" : ""}`}
                onClick={() => {
                  const matchingSlot = slots.find((slot) => new Date(slot.timestamp) >= new Date(hour.start_time) && new Date(slot.timestamp) < new Date(hour.end_time));
                  if (matchingSlot) setSelectedSlot(matchingSlot);
                }}
              >
                <span>{viennaTime.format(new Date(hour.start_time))}–{viennaTime.format(new Date(hour.end_time))}</span>
                <strong>€{hour.price_eur_mwh.toFixed(2)}<small>/MWh</small></strong>
                <small>€{hour.price_eur_kwh.toFixed(4)}/kWh</small>
                <em>{hour.action === "CHARGE" ? "Good to charge" : hour.action === "V2G_EXPORT" ? "V2G opportunity" : "Wait"}</em>
              </button>
            ))}
          </div>
        </article>
      )}

      {tab === "forecast" && forecast?.tips?.length > 0 && (
        <article className="content-card ai-tips-card">
          <div className="card-heading"><div><p className="eyebrow">SMART TIPS</p><h3>How to use this recommendation</h3></div></div>
          <div className="ai-tip-grid">{forecast.tips.map((tip, index) => <div key={tip}><b>{String(index + 1).padStart(2, "0")}</b><p>{tip}</p></div>)}</div>
        </article>
      )}

      {tab === "forecast" && (
        <article className="forecast-visual-card">
          <div className="forecast-visual-header">
            <div>
              <p className="eyebrow">YOUR NEXT 24 HOURS · TAP ANY BAR FOR DETAILS</p>
              <h3>What should I do and when?</h3>
            </div>
            <div className="forecast-legend">
              <span><i className="legend-charge" /> Charge</span>
              <span><i className="legend-discharge" /> V2G export</span>
              <span><i className="legend-standard" /> Wait</span>
            </div>
          </div>

          <div className="forecast-chart-bars">
            {slots.map((s, idx) => {
              const heightPct = Math.max(
                12,
                Math.min(100, ((s.electricity_price - minPrice) / (maxPrice - minPrice || 1)) * 100)
              );
              const recClass =
                s.recommendation === "V1G_CHARGE"
                  ? "v1g"
                  : s.recommendation === "V2G_DISCHARGE"
                  ? "v2g"
                  : "standard";
              const isSelected = selectedSlot?.timestamp === s.timestamp;

              return (
                <div
                  key={s.timestamp || idx}
                  className={`forecast-bar-item ${recClass} ${isSelected ? "selected" : ""}`}
                  style={{ height: `${heightPct}%` }}
                  title={`${new Date(s.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}: €${s.electricity_price}/MWh (${s.recommendation})`}
                  onClick={() => setSelectedSlot(s)}
                  onMouseEnter={() => setSelectedSlot(s)}
                />
              );
            })}
          </div>

          {selectedSlot && (
            <div className="slot-inspector">
              <div>
                <small className="muted">SELECTED TIME</small>
                <div>
                  <b>
                    {new Date(selectedSlot.timestamp).toLocaleDateString([], { month: "short", day: "numeric" })} · {new Date(selectedSlot.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </b>
                </div>
              </div>
              <div>
                <small className="muted">WHOLESALE ELECTRICITY PRICE</small>
                <div><b>€{selectedSlot.electricity_price}/MWh</b></div>
                <small className="muted">€{(selectedSlot.electricity_price / 1000).toFixed(4)}/kWh · {priceSourceLabel(selectedSlot.price_source)}</small>
                {selectedSlot.price_interval && <small className="muted">Likely range: €{selectedSlot.price_interval[0]}–€{selectedSlot.price_interval[1]}</small>}
                <small className="muted">Not the final station tariff.</small>
              </div>
              <div>
                <small className="muted">GRID ACTIVITY</small>
                <div><b>{levelFor(selectedSlot.grid_load, minLoad, maxLoad)}</b></div>
                <small className="muted">Lower activity is generally better for charging.</small>
              </div>
              <div>
                <small className="muted">CLEAN ENERGY AVAILABLE</small>
                <div><b>{levelFor(selectedSlot.renewable_total, minRenewable, maxRenewable)}</b></div>
                <small className="muted">Based on expected solar and wind production.</small>
              </div>
              <div>
                <small className="muted">PREDICTION RELIABILITY</small>
                <div><b>{selectedSlot.confidence_pct >= 75 ? "High" : selectedSlot.confidence_pct >= 50 ? "Medium" : "Low"}</b></div>
                {selectedSlot.confidence_pct != null && <small className="muted">{selectedSlot.confidence_pct}% · actual conditions can change.</small>}
              </div>
              <div>
                <span
                  className={`slot-action-tag ${
                    selectedSlot.recommendation === "V1G_CHARGE"
                      ? "v1g"
                      : selectedSlot.recommendation === "V2G_DISCHARGE"
                      ? "v2g"
                      : "standard"
                  }`}
                >
                  {selectedSlot.recommendation === "V1G_CHARGE"
                    ? "Charge during this period"
                    : selectedSlot.recommendation === "V2G_DISCHARGE"
                    ? "Export energy during this period"
                    : "Wait — no action recommended"}
                </span>
                <small className="slot-explanation">{selectedSlot.recommendation === "V1G_CHARGE" ? "A better moment to charge because price and grid activity are favourable." : selectedSlot.recommendation === "V2G_DISCHARGE" ? "The grid may value spare battery energy more during this period." : "Waiting may provide a better charging or V2G opportunity later."}</small>
              </div>
            </div>
          )}
        </article>
      )}

      {tab === "forecast" && (
        <article className="content-card station-ai-readiness">
          <div className="card-heading"><div><p className="eyebrow">CHARGING STATION</p><h3>Will a charger probably be free?</h3></div></div>
          <Field label="Charging station"><select value={stationId} onChange={(event) => setStationId(event.target.value)}>{stations.map((station) => <option key={station.id} value={station.id}>{station.station_name} · {station.city}</option>)}</select></Field>
          {stationForecast?.ready ? <p className="success-message">Best expected availability: {bestStationAvailability?.availability_probability_pct}% around {bestStationAvailability ? readableSlotTime(bestStationAvailability) : "the selected period"}.</p> : <p className="muted">We are still learning this station's busy and quiet times. Current connector availability remains visible in Plan charging. {stationForecast && `${stationForecast.observations}/${stationForecast.required_observations} readings collected.`}</p>}
        </article>
      )}

      {tab === "benchmark" && (
        <article className="content-card">
          <div className="card-heading">
            <div>
              <p className="eyebrow">ACADEMIC RIGOR & EMPIRICAL EVALUATION</p>
              <h3>Chronological model evaluation</h3>
            </div>
          </div>
          <p className="muted" style={{ marginBottom: "20px" }}>
            V3 selects Ridge or HistGradientBoosting per target on validation data, then reports performance on a later unseen test period.
          </p>

          {modelInfo?.model_type === "direct_multi_horizon" && <div className="benchmark-table-wrapper" style={{ marginBottom: "24px" }}><table className="benchmark-table"><thead><tr><th>V3 target</th><th>Selected model</th><th>Test MAE</th><th>Test RMSE</th><th>R²</th><th>80% interval coverage</th></tr></thead><tbody>{Object.entries(modelInfo.metrics).map(([target, result]) => <tr key={target} className="winner"><td>{target.replaceAll("_", " ")}</td><td>{result.selected_model}</td><td>{result.test.mae.toFixed(2)}</td><td>{result.test.rmse.toFixed(2)}</td><td>{result.test.r2.toFixed(3)}</td><td>{(result.test.interval_80_coverage * 100).toFixed(1)}%</td></tr>)}</tbody></table></div>}

          {modelInfo?.evaluation_samples && <div className="evaluation-panel"><div className="evaluation-heading"><div><p className="eyebrow">UNSEEN TEST PERIOD</p><h4>Forecast vs actual</h4></div><select value={evaluationTarget} onChange={(event) => setEvaluationTarget(event.target.value)}>{Object.keys(modelInfo.evaluation_samples).map((target) => <option key={target} value={target}>{target.replaceAll("_", " ")}</option>)}</select></div><ForecastActualChart samples={modelInfo.evaluation_samples[evaluationTarget] || []} /></div>}

          {["electricity_price", "grid_load", "solar_generation", "wind_generation"].map((target) => {
            const readable = target.replace("_", " ").toUpperCase();
            const unit = target.includes("price") ? "€/MWh" : "MW";

            return (
              <div key={target} style={{ marginBottom: "24px" }}>
                <h4 style={{ margin: "0 0 8px", font: "700 15px 'Manrope'" }}>
                  {readable} ({unit})
                </h4>
                <div className="benchmark-table-wrapper">
                  <table className="benchmark-table">
                    <thead>
                      <tr>
                        <th>Model</th>
                        <th>MAE</th>
                        <th>RMSE</th>
                        <th>R²</th>
                        <th>Training Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {benchmark?.models?.map((m) => {
                        const met = m.metrics[target];
                        const isWinner = m.model_name.includes("HistGradientBoosting");
                        return (
                          <tr key={m.model_name} className={isWinner ? "winner" : ""}>
                            <td>
                              {m.model_name}
                              {isWinner && <span className="winner-pill">Legacy benchmark winner</span>}
                            </td>
                            <td>{met ? met.mae.toFixed(4) : "—"}</td>
                            <td>{met ? met.rmse.toFixed(4) : "—"}</td>
                            <td>{met ? met.r2.toFixed(4) : "—"}</td>
                            <td>{m.train_time_sec}s</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}
        </article>
      )}
    </section>
  );
}
