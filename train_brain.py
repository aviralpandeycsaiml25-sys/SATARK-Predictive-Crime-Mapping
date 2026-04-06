import torch
import torch.optim as optim
from sqlalchemy import create_engine, text
from brain import SATARK_Brain

# 1. Connect to PostGIS (Update your password)
engine = create_engine("postgresql://postgres:Aviral19!@localhost:5432/satark_db")

def get_training_data():
    with engine.connect() as conn:
        # Get city list for Graph Nodes
        cities = [row[0] for row in conn.execute(text("SELECT DISTINCT city FROM crimes"))]
        
        # Get crime counts per city as input features
        data = conn.execute(text("SELECT city, count(*) FROM crimes GROUP BY city"))
        counts = {row[0]: row[1] for row in data}
        
        # Convert to a Tensor (AI-readable format)
        features = torch.tensor([counts.get(c, 0) for c in cities], dtype=torch.float).view(1, 1, len(cities), 1)
        return cities, features

# 2. Setup the Brain
cities, features = get_training_data()
num_nodes = len(cities)
adj = torch.ones((num_nodes, num_nodes)) # Simple adjacency for now

model = SATARK_Brain(num_nodes=num_nodes, num_features=1, adj=adj)
optimizer = optim.Adam(model.parameters(), lr=0.01) # The "Teacher"
criterion = torch.nn.MSELoss() # Measures how "wrong" the AI is

print("🧠 Starting Training Loop...")

# 3. The Training Loop (100 Epochs)
for epoch in range(101):
    optimizer.zero_grad()
    
    # Predict risk scores
    output = model(features)
    
    # In this demo, we "train" it to recognize the high-crime nodes
    target = features.view(1, num_nodes, 1) 
    loss = criterion(output, target)
    
    loss.backward()
    optimizer.step()
    
    if epoch % 20 == 0:
        print(f"Epoch {epoch} | Loss: {loss.item():.4f}")

# 4. Save the "Brain's knowledge"
torch.save(model.state_dict(), "satark_brain.pth")
print("✅ Training Complete. Model saved as 'satark_brain.pth'.")