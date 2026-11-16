import os
import sys
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.orbital_swarm import _segment_sun_distance

# --- 1. PARAMETRI ORBITALI E FISICA DINAMICA CON MANOVRA EVASIVA ---
N_RINGS = 4
SATS_PER_RING = 9
N_TOTAL = N_RINGS * SATS_PER_RING
R_ORBIT = 10.5
R_SUN = 3.3

np.random.seed(42)
inc_list, raan_list, phase_0, omega_list, ring_ids = [], [], [], [], []

for r_idx in range(N_RINGS):
    inc = np.deg2rad(25 + r_idx * 36)
    raan = np.deg2rad(r_idx * (180.0 / N_RINGS))
    omega = 0.032 * (1.0 + 0.14 * ((-1) ** r_idx))
    for s_idx in range(SATS_PER_RING):
        inc_list.append(inc)
        raan_list.append(raan)
        phase_0.append(2 * np.pi * s_idx / SATS_PER_RING + r_idx * 0.4)
        omega_list.append(omega)
        ring_ids.append(r_idx)

inc_list = np.array(inc_list)
raan_list = np.array(raan_list)
phase_0 = np.array(phase_0)
omega_list = np.array(omega_list)
ring_ids = np.array(ring_ids)

# Stato dinamico per le manovre evasive 3D dei satelliti (spostamento e velocità extra)
evasion_offset = np.zeros((N_TOTAL, 3))
evasion_vel = np.zeros((N_TOTAL, 3))

def get_nominal_positions(frame):
    """Calcola l'orbita kepleriana ideale senza perturbazioni."""
    phases = phase_0 + omega_list * frame
    x_orb = R_ORBIT * np.cos(phases)
    y_orb = R_ORBIT * np.sin(phases)

    y1 = y_orb * np.cos(inc_list)
    z1 = y_orb * np.sin(inc_list)
    x_final = x_orb * np.cos(raan_list) - y1 * np.sin(raan_list)
    y_final = x_orb * np.sin(raan_list) + y1 * np.cos(raan_list)
    return np.column_stack([x_final, y_final, z1])

# --- 2. PROTOCOLLO DI PURIFICAZIONE QUANTISTICA (BBPSSW / WERNER STATES) ---
def purify_fidelity(F):
    """Distillazione di entanglement BBPSSW: sacrifica 2 coppie rumorose per 1 ad alta fedeltà."""
    if F <= 0.5:
        return F
    num = F**2 + ((1.0 - F) / 3.0) ** 2
    den = F**2 + (2.0 / 3.0) * F * (1.0 - F) + 5.0 * ((1.0 - F) / 3.0) ** 2
    return float(num / den)

def werner_swap_e2e(fidelities, use_purification=True):
    """Calcola la fedeltà reale di Entanglement Swapping su catena di stati di Werner."""
    if not fidelities:
        return 0.0
    links = [purify_fidelity(purify_fidelity(f)) if use_purification else f for f in fidelities]
    # Conversione Fedeltà -> Parametro di Werner W = (4F - 1)/3
    w_prod = np.prod([(4.0 * max(f, 0.25) - 1.0) / 3.0 for f in links])
    return float((1.0 + 3.0 * w_prod) / 4.0)

# --- 3. GESTORE BRILLAMENTI SOLARI E SUPER-FLARE ON-DEMAND ---
class SolarFlareManager:
    def __init__(self):
        self.dirs = [
            np.array([0.85, 0.45, 0.25]),
            np.array([-0.6, 0.75, -0.3]),
        ]
        self.dirs = [d / np.linalg.norm(d) for d in self.dirs]
        self.superflare_boost = 0.0

    def trigger_superflare(self, event=None):
        """Attiva una tempesta solare estrema di classe X!"""
        self.superflare_boost = 2.4
        print("☀️ [ALERT] X-Class Super-Flare Erupted! Satellites initiating evasive maneuvers...")

    def get_active_flares(self, frame):
        self.superflare_boost *= 0.94  # Decadimento graduale del superflare
        flare_clouds, hazard_zones = [], []

        for idx, d in enumerate(self.dirs):
            cycle = ((frame + idx * 35) % 70) / 70.0
            r_front = R_SUN + cycle * (9.8 + 2.5 * self.superflare_boost)
            intensity = np.sin(cycle * np.pi) * (1.0 + self.superflare_boost)

            rot_angle = 0.014 * frame
            c, s = np.cos(rot_angle), np.sin(rot_angle)
            curr_dir = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]) @ d

            center_cme = curr_dir * r_front
            radius_cme = 3.4 + 1.2 * self.superflare_boost
            hazard_zones.append((center_cme, intensity, radius_cme, curr_dir))

            n_pts = int(100 + 60 * self.superflare_boost)
            t_stream = np.linspace(R_SUN, r_front, n_pts)
            spread = (0.18 + 0.08 * self.superflare_boost) * (t_stream - R_SUN)
            noise = np.random.normal(0, 1.0, (n_pts, 3)) * spread[:, None]
            pts = np.outer(t_stream, curr_dir) + noise
            flare_clouds.append((pts, min(intensity, 1.5)))

        return flare_clouds, hazard_zones

