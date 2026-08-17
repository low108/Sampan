class TestGivenName:
    """A bell that names the surname names nobody: half the household shares it."""

    def test_the_surname_is_dropped(self) -> None:
        from sampan.notifications import given_name

        assert given_name("Lim Siew Khim") == "Siew Khim"
        assert given_name("Tan Wei Lun") == "Wei Lun"
        assert given_name("Tan Xin Yi") == "Xin Yi"

    def test_a_single_name_survives_intact(self) -> None:
        from sampan.notifications import given_name

        assert given_name("Khim") == "Khim"
