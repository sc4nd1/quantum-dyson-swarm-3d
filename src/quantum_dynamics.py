import numpy as np
import qutip as qt

def _op_at(op, idx, N):
    ops = [qt.qeye(2) for _ in range(N)]
    ops[idx] = op
    return qt.tensor(ops)

def simulate_dicke_harvesting(n_qubits=5, t_max=40.0, steps=250):
    """Simula il guadagno energetico superradiante (Dicke ~ N^2) vs Classico (~ N)."""
    omega_sun = 2 * np.pi * 0.06
    j_link = 2 * np.pi * 0.04
    gamma_loss = 0.03

    sm = [_op_at(qt.destroy(2), i, n_qubits) for i in range(n_qubits)]
    sx = [_op_at(qt.sigmax(), i, n_qubits) for i in range(n_qubits)]
    num_ops = [sm[i].dag() * sm[i] for i in range(n_qubits)]

    j_minus = sum(sm)
    total_coherent_op = j_minus.dag() * j_minus
    classical_sum_op = sum(num_ops)

    H = 0.5 * omega_sun * sum(sx)
    for i in range(n_qubits):
        for j in range(i + 1, n_qubits):
            H += j_link * (sm[i].dag() * sm[j] + sm[i] * sm[j].dag())

    c_ops = [np.sqrt(gamma_loss) * sm[i] for i in range(n_qubits)]
    psi0 = qt.tensor([qt.basis(2, 0) for _ in range(n_qubits)])
    tlist = np.linspace(0, t_max, steps)

    res = qt.mesolve(H, psi0, tlist, c_ops=c_ops, e_ops=[total_coherent_op, classical_sum_op])
    return tlist, res.expect[0], res.expect[1]