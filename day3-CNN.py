import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import datasets, transforms
from torch.utils.data import DataLoader


## 无stride，padding：
# class MyConv2d(nn.Module):
#     def __init__(self, in_channels, out_channels, kernel_size):
#         super(MyConv2d, self).__init__()
#         self.weight = nn.Parameter(torch.randn(out_channels, in_channels, kernel_size, kernel_size) * 0.01)
#         self.bias = nn.Parameter(torch.zeros(out_channels))
#         self.kernel_size = kernel_size

#     def forward(self, x):
#         batch_size, in_channels, H, W = x.shape
#         out_channels = self.weight.shape[0]
#         k = self.kernel_size
#         out_H = H - k + 1
#         out_W = W - k + 1

#         output = torch.zeros((batch_size, out_channels, out_H, out_W), device=x.device)

#         for b in range(batch_size):
#             for oc in range(out_channels):
#                 for ic in range(in_channels):
#                     for i in range(out_H):
#                         for j in range(out_W):
#                             region = x[b, ic, i:i + k, j:j + k]
#                             output[b, oc, i, j] += torch.sum(region * self.weight[oc, ic])
#                 output[b, oc] += self.bias[oc]
#         return output

# 修改stride=2，同时加入padding（默认值分别为2和1）
class MyConv2d(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride=2, padding=1):
        super(MyConv2d, self).__init__()
        self.weight = nn.Parameter(torch.randn(out_channels, in_channels, kernel_size, kernel_size) * 0.01)
        self.bias = nn.Parameter(torch.zeros(out_channels))
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding

    def forward(self, x):
        batch_size, in_channels, H, W = x.shape
        out_channels = self.weight.shape[0]
        k = self.kernel_size
        p = self.padding
        
        # 计算输出尺寸 (考虑padding和stride)
        out_H = (H + 2*p - k) // self.stride + 1
        out_W = (W + 2*p - k) // self.stride + 1
        
        # 对输入进行padding
        if self.padding > 0:
            x_padded = torch.zeros((batch_size, in_channels, H + 2*p, W + 2*p), device=x.device)
            x_padded[:, :, p:p+H, p:p+W] = x  
        else:
            x_padded = x
        
        output = torch.zeros((batch_size, out_channels, out_H, out_W), device=x.device)

        for b in range(batch_size):
            for oc in range(out_channels):
                for ic in range(in_channels):
                    for i in range(out_H):
                        for j in range(out_W):
                            # 计算输入区域的起始位置（考虑stride）
                            h_start = i * self.stride
                            w_start = j * self.stride
                            region = x_padded[b, ic, h_start:h_start + k, w_start:w_start + k]
                            output[b, oc, i, j] += torch.sum(region * self.weight[oc, ic])
                output[b, oc] += self.bias[oc]
        return output

class MyBatchNorm2d(nn.Module):
    def __init__(self, num_features, eps=1e-5, momentum=0.1):
        super(MyBatchNorm2d, self).__init__()
        self.eps = eps
        self.momentum = momentum
        self.gamma = nn.Parameter(torch.ones(num_features))
        self.beta = nn.Parameter(torch.zeros(num_features))

        self.register_buffer('running_mean', torch.zeros(num_features))
        self.register_buffer('running_var', torch.ones(num_features))

    def forward(self, x):
        if self.training:
            mean = x.mean([0, 2, 3])
            var = x.var([0, 2, 3], unbiased=False)

            self.running_mean = (1 - self.momentum) * self.running_mean + self.momentum * mean.detach()
            self.running_var = (1 - self.momentum) * self.running_var + self.momentum * var.detach()
        else:
            mean = self.running_mean
            var = self.running_var
        x_hat = (x - mean[None, :, None, None]) / torch.sqrt(var[None, :, None, None] + self.eps)
        return self.gamma[None, :, None, None] * x_hat + self.beta[None, :, None, None]


class MyCNN(nn.Module):
    def __init__(self):
        super(MyCNN, self).__init__()
        self.conv = MyConv2d(1, 8, 3)
        self.bn = MyBatchNorm2d(8)
        self.pool = nn.MaxPool2d(2)
        # self.fc = nn.Linear(8 * 13 * 13, 10)  # 28 - 3 + 1 = 26 -> pool -> 13   # 为stride和padding是1和0的情况
        self.fc = nn.Linear(8 * 7 * 7, 10)  

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = F.relu(x)
        x = self.pool(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)
        return x


# 数据加载
transform = transforms.Compose([
    transforms.ToTensor()
])

train_dataset = datasets.MNIST(root='./mnist_data', train=True, transform=transform, download=True)
test_dataset = datasets.MNIST(root='./mnist_data', train=False, transform=transform, download=True)

train_loader = DataLoader(train_dataset, batch_size=64, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=64, shuffle=False)

# 模型训练
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = MyCNN().to(device)
optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
loss_fn = nn.CrossEntropyLoss()

for epoch in range(50):
    model.train()
    total_loss = 0
    for x, y in train_loader:
        x, y = x.to(device), y.to(device)
        out = model(x)
        loss = loss_fn(out, y)
        print(loss)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
    print(f"Epoch {epoch + 1}, Loss: {total_loss:.4f}")
