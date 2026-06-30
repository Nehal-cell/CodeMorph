import tensorflow as tf
from tensorflow.keras import layers

class SimpleClassifier(tf.keras.Model):
    def __init__(self, num_classes):
        super(SimpleClassifier, self).__init__()
        self.dense1 = layers.Dense(128, activation="relu")
        self.dense2 = layers.Dense(num_classes, activation="softmax")

    def call(self, inputs):
        x = self.dense1(inputs)
        return self.dense2(x)
