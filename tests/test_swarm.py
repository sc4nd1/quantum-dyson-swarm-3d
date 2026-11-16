import os
import sys
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.orbital_swarm import (
    generate_walker_swarm,
    build_entanglement_graph,
    find_antipodal_quantum_route,
    _segment_sun_distance,
)
from src.quantum_dynamics import simulate_dicke_harvesting

def test_no_solar_occultation():
    """Verifica che nessun link laser nel grafo attraversi il Sole."""
    r_sun = 3.2
    positions, _ = generate_walker_swarm(n_rings=4, sats_per_ring=9)
    G = build_entanglement_graph(positions, r_sun=r_sun, max_dist=8.8)

    assert G.number_of_edges() > 0, "Il grafo non contiene link laser!"
    for u, v in G.edges():
        dist_from_sun = _segment_sun_distance(positions[u], positions[v])
        assert dist_from_sun > r_sun, f"Il link ({u}, {v}) attraversa il Sole!"

def test_quantum_routing_validity():
    """Verifica che l'algoritmo di Dijkstra trovi un percorso valido con fedeltà in (0, 1]."""
    positions, _ = generate_walker_swarm()
    G = build_entanglement_graph(positions)
    path, target, fid = find_antipodal_quantum_route(G, positions, source_node=0)

    assert path[0] == 0 and path[-1] == target
    assert len(path) >= 2
    assert 0.0 < fid <= 1.0

def test_t2_memory_decoherence_penalty():
    """Verifica che la latenza della luce d/c e un T2 corto degradino la fedeltà end-to-end."""
    positions, _ = generate_walker_swarm()
    G_short_t2 = build_entanglement_graph(positions, t2_memory_s=10.0)
    G_long_t2 = build_entanglement_graph(positions, t2_memory_s=500.0)

    _, _, fid_short = find_antipodal_quantum_route(G_short_t2, positions, t2_memory_s=10.0)
    _, _, fid_long = find_antipodal_quantum_route(G_long_t2, positions, t2_memory_s=500.0)

    assert fid_long > fid_short, "Una memoria quantistica con T2 più alto deve dare una fedeltà maggiore!"

def test_dicke_quantum_advantage():
    """Verifica che il picco superradiante (Dicke) superi la raccolta classica."""
    _, p_entangled, p_classical = simulate_dicke_harvesting(n_qubits=4, t_max=30.0, steps=100)
    assert np.max(p_entangled) > np.max(p_classical), "Manca il vantaggio quantistico superradiante!"

if __name__ == "__main__":
    test_no_solar_occultation()
    test_quantum_routing_validity()
    test_t2_memory_decoherence_penalty()
    test_dicke_quantum_advantage()
    print("✅ Tutti i 4 test fisici, relativistici e geometrici sono passati!")