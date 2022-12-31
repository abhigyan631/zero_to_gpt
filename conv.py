from network import Module
import numpy as np
from skimage.util import view_as_windows
import math

def convolve(image, kernel):
    return np.matmul(image, kernel.reshape(math.prod(kernel.shape), 1)).copy()

def unroll_image(image, kernel_x, kernel_y):
    unrolled = view_as_windows(image, (kernel_x, kernel_y))
    x_size = (image.shape[0] - (kernel_x - 1))
    y_size = (image.shape[1] - (kernel_y - 1))
    rows = x_size * y_size
    return unrolled.reshape(rows, kernel_x * kernel_y)

class Conv(Module):
    def __init__(self, input_channels, output_channels, kernel_x, kernel_y, relu=True, seed=0):
        self.add_relu = relu
        self.kernel_x = kernel_x
        self.kernel_y = kernel_y
        self.input_channels = input_channels
        self.output_channels = output_channels
        self.hidden = None

        np.random.seed(seed)
        self.weights = np.random.rand(input_channels, output_channels, kernel_x, kernel_y) / 10
        self.relu = lambda x: np.maximum(x, 0)

        super().__init__()

    def forward(self, x):
        new_x = x.shape[1] - (self.kernel_x - 1)
        new_y = x.shape[2] - (self.kernel_y - 1)
        output = np.zeros((self.output_channels, new_x, new_y))
        for channel in range(self.input_channels):
            unrolled = unroll_image(x[channel, :], self.kernel_x, self.kernel_y)
            for next_channel in range(self.output_channels):
                kernel = self.weights[channel, next_channel, :]
                mult = convolve(unrolled, kernel).reshape(new_x, new_y)
                output[next_channel, :] += mult
        output /= x.shape[0]

        self.hidden = output.copy()
        if self.add_relu:
            output = np.maximum(output, 0)
        return output

    def backward(self, grad, lr, prev_hidden):
        grad = grad.reshape(self.hidden.shape)
        if self.add_relu:
            grad = np.multiply(grad, np.heaviside(self.hidden, 0))

        _, grad_x, grad_y = grad.shape
        new_grad = np.zeros(prev_hidden.shape)
        for channel in range(self.input_channels):
            # With multi-channel output, you need to loop across the output grads to link to input channel kernels
            # Each kernel gets a unique update
            flat_input = unroll_image(prev_hidden[channel, :], grad_x, grad_y)
            for next_channel in range(self.output_channels):
                # Kernel update
                channel_grad = grad[next_channel, :]
                k_grad = convolve(flat_input, channel_grad).reshape(self.kernel_x, self.kernel_y)
                grad_norm = math.prod(channel_grad.shape)
                self.weights[channel, next_channel, :] -= (k_grad * lr) / grad_norm
        for next_channel in range(self.output_channels):
            channel_grad = grad[next_channel, :]
            padded_grad = np.pad(channel_grad, ((self.kernel_x - 1, self.kernel_x - 1), (self.kernel_y - 1, self.kernel_y - 1)))
            flat_padded = unroll_image(padded_grad, self.kernel_x, self.kernel_y)
            for channel in range(self.input_channels):
                # Grad to lower layer
                flipped_kernel = np.flip(self.weights[channel, next_channel, :], axis=[0, 1])
                updated_grad = convolve(flat_padded, flipped_kernel).reshape(prev_hidden.shape[1], prev_hidden.shape[2])
                # Since we're multiplying each input by multiple kernel values, reduce the gradient accordingly
                # This will reduce the edges more than necessary (they contribute to fewer output values), but is simple to implement
                new_grad[channel, :] += updated_grad / math.prod(flipped_kernel.shape)
        return new_grad