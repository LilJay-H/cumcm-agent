import json, os, itertools
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

np.random.seed(42)

# === Scenario parameters (to be calibrated with real data) ===
CAREERS = ["Software Developer", "Electrician", "Graphic Designer"]
DIMS = ["Cognitive", "Social", "Physical", "Creative"]
TASK_VECTORS = np.array([[0.50,0.15,0.05,0.30],[0.15,0.20,0.60,0.05],[0.20,0.15,0.05,0.60]])
SCENARIOS = ["conservative", "base", "aggressive"]
YEARS = np.arange(2026, 2037)
T0 = 2026
TOTAL_CREDITS = 120
COURSE_NAMES = ["Core","AI_Tools","AI_Principles","Ethics_Humanities","Practicum","Cross_Domain"]

# Logistic params per scenario: L, r, t0 for each dim
LOGISTIC = {
    "conservative": {"L":[0.60,0.25,0.05,0.40],"r":[0.20,0.15,0.10,0.25],"t0":[2027,2029,2032,2027]},
    "base":         {"L":[0.75,0.40,0.10,0.60],"r":[0.35,0.25,0.15,0.40],"t0":[2026,2028,2030,2026]},
    "aggressive":   {"L":[0.90,0.55,0.20,0.80],"r":[0.50,0.35,0.25,0.55],"t0":[2025,2027,2028,2025]},
}
# Substitution elasticity sigma_ij (career x dim)
SIGMA = np.array([[0.60,0.20,0.05,0.40],[0.15,0.15,0.03,0.05],[0.35,0.20,0.05,0.70]])
# Augmentation elasticity eta_ij
ETA = np.array([[0.50,0.30,0.10,0.35],[0.20,0.25,0.40,0.10],[0.30,0.25,0.10,0.50]])
# Employment elasticity
LAMBDA_SUB, MU_AUG = 1.0, 0.8
# Base growth (no-AI counterfactual annual rate)
G_BASE = [0.015, 0.008, 0.003]

# Contribution matrices per career (6 courses x 4 dims)
CONTRIB = {
    0: np.array([[0.45,0.10,0.05,0.30],[0.35,0.05,0.00,0.15],[0.55,0.05,0.00,0.10],
                 [0.10,0.40,0.00,0.10],[0.15,0.15,0.10,0.15],[0.10,0.35,0.00,0.20]]),
    1: np.array([[0.20,0.10,0.55,0.05],[0.25,0.05,0.10,0.05],[0.30,0.05,0.05,0.05],
                 [0.10,0.35,0.05,0.10],[0.10,0.10,0.60,0.10],[0.15,0.30,0.10,0.15]]),
    2: np.array([[0.15,0.10,0.05,0.60],[0.25,0.05,0.00,0.30],[0.40,0.05,0.00,0.15],
                 [0.10,0.35,0.00,0.20],[0.10,0.20,0.05,0.45],[0.15,0.30,0.00,0.30]]),
}
# Min credit fractions per course
ALPHA_MIN = np.array([0.25, 0.05, 0.03, 0.05, 0.10, 0.05])

def logistic_capability(t, L, r, t0):
    return L / (1.0 + np.exp(-r * (t - t0)))

def compute_capabilities(scenario):
    p = LOGISTIC[scenario]
    C = np.zeros((len(YEARS), 4))
    for j in range(4):
        C[:, j] = logistic_capability(YEARS, p["L"][j], p["r"][j], p["t0"][j])
    return C

def compute_rates(C, career_idx):
    tau = TASK_VECTORS[career_idx]
    sigma = SIGMA[career_idx]
    eta = ETA[career_idx]
    R = np.array([np.sum(tau * sigma * C[t]) for t in range(len(YEARS))])
    A = np.array([np.sum(tau * eta * C[t] * (1 - sigma * C[t])) for t in range(len(YEARS))])
    R = np.clip(R, 0, 1)
    A = np.clip(A, 0, 1)
    return R, A

