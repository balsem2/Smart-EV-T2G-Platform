import { useEffect, useMemo, useState } from "react";

import { api } from "./api";

const nextMorning = () => {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  date.setHours(7, 0, 0, 0);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
};

const navigation = [
  ["overview", "⌂", "Overview"],
  ["plan", "⚡", "Plan charging"],
  ["vehicles", "◇", "My vehicles"],
  ["rewards", "◎", "Rewards"],
  ["settings", "⚙", "Settings"],
];

const modeCopy = {
  normal: ["Normal", "Charge immediately"],
  v1g: ["Smart V1G", "Shift demand intelligently"],
  v2g: ["V2G", "Charge and support the grid"],
};

function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const payload = mode === "register"
        ? form
        : { email: form.email, password: form.password };
      const response = await api.post(`/auth/${mode}`, payload);
      onAuthenticated(response);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-story">
        <a className="brand brand--light" href="#top"><span className="brand-mark">⚡</span><span>Smart EV</span></a>
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
          <h2>{mode === "login" ? "Sign in to your account" : "Create your account"}</h2>
          <p className="muted">Your vehicles, plans and rewards stay connected to you.</p>

          <div className="auth-tabs">
            <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Login</button>
            <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Register</button>
          </div>

          <form onSubmit={submit}>
            {mode === "register" && (
              <Field label="Full name" value={form.name} onChange={(value) => setForm({ ...form, name: value })} required />
            )}
            <Field label="Email address" type="email" value={form.email} onChange={(value) => setForm({ ...form, email: value })} required />
            <Field label="Password" type="password" value={form.password} onChange={(value) => setForm({ ...form, password: value })} minLength="8" required />
            {error && <p className="error-message">{error}</p>}
            <button className="primary-button" disabled={loading}>
              {loading ? "Please wait…" : mode === "login" ? "Login" : "Create account"}<span>→</span>
            </button>
          </form>
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
      <header className="onboarding-header"><span className="brand"><span className="brand-mark">⚡</span><span>Smart EV</span></span><button className="logout-button" onClick={logout}>Log out</button></header>
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
  return (
    <aside className="sidebar">
      <button className="brand brand-button" onClick={() => setActive("overview")}>
        <span className="brand-mark">⚡</span><span>Smart EV</span>
      </button>
      <nav>
        {navigation.map(([key, icon, label]) => (
          <button key={key} className={active === key ? "active" : ""} onClick={() => setActive(key)}>
            <i>{icon}</i><span>{label}</span>
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
  return (
    <article className={`mode-card ${recommended ? "best" : ""} ${selected ? "selected" : ""}`} onClick={onSelect} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelect(); }} role="button" tabIndex="0">
      <div className="mode-card__top">
        <div><p className="eyebrow">{subtitle}</p><h3>{name}</h3></div>
        {recommended && <span className="best-pill">Recommended</span>}
      </div>
      <strong className="price">€{result.cost_eur.toFixed(2)}</strong>
      <Metric label="Saving" value={`€${result.saving_eur.toFixed(2)}`} />
      <Metric label="V2G reward" value={`€${result.v2g_reward_eur.toFixed(2)}`} />
      <Metric label="Active slots" value={result.slots.length} />
      <span className="choose-plan">{selected ? "✓ Selected" : "Choose this plan"}</span>
    </article>
  );
}

function Metric({ label, value }) {
  return <div className="metric-row"><span>{label}</span><b>{value}</b></div>;
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
  const [active, setActive] = useState("overview");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(Boolean(token));
  const [error, setError] = useState("");

  const loadData = async (activeToken) => {
    const [profile, ownedVehicles, availableStations, vehicleCatalog, rewardHistory, requestHistory, savedPaymentMethod] = await Promise.all([
      api.get("/me", activeToken),
      api.get("/vehicles", activeToken),
      api.get("/stations", activeToken),
      api.get("/catalog/vehicles", activeToken),
      api.get("/me/rewards", activeToken),
      api.get("/charging-requests", activeToken),
      api.get("/me/payment-method", activeToken),
    ]);
    setUser(profile);
    setVehicles(ownedVehicles);
    setStations(availableStations);
    setCatalog(vehicleCatalog);
    setRewards(rewardHistory);
    setRequests(requestHistory);
    setPaymentMethod(savedPaymentMethod);
  };

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    loadData(token).catch(() => logout()).finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    if (!token) return undefined;
    const interval = window.setInterval(() => {
      api.get("/stations", token).then(setStations).catch(() => {});
    }, 30000);
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
  if (loading || !user) return <div className="app-loader"><span>⚡</span><p>Loading Smart EV…</p></div>;

  if (!user.onboarding_completed) {
    return <Onboarding user={user} token={token} catalog={catalog} onCompleted={() => loadData(token)} logout={logout} />;
  }

  const refreshProfile = async () => {
    const [profile, rewardHistory, requestHistory] = await Promise.all([
      api.get("/me", token),
      api.get("/me/rewards", token),
      api.get("/charging-requests", token),
    ]);
    setUser(profile);
    setRewards(rewardHistory);
    setRequests(requestHistory);
  };

  return (
    <div className="app-shell">
      <Sidebar active={active} setActive={setActive} user={user} logout={logout} />
      <main className="app-main">
        <header className="app-header">
          <div><p className="kicker">SMART EV CONTROL CENTER</p><h1>{navigation.find(([key]) => key === active)?.[2]}</h1></div>
          <div className="live-status"><i /> Grid connected</div>
        </header>

        {error && <p className="error-message global-error">{error}</p>}
        {active === "overview" && <Overview user={user} vehicles={vehicles} requests={requests} rewards={rewards} setActive={setActive} />}
        {active === "plan" && <PlanView token={token} vehicles={vehicles} stations={stations} paymentMethod={paymentMethod} results={results} setResults={setResults} setError={setError} refreshProfile={refreshProfile} />}
        {active === "vehicles" && <VehiclesView token={token} catalog={catalog} vehicles={vehicles} setVehicles={setVehicles} setError={setError} />}
        {active === "rewards" && <RewardsView user={user} rewards={rewards} />}
        {active === "settings" && <SettingsView token={token} user={user} setUser={setUser} paymentMethod={paymentMethod} setPaymentMethod={setPaymentMethod} setError={setError} />}
      </main>
    </div>
  );
}

function Overview({ user, vehicles, requests, rewards, setActive }) {
  return (
    <section className="view-stack">
      <article className="welcome-card">
        <div><p className="eyebrow">GOOD ENERGY STARTS HERE</p><h2>Welcome back, {user.name?.split(" ")[0]}.</h2><p>Your account is ready to plan a cleaner, lower-cost charging session.</p></div>
        <button className="light-button" onClick={() => setActive("plan")}>Plan a charge <span>→</span></button>
      </article>
      <div className="stat-grid">
        <StatCard label="Reward wallet" value={`€${user.wallet_balance.toFixed(2)}`} detail="Earned through V2G" accent />
        <StatCard label="Smart points" value={user.reward_points} detail="10 points per exported kWh" />
        <StatCard label="My vehicles" value={vehicles.length} detail="Connected to this account" />
        <StatCard label="Charging plans" value={requests.length} detail="Saved sessions" />
      </div>
      <div className="split-grid">
        <article className="content-card">
          <div className="card-heading"><div><p className="eyebrow">GARAGE</p><h3>Your vehicles</h3></div><button className="text-button" onClick={() => setActive("vehicles")}>Manage →</button></div>
          {vehicles.length ? vehicles.slice(0, 3).map((vehicle) => <VehicleRow key={vehicle.id} vehicle={vehicle} />) : <EmptyCopy text="Add your first EV to start planning." />}
        </article>
        <article className="content-card">
          <div className="card-heading"><div><p className="eyebrow">RECENT VALUE</p><h3>V2G rewards</h3></div><button className="text-button" onClick={() => setActive("rewards")}>View all →</button></div>
          {rewards.length ? rewards.slice(0, 3).map((reward) => <RewardRow key={reward.id} reward={reward} />) : <EmptyCopy text="Your first V2G reward will appear here." />}
        </article>
      </div>
    </section>
  );
}

function StatCard({ label, value, detail, accent = false }) {
  return <article className={`stat-card ${accent ? "accent" : ""}`}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>;
}

function VehicleRow({ vehicle }) {
  return <div className="list-row"><span className="list-icon">EV</span><div><b>{vehicle.model}</b><small>{vehicle.battery_capacity} kWh battery</small></div><em>{vehicle.vehicle_age} yr</em></div>;
}

function RewardRow({ reward }) {
  return <div className="list-row"><span className="list-icon reward">↗</span><div><b>Grid support</b><small>{reward.energy_returned?.toFixed(2)} kWh exported</small></div><em>+€{reward.reward?.toFixed(2)}</em></div>;
}

function EmptyCopy({ text }) { return <p className="empty-copy">{text}</p>; }

function PaymentPanel({ plan, token, payment, onPaid, savedPaymentMethod }) {
  const [form, setForm] = useState({ cardholder: "", cardNumber: "", expiry: "", cvc: "" });
  const [useSaved, setUseSaved] = useState(Boolean(savedPaymentMethod));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [name] = modeCopy[plan.mode];

  const pay = async (event) => {
    event.preventDefault(); setError("");
    if (useSaved && savedPaymentMethod) {
      setBusy(true);
      try {
        const receipt = await api.post("/payments/checkout", { schedule_id: plan.schedule_id, payment_method: "saved_card", payment_method_id: savedPaymentMethod.id }, token);
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
      const receipt = await api.post("/payments/checkout", { schedule_id: plan.schedule_id, payment_method: "test_card", card_last4: digits.slice(-4) }, token);
      setForm({ cardholder: "", cardNumber: "", expiry: "", cvc: "" });
      onPaid(receipt);
    } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };

  if (payment) return <article className="payment-success"><span>✓</span><div><p className="eyebrow">PAYMENT CONFIRMED</p><h3>{name} is booked</h3><p>€{payment.amount.toFixed(2)} paid with card ending {payment.card_last4}.</p><small>Reference: {payment.reference}</small></div></article>;

  return <article className="payment-card"><div className="payment-summary"><div><p className="eyebrow">SELECTED PLAN</p><h3>{name}</h3><p>Advance payment confirms your charging plan.</p></div><strong>€{plan.cost_eur.toFixed(2)}</strong></div><form onSubmit={pay}>{savedPaymentMethod && <button type="button" className={`saved-card-choice ${useSaved ? "active" : ""}`} onClick={() => setUseSaved(true)}><span>{savedPaymentMethod.brand}</span><b>•••• {savedPaymentMethod.last4}</b><small>Expires {String(savedPaymentMethod.expiry_month).padStart(2, "0")}/{String(savedPaymentMethod.expiry_year).slice(-2)}</small></button>}{useSaved && savedPaymentMethod ? <button type="button" className="text-button another-card" onClick={() => setUseSaved(false)}>Use another card</button> : <><Field label="Cardholder name" value={form.cardholder} onChange={(value) => setForm({ ...form, cardholder: value })} autoComplete="cc-name" required /><Field label="Demo card number" value={form.cardNumber} onChange={(value) => setForm({ ...form, cardNumber: value })} inputMode="numeric" placeholder="4242 4242 4242 4242" autoComplete="cc-number" required /><div className="field-grid"><Field label="Expiry" value={form.expiry} onChange={(value) => setForm({ ...form, expiry: value })} placeholder="MM/YY" autoComplete="cc-exp" required /><Field label="CVC" type="password" value={form.cvc} onChange={(value) => setForm({ ...form, cvc: value })} inputMode="numeric" autoComplete="cc-csc" required /></div></>}{error && <p className="error-message">{error}</p>}<p className="payment-note">Demo payment only — full card details and CVC are never sent to or stored by Smart EV.</p><button className="primary-button" disabled={busy}>{busy ? "Confirming…" : `Pay €${plan.cost_eur.toFixed(2)} in advance`}<span>→</span></button></form></article>;
}

function PlanView({ token, vehicles, stations, paymentMethod, results, setResults, setError, refreshProfile }) {
  const rankedStations = useMemo(() => [...stations].sort((a, b) => {
    const aUsable = a.operational_status === "online" && a.available_chargers > 0;
    const bUsable = b.operational_status === "online" && b.available_chargers > 0;
    if (aUsable !== bUsable) return bUsable - aUsable;
    if (a.available_chargers !== b.available_chargers) return b.available_chargers - a.available_chargers;
    return b.power_kw - a.power_kw;
  }), [stations]);
  const recommendedStation = rankedStations.find((station) => station.operational_status === "online" && station.available_chargers > 0);
  const [form, setForm] = useState({ vehicleId: vehicles[0]?.id ?? "", stationId: recommendedStation?.id ?? "", currentSoc: 30, targetSoc: 80, departureTime: nextMorning() });
  const [busy, setBusy] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [payment, setPayment] = useState(null);
  const best = useMemo(() => results.length ? [...results].sort((a, b) => a.cost_eur - b.cost_eur)[0] : null, [results]);
  const selectedStation = stations.find((station) => station.id === Number(form.stationId));

  useEffect(() => {
    if (!form.vehicleId && vehicles[0]) setForm((current) => ({ ...current, vehicleId: vehicles[0].id }));
    const currentStation = stations.find((station) => station.id === Number(form.stationId));
    if ((!currentStation || currentStation.operational_status !== "online" || currentStation.available_chargers < 1) && recommendedStation) {
      setForm((current) => ({ ...current, stationId: recommendedStation.id }));
    }
  }, [vehicles, stations, form.vehicleId, form.stationId, recommendedStation]);

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
      const chargingRequest = await api.post("/charging-requests", { vehicle_id: Number(form.vehicleId), station_id: stationId, current_soc: Number(form.currentSoc), target_soc: Number(form.targetSoc), departure_time: form.departureTime }, token);
      const comparison = await Promise.all(["normal", "v1g", "v2g"].map((mode) => api.post(`/optimization/${chargingRequest.id}`, { mode }, token)));
      setResults(comparison);
      await refreshProfile();
    } catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };

  return (
    <section className="view-stack">
      <div className="planner-grid">
        <form className="content-card planner-card" onSubmit={submit}>
          <div className="card-heading"><div><p className="eyebrow">NEW SESSION</p><h3>Charging preferences</h3></div><span className="step-pill">01</span></div>
          <Field label="Vehicle"><select value={form.vehicleId} onChange={(e) => setForm({ ...form, vehicleId: e.target.value })}>{vehicles.length ? vehicles.map((v) => <option key={v.id} value={v.id}>{v.model} · {v.battery_capacity} kWh</option>) : <option value="">No vehicle added</option>}</select></Field>
          <Field label="Charging station"><select value={form.stationId} onChange={(e) => setForm({ ...form, stationId: e.target.value })}>{rankedStations.length ? rankedStations.map((s) => <option key={s.id} value={s.id} disabled={s.operational_status !== "online" || s.available_chargers < 1}>{s.id === recommendedStation?.id ? "Recommended · " : ""}{s.station_name} · {s.city} · {s.available_chargers}/{s.total_chargers} free</option>) : <option value="">No station available</option>}</select></Field>
          {selectedStation && <div className={`station-status ${selectedStation.operational_status === "online" && selectedStation.available_chargers > 0 ? "available" : "unavailable"}`}><i /><div><b>{selectedStation.available_chargers} of {selectedStation.total_chargers} chargers available</b><small>{selectedStation.power_kw} kW · {selectedStation.charger_type} · {selectedStation.availability_source} status</small></div></div>}
          <div className="field-grid"><Field label="Current SoC (%)" type="number" value={form.currentSoc} onChange={(v) => setForm({ ...form, currentSoc: v })} min="0" max="99" /><Field label="Target SoC (%)" type="number" value={form.targetSoc} onChange={(v) => setForm({ ...form, targetSoc: v })} min="1" max="100" /></div>
          <Field label="Ready by" type="datetime-local" value={form.departureTime} onChange={(v) => setForm({ ...form, departureTime: v })} />
          <button className="primary-button" disabled={busy}>{busy ? "Optimizing…" : "Build my smart plan"}<span>→</span></button>
        </form>
        <article className="insight-card"><p className="eyebrow">{results[0]?.forecast_source === "machine_learning" ? "AI FORECAST ACTIVE" : "AUSTRIAN ENERGY DATA"}</p><h3>One target.<br />Three strategies.</h3><p>Smart EV predicts Austrian price, grid pressure and renewable availability for every 15-minute window before departure.</p><div className="formula"><span>55% price</span><span>30% load</span><span>15% renewables</span></div>{results[0] && <small className="model-label">Model: {results[0].model_name}</small>}</article>
      </div>
      {results.length > 0 && <section className="results-block"><div className="card-heading"><div><p className="eyebrow">COMPARISON</p><h3>Choose the smartest outcome</h3></div><span className="step-pill">02</span></div><div className="mode-grid">{results.map((result) => <ModeCard key={result.mode} result={result} recommended={result === best} selected={selectedPlan?.schedule_id === result.schedule_id} onSelect={() => { setSelectedPlan(result); setPayment(null); }} />)}</div>{selectedPlan ? <PaymentPanel key={selectedPlan.schedule_id} plan={selectedPlan} token={token} payment={payment} onPaid={setPayment} savedPaymentMethod={paymentMethod} /> : <p className="choose-prompt">Select one plan above to continue to advance payment.</p>}<article className="timeline-card"><div><p className="eyebrow">RECOMMENDED V2G PLAN</p><h3>Energy activity timeline</h3></div><div className="timeline">{results.find((item) => item.mode === "v2g")?.slots.map((slot) => <div className={`timeline-slot ${slot.action}`} key={`${slot.timestamp}-${slot.action}`} title={`${new Date(slot.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · ${slot.energy_kwh} kWh`} />)}</div><div className="legend"><span><i className="charge" /> Charging</span><span><i className="discharge" /> Grid export</span></div></article></section>}
    </section>
  );
}

