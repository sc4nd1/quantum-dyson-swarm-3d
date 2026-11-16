import numpy as np
import networkx as nx

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

            # Rotazioni 3D (Inclinazione + Nodo Ascendente)
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

def build_entanglement_graph(positions, r_sun=3.2, max_dist=8.8):
    """Crea il grafo dei link laser e calcola la fedeltà dell'entanglement."""
    G = nx.Graph()
    n_total = len(positions)
    for i in range(n_total):
        G.add_node(i, pos=positions[i])

    for i in range(n_total):
        for j in range(i + 1, n_total):
            dist = np.linalg.norm(positions[i] - positions[j])
            if dist < max_dist and _segment_sun_distance(positions[i], positions[j]) > r_sun:
                fidelity = float(np.exp(-((dist - 2.5) / 6.5) ** 2))
                # Costo di Dijkstra: -log(fidelity) massimizza il prodotto delle fedeltà!
                cost = -np.log(max(fidelity, 1e-6))
                G.add_edge(i, j, fidelity=fidelity, cost=cost, dist=dist)
    return G

def find_antipodal_quantum_route(G, positions, source_node=0):
    """Trova il percorso ottimo di Entanglement Swapping verso il satellite più lontano."""
    dists = np.linalg.norm(positions - positions[source_node], axis=1)
    target_node = int(np.argmax(dists))
    path = nx.shortest_path(G, source=source_node, target=target_node, weight="cost")
    
    # Fedeltà end-to-end lungo la catena di repeater
    e2e_fidelity = np.prod([G[path[k]][path[k+1]]["fidelity"] for k in range(len(path)-1)])
    return path, target_node, e2e_fidelity