def compute_employment_index(R, A, g_base):
    idx = np.ones(len(YEARS)) * 100.0
    for t in range(1, len(YEARS)):
        dR = R[t] - R[t-1]
        dA = A[t] - A[t-1]
        growth = g_base - LAMBDA_SUB * dR + MU_AUG * dA
        idx[t] = idx[t-1] * (1 + growth)
    idx = np.maximum(idx, 1.0)
    return idx

def no_ai_counterfactual(g_base):
    idx = np.ones(len(YEARS)) * 100.0
    for t in range(1, len(YEARS)):
        idx[t] = idx[t-1] * (1 + g_base)
    return idx

# === Curriculum optimization via grid search ===
def grid_search_curriculum(career_idx, C_base, weights=(1.0, 0.0, 0.0)):
    w_emp, w_eq, w_res = weights
    tau = TASK_VECTORS[career_idx]
    S = CONTRIB[career_idx]
    R_base, A_base = compute_rates(C_base, career_idx)
    task_value = tau * (1 - R_base[-1] + A_base[-1])
    emp_scores = S @ task_value
    # Equity: practicum+cross benefit low-income more
    eq_weights = np.array([0.0, -0.1, -0.15, 0.1, 0.2, 0.15])
    # Resilience: min across scenarios
    res_scores = []
    for sc in SCENARIOS:
        Cs = compute_capabilities(sc)
        Rs, As = compute_rates(Cs, career_idx)
        tv = tau * (1 - Rs[-1] + As[-1])
        res_scores.append(S @ tv)
    res_min = np.minimum(np.minimum(res_scores[0], res_scores[1]), res_scores[2])

    best_score, best_alpha = -np.inf, None
    step = 0.05
    slots = 6
    budget = int(round(1.0 / step))
    # Efficient: random sample from feasible space
    n_samples = 8000
    for _ in range(n_samples):
        raw = np.random.dirichlet(np.ones(slots))
        alpha = np.maximum(raw, ALPHA_MIN)
        alpha /= alpha.sum()
        if np.any(alpha < ALPHA_MIN - 1e-9):
            continue
        score = w_emp * np.dot(alpha, emp_scores) + w_eq * np.dot(alpha, eq_weights) + w_res * np.dot(alpha, res_min)
        if score > best_score:
            best_score, best_alpha = score, alpha.copy()
    credits = np.round(best_alpha * TOTAL_CREDITS).astype(int)
    diff = TOTAL_CREDITS - credits.sum()
    credits[0] += diff
    return credits, best_alpha, best_score

# === Main computation ===
results = {"metadata":{"model":"TED-compact","base_year":T0,"index_base":100,
           "note":"Employment demand INDEX (2026=100), not headcount predictions"},
           "parameters":{"task_vectors":{c:TASK_VECTORS[i].tolist() for i,c in enumerate(CAREERS)},
                         "scenarios":SCENARIOS,"sigma":SIGMA.tolist(),"eta":ETA.tolist()}}

career_outlook = {}
capacity_decisions = {}
all_indices = {}

for i, career in enumerate(CAREERS):
    career_outlook[career] = {}
    capacity_decisions[career] = {}
    all_indices[career] = {}
    for sc in SCENARIOS:
        C = compute_capabilities(sc)
        R, A = compute_rates(C, i)
        idx = compute_employment_index(R, A, G_BASE[i])
        cf = no_ai_counterfactual(G_BASE[i])
        all_indices[career][sc] = idx
        yr10_idx = idx[-1]
        advice = "expand" if yr10_idx > 105 else ("shrink" if yr10_idx < 95 else "stable")
        career_outlook[career][sc] = {"index":{int(y):round(float(v),2) for y,v in zip(YEARS,idx)},
            "counterfactual":{int(y):round(float(v),2) for y,v in zip(YEARS,cf)},
            "substitution_rate":{int(y):round(float(R[t]),4) for t,y in enumerate(YEARS)},
            "augmentation_rate":{int(y):round(float(A[t]),4) for t,y in enumerate(YEARS)}}
        capacity_decisions[career][sc] = {"year10_index":round(float(yr10_idx),2),"recommendation":advice}

