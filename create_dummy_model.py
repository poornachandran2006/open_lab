"""
GridGuard - Pre-trained Random Forest Model Generator
Trained on the exact representative feature vectors for the 8 IEEE 1159 disturbance classes:
0: Normal
1: Voltage Sag
2: Voltage Swell
3: Interruption
4: Flicker
5: Transient Spike
6: Harmonic Distortion
7: Notching

Features: [rms, crest_factor, thd, band_energy]
Saves to: gridguard_rf_model_combined.pkl
"""

import os
os.environ["LOKY_MAX_CPU_COUNT"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier

np.random.seed(42)

# Centroids matching exact GridGuard IEEE 1159 representative features
CENTROIDS = [
    (0, "Normal",              [0.707, 1.414, 0.003, 0.001]),
    (1, "Voltage Sag",         [0.450, 1.850, 0.067, 0.008]),
    (2, "Voltage Swell",       [0.900, 1.700, 0.033, 0.003]),
    (3, "Interruption",        [0.050, 2.100, 0.170, 0.027]),
    (4, "Flicker",             [0.720, 1.650, 0.005, 0.001]),
    (5, "Transient Spike",     [0.741, 3.100, 0.100, 0.066]),
    (6, "Harmonic Distortion", [0.740, 1.310, 0.308, 0.017]),
    (7, "Notching",            [0.692, 1.520, 0.137, 0.018]),
]

X = []
y = []
samples_per_class = 200

for label, name, center in CENTROIDS:
    center = np.array(center)
    # Add realistic small noise around the centroid (3-5% standard deviation)
    std_dev = np.maximum(center * 0.04, 0.001)
    noise = np.random.normal(0, std_dev, (samples_per_class, 4))
    samples = np.clip(center + noise, 0.0, None)
    
    # Always include the exact centroid
    samples[0] = center

    X.append(samples)
    y.extend([label] * samples_per_class)

X = np.vstack(X)
y = np.array(y)

rf_model = RandomForestClassifier(n_estimators=30, max_depth=8, random_state=42, n_jobs=1)
rf_model.fit(X, y)

output_path = "gridguard_rf_model_combined.pkl"
joblib.dump(rf_model, output_path)
print(f"SUCCESS: Model saved to {output_path} ({len(y)} samples, 8 classes).", flush=True)

# Verification check
test_vectors = [c[2] for c in CENTROIDS]
preds = rf_model.predict(test_vectors)
print(f"Verification accuracy on centroids: {(preds == np.arange(8)).mean() * 100:.1f}%")
