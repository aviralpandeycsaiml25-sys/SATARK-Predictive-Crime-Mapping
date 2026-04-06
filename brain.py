import torch
import torch.nn as nn
import torch.nn.functional as F

class STGCNBlock(nn.Module):
    def __init__(self, in_channels, out_channels, adjacency_matrix):
        super(STGCNBlock, self).__init__()
        self.register_buffer('adj', adjacency_matrix)
        self.t_conv = nn.Conv2d(in_channels, out_channels, kernel_size=(1, 3), padding=(0, 1))
        self.s_conv = nn.Linear(out_channels, out_channels)

    def forward(self, x):
        # x shape: (Batch, Channels, Nodes, Time)
        x = self.t_conv(x)
        
        # FIX: Align dimensions for matrix multiplication
        x = x.permute(0, 1, 3, 2) 
        x = torch.matmul(x, self.adj)
        x = x.permute(0, 1, 3, 2)
        
        x = self.s_conv(x.transpose(1, 3)).transpose(1, 3)
        return F.relu(x)

class SATARK_Brain(nn.Module):
    def __init__(self, num_nodes, num_features, adj):
        super(SATARK_Brain, self).__init__()
        self.block1 = STGCNBlock(num_features, 64, adj)
        self.block2 = STGCNBlock(64, 128, adj)
        self.fully_connected = nn.Linear(128, 1)

    # CRITICAL: This must be named exactly 'forward'
    def forward(self, x):
        x = self.block1(x)
        x = self.block2(x)
        # Pool across the time dimension
        x = torch.mean(x, dim=-1) 
        # Final prediction per node
        return self.fully_connected(x.transpose(1, 2))