flare_sim = SolarFlareManager()
state = {"purification": True}

def update_satellite_evasion(nom_pos, hazard_zones):
    """Propulsione a vela solare: i satelliti scartano fisicamente dal cono del brillamento!"""
    global evasion_offset, evasion_vel
    # Forza di richiamo PD verso l'orbita nominale (Station-Keeping)
    force = -0.12 * evasion_offset - 0.30 * evasion_vel
    evading_mask = np.zeros(N_TOTAL, dtype=bool)

    current_pos = nom_pos + evasion_offset
    for c_cme, intensity, radius, flare_dir in hazard_zones:
        if intensity > 0.15:
            diff = current_pos - c_cme
            dists = np.linalg.norm(diff, axis=1)
            in_danger = dists < (radius + 1.8)
            evading_mask |= in_danger

            for i in np.where(in_danger)[0]:
                # Spinta laterale + radiale con la vela solare per uscire dal cono di plasma
                escape_dir = diff[i] / (dists[i] + 1e-6)
                force[i] += escape_dir * (0.65 * intensity * (radius + 1.8 - dists[i]))

    evasion_vel += force
    evasion_offset += evasion_vel
    return nom_pos + evasion_offset, evading_mask

def build_dynamic_quantum_graph(positions, hazard_zones):
    G = nx.Graph()
    for i in range(N_TOTAL):
        G.add_node(i)

    for i in range(N_TOTAL):
        for j in range(i + 1, N_TOTAL):
            p1, p2 = positions[i], positions[j]
            dist = np.linalg.norm(p1 - p2)
            if dist < 9.5 and _segment_sun_distance(p1, p2) > R_SUN:
                fid = float(np.exp(-((dist - 2.2) / 7.5) ** 2))
                mid = 0.5 * (p1 + p2)
                flare_hit = False

                for c_cme, intensity, radius, _ in hazard_zones:
                    d_flare = np.linalg.norm(mid - c_cme)
                    if d_flare < radius and intensity > 0.2:
                        attenuation = np.exp(-3.2 * intensity * ((radius - d_flare) / radius))
                        fid *= attenuation
                        flare_hit = True

                fid = max(fid, 0.26)
                eff_fid = purify_fidelity(purify_fidelity(fid)) if state["purification"] else fid
                cost = -np.log(max(eff_fid, 1e-6))
                G.add_edge(i, j, raw_fid=fid, eff_fid=eff_fid, cost=cost, hit=flare_hit)
    return G

# --- 4. INTERFACCIA GRAFICA 3D + BOTTONI DI CONTROLLO MISSIONE ---
fig = plt.figure(figsize=(14.5, 7.5), facecolor="#070a12")
plt.subplots_adjust(bottom=0.14)
ax = fig.add_subplot(121, projection="3d")
ax2 = fig.add_subplot(122, facecolor="#0e1320")

# Bottoni interattivi nella dashboard
ax_btn_flare = plt.axes([0.15, 0.03, 0.22, 0.055])
btn_flare = Button(ax_btn_flare, "☀️ TRIGGER X-CLASS FLARE", color="#ff0055", hovercolor="#ff4d6d")
btn_flare.label.set_color("white")
btn_flare.label.set_fontweight("bold")
btn_flare.on_clicked(flare_sim.trigger_superflare)

ax_btn_pur = plt.axes([0.42, 0.03, 0.24, 0.055])
btn_pur = Button(ax_btn_pur, "🛡️ PURIFICATION: ON (BBPSSW)", color="#00bbf9", hovercolor="#00f5d4")
btn_pur.label.set_color("#070a12")
btn_pur.label.set_fontweight("bold")

def toggle_purification(event):
    state["purification"] = not state["purification"]
    if state["purification"]:
        btn_pur.label.set_text("🛡️ PURIFICATION: ON (BBPSSW)")
        btn_pur.color = "#00bbf9"
    else:
        btn_pur.label.set_text("⚠️ PURIFICATION: OFF (RAW)")
        btn_pur.color = "#6c757d"

btn_pur.on_clicked(toggle_purification)

u, v = np.mgrid[0:2*np.pi:36j, 0:np.pi:20j]
x_s0, y_s0, z_s0 = np.cos(u) * np.sin(v), np.sin(u) * np.sin(v), np.cos(v)
history_frames, history_raw, history_pur = [], [], []

