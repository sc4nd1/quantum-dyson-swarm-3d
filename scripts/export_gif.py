import os
import sys
import matplotlib
matplotlib.use("Agg")
from matplotlib.animation import FuncAnimation, PillowWriter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import scripts.run_realtime_flare as sim

def export_animation():
    os.makedirs("figures", exist_ok=True)
    out_path = "figures/live_dyson_swarm.gif"
    print("🎬 Generazione GIF 3D in corso (90 frames con X-Class Flare e decoerenza T2)...")

    sim.history_frames.clear()
    sim.history_raw.clear()
    sim.history_pur.clear()
    sim.history_ideal.clear()
    sim.evasion_offset[:] = 0.0
    sim.evasion_vel[:] = 0.0

    def wrapped_update(frame):
        if frame == 20:
            sim.flare_sim.trigger_superflare()
        return sim.update(frame)

    ani = FuncAnimation(sim.fig, wrapped_update, frames=90, interval=55)
    ani.save(out_path, writer=PillowWriter(fps=16), dpi=100)
    print(f"GIF salvata con successo in: {out_path}")

if __name__ == "__main__":
    export_animation()