import os
import sys
import numpy as np
import matplotlib.pyplot as plt

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.orbital_swarm import generate_walker_swarm, build_entanglement_graph, find_antipodal_quantum_route
from src.quantum_dynamics import simulate_dicke_harvesting

def main():
    r_sun = 3.2
    positions, ring_ids = generate_walker_swarm(n_rings=4, sats_per_ring=9, r_orbit=10.0)
    G = build_entanglement_graph(positions, r_sun=r_sun, max_dist=8.8)
    route_path, target_id, e2e_fid = find_antipodal_quantum_route(G, positions, source_node=0)

    print(f"=== QUANTUM DYSON SWARM ROUTING ===")
    print(f"Percorso Entanglement Swapping (Sat 0 -> Sat {target_id}): {route_path}")
    print(f"Fedeltà End-to-End stimata: {e2e_fid*100:.2f} %")

    tlist, p_entangled, p_classical = simulate_dicke_harvesting(n_qubits=5)

    fig = plt.figure(figsize=(13, 6.5))
    ax = fig.add_subplot(121, projection="3d")
    ax.set_facecolor("#0b0f19")

    u, v = np.mgrid[0:2*np.pi:30j, 0:np.pi:20j]
    ax.plot_surface(r_sun * np.cos(u) * np.sin(v),
                    r_sun * np.sin(u) * np.sin(v),
                    r_sun * np.cos(v), color="gold", alpha=0.85, edgecolor="darkorange", lw=0.3)

    for i, j, data in G.edges(data=True):
        p1, p2 = positions[i], positions[j]
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                color="cyan", alpha=0.18 + 0.45 * data["fidelity"], lw=0.8)

    for k in range(len(route_path) - 1):
        p1, p2 = positions[route_path[k]], positions[route_path[k+1]]
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                color="#ff0055", lw=3.2, zorder=10,
                label="Dijkstra Quantum Route" if k == 0 else "")

    colors = ["#00f5d4", "#fee440", "#9b5de5", "#00bbf9"]
    for r_idx in range(4):
        mask = ring_ids == r_idx
        ax.scatter(positions[mask, 0], positions[mask, 1], positions[mask, 2],
                   s=55, color=colors[r_idx], edgecolors="white", lw=0.8, label=f"Ring {r_idx+1}")

    ax.set_title(f"3D Quantum Dyson Swarm & Entanglement Routing\nRoute: {route_path} (Fidelity: {e2e_fid:.2f})")
    ax.legend(loc="upper left", fontsize=8)

    ax2 = fig.add_subplot(122)
    ax2.plot(tlist, p_entangled, color="#ff0055", lw=2.5, label="Entangled Cluster (Dicke Superabsorption ~ N²)")
    ax2.plot(tlist, p_classical, color="royalblue", lw=2, linestyle="--", label="Independent Satellites (~ N)")
    ax2.fill_between(tlist, p_classical, p_entangled, color="#ff0055", alpha=0.15, label="Quantum Advantage")
    ax2.set_title("Coherent Energy Harvesting Dynamics (QuTiP Lindblad Solver)")
    ax2.set_xlabel("Time (scaled units)")
    ax2.set_ylabel(r"Collective Intensity $\langle J_+ J_- \rangle$")
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper left")

    plt.tight_layout()
    os.makedirs("figures", exist_ok=True)
    plt.savefig("figures/dyson_swarm_simulation.png", dpi=300)
    print("Grafico salvato in figures/dyson_swarm_simulation.png!")
    plt.show()

if __name__ == "__main__":
    main()