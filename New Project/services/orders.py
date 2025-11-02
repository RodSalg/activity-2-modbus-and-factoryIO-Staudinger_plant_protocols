class OrderManager:
    def __init__(self):
        self.pending_A = 0
        self.pending_B = 0

    def set_pending(self, a: int, b: int):
        self.pending_A, self.pending_B = max(0, int(a)), max(0, int(b))

    def pick_destination(self) -> str:
        if self.pending_A > 0:
            self.pending_A -= 1
            return "A"
        if self.pending_B > 0:
            self.pending_B -= 1
            return "B"
        return "A"  # default

    def has_pending(self) -> bool:
        return (self.pending_A > 0) or (self.pending_B > 0)
