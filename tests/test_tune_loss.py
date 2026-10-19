import pandas as pd

from jarvis.tune_loss import loss_table, straps_to_skip


def make_homes(rows):
    return pd.DataFrame(rows, columns=["strap", "wall", "destroyed"])


HOMES = make_homes([
    ("R1", "Frame Wood/Shake", True),
    ("R2", "Frame Wood/Shake", False),
    ("R3", "Frame Wood/Shake", True),
    ("R4", "Brick Veneer", False),
    ("R5", None, True),
])


def factors_by_siding(table):
    return {row.wall: row.loss_factor for row in table.itertuples()}


def test_small_and_unknown_sidings_get_no_row_of_their_own():
    table = loss_table(HOMES, min_homes=2, prior_homes=0)
    # One brick home is too few for a row, and R5's blank siding only counts
    # toward the overall row.
    assert factors_by_siding(table) == {"any": 0.6, "wood": 0.667}


def test_sidings_are_pulled_toward_the_overall_rate():
    table = loss_table(HOMES, min_homes=2, prior_homes=3)
    # wood: (2 destroyed + 3 homes at 0.6) / (3 + 3) homes
    assert factors_by_siding(table)["wood"] == 0.633


def test_skips_new_roofs_since_the_fire_and_homes_still_being_built(tmp_path):
    path = tmp_path / "permits.csv"
    reroof = "RESIDENTIAL RE-ROOF"
    permits = pd.DataFrame({
        "strap": ["R1", "R2", "R3", "R4"],
        "permit_category": [reroof, reroof, "DECK", "NEW CONSTRUCTION"],
        "issue_dt": [
            "6/1/2021 12:00:00 AM",  # re-roofed before the fire
            "3/15/2022 12:00:00 AM",  # re-roofed after it
            "3/15/2022 12:00:00 AM",  # a deck doesn't change the siding or roof
            "11/2/2021 12:00:00 AM",  # still being built when the fire hit
        ],
    })
    permits.to_csv(path, index=False)
    assert straps_to_skip(path) == {"R2", "R4"}