results["career_outlook"] = career_outlook
results["capacity_decisions"] = capacity_decisions

# Curriculum
curriculum_alloc = {}
C_base = compute_capabilities("base")
for i, career in enumerate(CAREERS):
    cr_emp, alpha_emp, sc_emp = grid_search_curriculum(i, C_base, (1.0, 0.0, 0.0))
    cr_full, alpha_full, sc_full = grid_search_curriculum(i, C_base, (0.5, 0.25, 0.25))
    curriculum_alloc[career] = {
        "employment_only":{COURSE_NAMES[k]:int(cr_emp[k]) for k in range(6)},
        "with_equity_resilience":{COURSE_NAMES[k]:int(cr_full[k]) for k in range(6)},
        "total_credits_check":[int(cr_emp.sum()), int(cr_full.sum())]}
results["curriculum_allocations"] = curriculum_alloc

# Scenario analysis summary
scenario_analysis = {}
for i, career in enumerate(CAREERS):
    scenario_analysis[career] = {sc: capacity_decisions[career][sc] for sc in SCENARIOS}
results["scenario_analysis"] = scenario_analysis

# Sensitivity: 2D scan sub_mult x aug_mult
sub_mults = np.linspace(0.5, 1.5, 11)
aug_mults = np.linspace(0.5, 1.5, 11)
sens_data = {}
for i, career in enumerate(CAREERS):
    heatmap = np.zeros((len(sub_mults), len(aug_mults)))
    for si, sm in enumerate(sub_mults):
        for ai, am in enumerate(aug_mults):
            C = compute_capabilities("base")
            tau = TASK_VECTORS[i]
            R = np.array([np.clip(np.sum(tau * SIGMA[i]*sm * C[t]), 0, 1) for t in range(len(YEARS))])
            A = np.array([np.clip(np.sum(tau * ETA[i]*am * C[t] * (1 - SIGMA[i]*sm*C[t])), 0, 1) for t in range(len(YEARS))])
            idx = compute_employment_index(R, A, G_BASE[i])
            heatmap[si, ai] = idx[-1]
    sens_data[career] = heatmap
results["sensitivity_analysis"] = {c:{"sub_mult_range":[0.5,1.5],"aug_mult_range":[0.5,1.5],
    "index_min":round(float(sens_data[c].min()),2),"index_max":round(float(sens_data[c].max()),2)} for c in CAREERS}

# Non-employment objectives
non_emp = {}
for i, career in enumerate(CAREERS):
    _, alpha_emp, _ = grid_search_curriculum(i, C_base, (1.0, 0.0, 0.0))
    _, alpha_full, _ = grid_search_curriculum(i, C_base, (0.5, 0.25, 0.25))
    eq_shift = alpha_full[4]+alpha_full[5] - (alpha_emp[4]+alpha_emp[5])
    non_emp[career] = {"equity_gain_practicum_cross":round(float(eq_shift),3),
        "resilience_note":"min-scenario index used in optimization"}
results["non_employment_objectives"] = non_emp

# Validation
checks = {"all_indices_positive":True,"all_rates_in_01":True,"all_credits_sum_120":True}
for career in CAREERS:
    for sc in SCENARIOS:
        vals = list(career_outlook[career][sc]["index"].values())
        if any(v < 0 for v in vals): checks["all_indices_positive"] = False
        rvals = list(career_outlook[career][sc]["substitution_rate"].values())
        avals = list(career_outlook[career][sc]["augmentation_rate"].values())
        if any(v<0 or v>1 for v in rvals+avals): checks["all_rates_in_01"] = False
    for key in ["employment_only","with_equity_resilience"]:
        s = sum(curriculum_alloc[career][key].values())
        if s != 120: checks["all_credits_sum_120"] = False
