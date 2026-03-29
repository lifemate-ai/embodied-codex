from toio_world.policies import calibration_sweep, random_walk, spin, square


def test_square_policy_has_expected_length() -> None:
    assert len(square(repeats=2)) == 16


def test_spin_policy_has_expected_length() -> None:
    assert len(spin(repeats=5)) == 5


def test_random_walk_is_seedable() -> None:
    assert random_walk(steps=4, seed=1) == random_walk(steps=4, seed=1)


def test_calibration_sweep_yields_repeated_discrete_actions() -> None:
    actions = calibration_sweep(repeats=2)
    assert len(actions) == 14
    assert actions[0].type == "forward_short"
    assert actions[-1].type == "turn_right_large"
