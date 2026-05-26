from gpiozero import DigitalInputDevice

import random 
import time   

class PirSampler:
    def __init__(self, pin: int):
        self.pin = pin
        self.dev = DigitalInputDevice(pin)

    def read(self) -> bool:
        # True = HIGH, False = LOW
        return bool(self.dev.value)

class VirtualPirSampler:
    def __init__(self, motion_probability: float = 0.05, hold_time_s: float = 2.0):
        """
        motion_probability: Πιθανότητα (0.0 έως 1.0) να "δει" κίνηση σε κάθε sample.
        hold_time_s: Πόσα δευτερόλεπτα θα κρατήσει το σήμα HIGH αφού εντοπίσει κίνηση (για να μην ανοιγοκλείνει στιγμιαία).
        """
        self.probability = motion_probability
        self.hold_time = hold_time_s
        self.is_high = False
        self.high_until = 0.0

    def read(self) -> bool:
        current_time = time.time()
        
        if self.is_high:
            # Αν είναι ήδη ψηλά, δες αν πέρασε ο χρόνος για να "πέσει"
            if current_time > self.high_until:
                self.is_high = False
            return self.is_high
        else:
            # Αν είναι χαμηλά, δες αν θα "χτυπήσει" κίνηση τώρα
            if random.random() < self.probability:
                self.is_high = True
                self.high_until = current_time + self.hold_time
            return self.is_high