results["validation_checks"] = checks

results["limitations"] = [
    "Task vectors are scenario assumptions, not calibrated from O*NET/BLS data.",
    "Contribution matrices S_kj are expert-judgment placeholders requiring empirical validation.",
    "No cross-career interaction effects modeled.",
    "Equity proxy v_ks is assumption-driven; conclusions are illustrative, not data-supported.",
    "BLS projections may embed partial AI effects; g_base used here is a no-AI counterfactual estimate.",
    "Demand creation effect omitted to avoid level/increment mixing; only substitution and augmentation modeled."
]

# === Output ===
os.makedirs("results", exist_ok=True)
os.makedirs("figures", exist_ok=True)
with open("results/results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

# Fig 1: Career scenarios
fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), sharey=True)
colors = {"conservative":"#2196F3","base":"#4CAF50","aggressive":"#F44336"}
for i, career in enumerate(CAREERS):
    ax = axes[i]
    for sc in SCENARIOS:
        idx = list(career_outlook[career][sc]["index"].values())
        ax.plot(YEARS, idx, color=colors[sc], label=sc, linewidth=2)
    cf = list(career_outlook[career]["base"]["counterfactual"].values())
    ax.plot(YEARS, cf, '--', color='gray', label='No-AI counterfactual')
    ax.axhline(100, color='k', linewidth=0.5, linestyle=':')
    ax.set_title(career, fontsize=11)
    ax.set_xlabel("Year")
    if i == 0: ax.set_ylabel("Employment Demand Index (2026=100)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("figures/career_scenarios.png", dpi=300, bbox_inches='tight')
plt.close()

# Fig 2: Curriculum allocations
fig, axes = plt.subplots(1, 3, figsize=(14, 5))
x = np.arange(6)
width = 0.35
for i, career in enumerate(CAREERS):
    ax = axes[i]
    emp_vals = [curriculum_alloc[career]["employment_only"][c] for c in COURSE_NAMES]
    full_vals = [curriculum_alloc[career]["with_equity_resilience"][c] for c in COURSE_NAMES]
    ax.bar(x - width/2, emp_vals, width, label='Employment Only', color='#1976D2')
    ax.bar(x + width/2, full_vals, width, label='+ Equity & Resilience', color='#FF8F00')
    ax.set_xticks(x)
    ax.set_xticklabels(["Core","AI Tool","AI Prin","Ethics","Pract","Cross"], fontsize=8, rotation=30)
    ax.set_title(career, fontsize=10)
    ax.set_ylabel("Credits (total=120)")
    ax.legend(fontsize=8)
    ax.set_ylim(0, 65)
    ax.grid(axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig("figures/curriculum_allocations.png", dpi=300, bbox_inches='tight')
plt.close()

# Fig 3: Sensitivity heatmap
fig, axes = plt.subplots(1, 3, figsize=(14, 4))
for i, career in enumerate(CAREERS):
    ax = axes[i]
    im = ax.imshow(sens_data[career], origin='lower', aspect='auto',
                   extent=[0.5,1.5,0.5,1.5], cmap='RdYlGn', vmin=80, vmax=120)
    ax.set_xlabel("Augmentation Elasticity Multiplier")
    if i == 0: ax.set_ylabel("Substitution Elasticity Multiplier")
    ax.set_title(career, fontsize=10)
    cs = ax.contour(sens_data[career], levels=[95,100,105], origin='lower',
                    extent=[0.5,1.5,0.5,1.5], colors='k', linewidths=0.8)
    ax.clabel(cs, inline=True, fontsize=8)
    plt.colorbar(im, ax=ax, fraction=0.046)
plt.tight_layout()
plt.savefig("figures/sensitivity_heatmap.png", dpi=300, bbox_inches='tight')
plt.close()

print("Done. Outputs: results/results.json, figures/career_scenarios.png, "
      "figures/curriculum_allocations.png, figures/sensitivity_heatmap.png")