function VehiclesView({ token, catalog, vehicles, setVehicles, setError }) {
  const [busy, setBusy] = useState(false);
  const submit = async (form) => {
    setBusy(true); setError("");
    try { const vehicle = await api.post("/vehicles", form, token); setVehicles([...vehicles, vehicle]); }
    catch (requestError) { setError(requestError.message); } finally { setBusy(false); }
  };
  return <section className="view-stack"><div className="split-grid vehicles-layout"><article className="content-card"><div className="card-heading"><div><p className="eyebrow">MY GARAGE</p><h3>Connected vehicles</h3></div><span className="count-pill">{vehicles.length}</span></div>{vehicles.length ? vehicles.map((vehicle) => <VehicleRow key={vehicle.id} vehicle={vehicle} />) : <EmptyCopy text="Your garage is empty." />}</article><article className="content-card"><div className="card-heading"><div><p className="eyebrow">ADD VEHICLE</p><h3>Connect another EV</h3></div></div><VehicleForm catalog={catalog} onSubmit={submit} busy={busy} buttonLabel="Add to my garage" /></article></div></section>;
}

function RewardsView({ user, rewards }) {
  return <section className="view-stack"><article className="rewards-hero"><div><p className="eyebrow">SMART EV WALLET</p><h2>€{user.wallet_balance.toFixed(2)}</h2><p>Earned by returning clean, flexible energy to the grid.</p></div><div className="points-orbit"><strong>{user.reward_points}</strong><span>points</span></div></article><article className="content-card"><div className="card-heading"><div><p className="eyebrow">ACTIVITY</p><h3>Reward history</h3></div></div>{rewards.length ? rewards.map((reward) => <RewardRow key={reward.id} reward={reward} />) : <EmptyCopy text="Complete a V2G plan to earn your first reward." />}</article></section>;
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