def update(frame):
    ax.cla()
    ax.set_facecolor("#070a12")

    # 1. Sole e brillamenti
    flare_clouds, hazard_zones = flare_sim.get_active_flares(frame)
    pert = 1.0 + (0.04 + 0.03 * flare_sim.superflare_boost) * np.sin(6*u + 0.25*frame) * np.sin(5*v - 0.2*frame)
    ax.plot_surface(R_SUN * pert * x_s0, R_SUN * pert * y_s0, R_SUN * pert * z_s0,
                    cmap="afmhot", alpha=0.92, edgecolor="orangered", lw=0.15)

    for pts, intensity in flare_clouds:
        if intensity > 0.05:
            ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2],
                       c=np.linspace(1.0, 0.1, len(pts)), cmap="autumn",
                       s=20 * intensity, alpha=min(0.85, 0.6 * intensity))

    # 2. Posizioni satelliti con manovra evasiva
    nom_pos = get_nominal_positions(frame)
    positions, evading_mask = update_satellite_evasion(nom_pos, hazard_zones)

    # Disegna i vettori di spinta evasiva per i satelliti che stanno schivando il plasma
    for i in np.where(evading_mask)[0]:
        ax.plot([nom_pos[i, 0], positions[i, 0]],
                [nom_pos[i, 1], positions[i, 1]],
                [nom_pos[i, 2], positions[i, 2]], color="yellow", lw=1.8, alpha=0.9)

    # 3. Grafo e Routing Quantistico
    G = build_dynamic_quantum_graph(positions, hazard_zones)
    source_node = 0
    target_node = int(np.argmax(np.linalg.norm(positions - positions[source_node], axis=1)))

    for i, j, data in G.edges(data=True):
        p1, p2 = positions[i], positions[j]
        if data["hit"]:
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                    color="orange", linestyle=":", alpha=0.55, lw=1.1)
        else:
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                    color="#00f5d4", alpha=0.12 + 0.30 * data["eff_fid"], lw=0.7)

    raw_e2e, pur_e2e = 0.0, 0.0
    if nx.has_path(G, source_node, target_node):
        path = nx.shortest_path(G, source=source_node, target=target_node, weight="cost")
        raw_links = [G[path[k]][path[k+1]]["raw_fid"] for k in range(len(path)-1)]
        raw_e2e = werner_swap_e2e(raw_links, use_purification=False)
        pur_e2e = werner_swap_e2e(raw_links, use_purification=True)

        for k in range(len(path) - 1):
            p1, p2 = positions[path[k]], positions[path[k+1]]
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                    color="#ff0055", lw=3.4, zorder=15)

    # 4. Satelliti (Quelli in manovra evasiva lampeggiano in giallo/arancio!)
    ring_colors = ["#00f5d4", "#fee440", "#9b5de5", "#3a86ff"]
    for r_idx in range(N_RINGS):
        mask = (ring_ids == r_idx) & (~evading_mask)
        ax.scatter(positions[mask, 0], positions[mask, 1], positions[mask, 2],
                   s=46, color=ring_colors[r_idx], edgecolors="white", lw=0.7)

    if np.any(evading_mask):
        ax.scatter(positions[evading_mask, 0], positions[evading_mask, 1], positions[evading_mask, 2],
                   s=75, color="#ffbe0b", edgecolors="red", lw=1.5, marker="D")

    ax.scatter(*positions[source_node], s=130, color="lime", edgecolors="black", marker="^", zorder=20)
    ax.scatter(*positions[target_node], s=130, color="#ff0055", edgecolors="white", marker="*", zorder=20)

    ax.set_xlim(-12.5, 12.5)
    ax.set_ylim(-12.5, 12.5)
    ax.set_zlim(-10.5, 10.5)
    ax.set_axis_off()
    n_evade = int(np.sum(evading_mask))
    ax.set_title(
        f"3D Quantum Dyson Swarm | Evading Satellites: {n_evade}\n"
        f"Swapped Fidelity: {pur_e2e*100:.1f}% (Purified) vs {raw_e2e*100:.1f}% (Raw)",
        color="white", fontsize=10.5, pad=8
    )

    # 5. Telemetria Dual-Trace (Purified vs Raw Unpurified)
    history_frames.append(frame)
    history_raw.append(raw_e2e * 100.0)
    history_pur.append(pur_e2e * 100.0)
    if len(history_frames) > 80:
        history_frames.pop(0)
        history_raw.pop(0)
        history_pur.pop(0)

    ax2.cla()
    ax2.set_facecolor("#0e1320")
    ax2.plot(history_frames, history_pur, color="#00f5d4", lw=2.4, label="BBPSSW Purified + Swapped Fidelity (%)")
    ax2.plot(history_frames, history_raw, color="#ff0055", lw=1.8, linestyle="--", label="Raw Unpurified Swapping (%)")
    ax2.fill_between(history_frames, history_raw, history_pur, color="#00f5d4", alpha=0.18, label="Quantum Distillation Gain")
    ax2.axhline(50.0, color="gold", linestyle=":", lw=1.2, label="Quantum Bell Threshold (50%)")
    ax2.set_ylim(20, 102)
    ax2.set_title("Live Quantum Repeater Telemetry (Werner State Distillation)", color="white", fontsize=11)
    ax2.set_xlabel("Time Step", color="lightgray")
    ax2.set_ylabel("End-to-End State Fidelity (%)", color="lightgray")
    ax2.tick_params(colors="lightgray")
    ax2.grid(True, color="#252f42", alpha=0.5)
    ax2.legend(loc="lower left", facecolor="#161d2f", labelcolor="white", fontsize=8.5)

ani = FuncAnimation(fig, update, frames=500, interval=50, repeat=True)
plt.show()