import numpy as np
import networkx as nx

# Costanti astrofisiche (scala basata sul raggio del Sole R_SUN = 3.2 unità = 696,340 km)
R_SUN_KM = 696340.0
SIM_R_SUN = 3.2
UNIT_TO_KM = R_SUN_KM / SIM_R_SUN        # ~217,606 km per unità di simulazione
C_LIGHT_KM_S = 299792.458                # Velocità della luce nel vuoto (km/s)
SWAP_OVERHEAD_S = 1.8                    # Overhead di sincronizzazione e BSM per repeater (s)

def generate_walker_swarm(n_rings=4, sats_per_ring=9, r_orbit=10.0, seed=42):
    """Genera le posizioni 3D di uno sciame di Dyson su anelli orbitali inclinati."""
    np.random.seed(seed)
    positions, ring_ids = [], []

    for r_idx in range(n_rings):
        inc = np.deg2rad(25 + r_idx * 35)
        raan = np.deg2rad(r_idx * (180.0 / n_rings))

        for s_idx in range(sats_per_ring):
            phase = 2 * np.pi * s_idx / sats_per_ring + (r_idx * 0.3)
            x_orb, y_orb = r_orbit * np.cos(phase), r_orbit * np.sin(phase)

            y1, z1 = y_orb * np.cos(inc), y_orb * np.sin(inc)
            x_final = x_orb * np.cos(raan) - y1 * np.sin(raan)
            y_final = x_orb * np.sin(raan) + y1 * np.cos(raan)

            positions.append([x_final, y_final, z1])
            ring_ids.append(r_idx)

    return np.array(positions), np.array(ring_ids)

def _segment_sun_distance(p1, p2):
    """Distanza minima tra il raggio laser (p1->p2) e il centro del Sole (0,0,0)."""
    v = p2 - p1
    t = np.clip(-np.dot(p1, v) / (np.dot(v, v) + 1e-12), 0.0, 1.0)
    closest_pt = p1 + t * v
    return np.linalg.norm(closest_pt)

def link_latency_seconds(dist_units):
    """Converte la distanza adimensionale nel ritardo relativistico di propagazione d/c (s)."""
    dist_km = dist_units * UNIT_TO_KM
    return float(dist_km / C_LIGHT_KM_S)

def build_entanglement_graph(positions, r_sun=3.2, max_dist=8.8, t2_memory_s=60.0):
    """Crea il grafo dei link laser includendo l'attenuazione ottica e il costo di decoerenza T2."""
    G = nx.Graph()
    n_total = len(positions)
    for i in range(n_total):
        G.add_node(i, pos=positions[i])

    for i in range(n_total):
        for j in range(i + 1, n_total):
            dist = float(np.linalg.norm(positions[i] - positions[j]))
            if dist < max_dist and _segment_sun_distance(positions[i], positions[j]) > r_sun:
                fidelity = float(np.exp(-((dist - 2.5) / 6.5) ** 2))
                w_link = max((4.0 * fidelity - 1.0) / 3.0, 1e-4)

                # Latenza relativistica della luce + tempo di attesa per Entanglement Swapping
                dt_light = link_latency_seconds(dist)
                dt_step = dt_light + SWAP_OVERHEAD_S
                memory_decay = float(np.exp(-dt_step / max(t2_memory_s, 1e-3)))

                # Costo composito di Dijkstra: infedeltà canale + decoerenza memoria T2
                cost = -np.log(w_link) + (dt_step / max(t2_memory_s, 1e-3))
                G.add_edge(
                    i, j,
                    fidelity=fidelity,
                    w_link=w_link,
                    latency_s=dt_light,
                    memory_decay=memory_decay,
                    cost=cost,
                    dist=dist,
                )
    return G

def find_antipodal_quantum_route(G, positions, source_node=0, t2_memory_s=60.0):
    """Trova il percorso ottimo verso gli antipodi considerando la decoerenza T2."""
    dists = np.linalg.norm(positions - positions[source_node], axis=1)
    target_node = int(np.argmax(dists))
    path = nx.shortest_path(G, source=source_node, target=target_node, weight="cost")

    n_hops = len(path) - 1
    total_light_s = sum(G[path[k]][path[k+1]]["latency_s"] for k in range(n_hops))
    total_wait_s = total_light_s + max(0, n_hops - 1) * SWAP_OVERHEAD_S

    w_optical = np.prod([G[path[k]][path[k+1]]["w_link"] for k in range(n_hops)])
    w_final = w_optical * np.exp(-total_wait_s / max(t2_memory_s, 1e-3))
    e2e_fidelity = float((1.0 + 3.0 * w_final) / 4.0)

    return path, target_node, e2e_fidelity