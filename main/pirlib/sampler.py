from gpiozero import DigitalInputDevice
import random 
import time
from datetime import datetime # ΝΕΟ: Για να βλέπουμε ώρα/μέρα

class PirSampler:
    def __init__(self, pin: int):
        self.pin = pin
        self.dev = DigitalInputDevice(pin)

    def read(self) -> bool:
        # True = HIGH, False = LOW
        return bool(self.dev.value)

class VirtualPirSampler:
    def __init__(self, sample_interval: float = 0.1, hold_time_s: float = 1.5, rate_multiplier: float = 10.0):
        """
        sample_interval: Κάθε πότε διαβάζει ο producer το read() (σε δευτερόλεπτα).
        hold_time_s: Πόσο διαρκεί το σήμα HIGH.
        rate_multiplier: Πολλαπλασιαστής (π.χ. 10.0) για να έρχονται τα δεδομένα πιο γρήγορα κατά το debugging.
        """
        self.sample_interval = sample_interval
        self.hold_time = hold_time_s
        self.rate_multiplier = rate_multiplier
        
        self.is_high = False
        self.high_until = 0.0

    def _get_current_base_rate(self) -> float:
        """Επιστρέφει το 'events per hour' βάσει του αλγορίθμου από το train_model.py"""
        now = datetime.now()
        day_of_week = now.weekday() # 0: Δευτέρα, 6: Κυριακή
        hour = now.hour

        if day_of_week == 5 or day_of_week == 6:
            base_rate = 2
        elif 8 <= hour <= 10:
            base_rate = 15
        elif 11 <= hour <= 14:
            base_rate = 25
        elif 15 <= hour <= 17:
            base_rate = 12
        elif 18 <= hour <= 20:
            base_rate = 8
        else:
            base_rate = 1
            
        return base_rate * self.rate_multiplier

    def read(self) -> bool:
        current_time = time.time()
        
        if self.is_high:
            # Αν είναι ήδη ψηλά, δες αν πέρασε ο χρόνος για να "πέσει"
            if current_time > self.high_until:
                self.is_high = False
            return self.is_high
        else:
            # 1. Υπολογισμός events ανά ώρα 
            events_per_hour = self._get_current_base_rate()
            
            # 2. Μετατροπή σε events ανά δευτερόλεπτο
            events_per_second = events_per_hour / 3600.0
            
            # 3. Πιθανότητα στο συγκεκριμένο χρονικό "παράθυρο" (sample_interval)
            # Αν τρέχει 10 φορές το δευτερόλεπτο (0.1s), η πιθανότητα μοιράζεται.
            dynamic_probability = events_per_second * self.sample_interval
            
            if random.random() < dynamic_probability:
                self.is_high = True
                self.high_until = current_time + self.hold_time
                
            return self.is_high