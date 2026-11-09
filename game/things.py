"""Item instances: a kind (a row of data/items.csv) plus its own state."""

from tables import ITEMS, TUNE


class Thing:
    def __init__(self, kind, charges=None, fuel=None):
        self.kind = kind
        row = ITEMS[kind]
        self.charges = row["charges"] if charges is None else charges  # waterskin drinks
        self.fuel = row["fuel_sec"] * 60 if fuel is None else fuel  # torch frames left

    @property
    def row(self):
        return ITEMS[self.kind]

    @property
    def name(self):
        if self.kind == "torch" and self.fuel <= 0:
            return "a burnt-out torch"
        if self.kind == "waterskin" and self.charges <= 0:
            return "an empty waterskin"
        return self.row["name"]

    def fits(self, slot):
        """Can this go in an equipment slot (right, left, head, body) or the pack?"""
        if slot == "pack":
            return True
        want = self.row["slot"]
        return want == ("hand" if slot in ("right", "left") else slot)

    @property
    def light(self):
        """0..1 brightness when held: only torches with fuel give light."""
        if self.kind != "torch" or self.fuel <= 0:
            return 0.0
        frac = self.fuel / (self.row["fuel_sec"] * 60)
        dim = TUNE["torch_dim"]
        return 1.0 if frac >= dim else 0.4 + 0.6 * frac / dim

    def copy(self):
        return Thing(self.kind, self.charges, self.fuel)

    def __repr__(self):
        return f"Thing({self.kind!r})"
