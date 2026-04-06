# SATARK: Spatio-Temporal Crime Prediction Engine

**SATARK** is a predictive analytics platform designed to assist law enforcement by identifying potential crime hotspots using Deep Learning.

## 🔬 Research Methodology
- **Architecture:** Spatio-Temporal Graph Convolutional Networks (ST-GCN).
- **Core Logic:** Modeling urban sectors as nodes in a graph to capture spatial correlations in criminal activity.
- **Backend:** FastAPI (Asynchronous Python) for real-time inference.
- **Frontend:** Vanilla JS with Leaflet.js for 3D spatial visualization.

## 📂 Key Components
- `main.py`: Entry point for the FastAPI server.
- `satark_brain.pth`: Pre-trained weights for the ST-GCN model.
- `train_brain.py`: Script for model training and hyperparameter tuning.
- `frontend/`: Interactive dashboard for law enforcement visualization.
