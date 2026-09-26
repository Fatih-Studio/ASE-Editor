import pytest

from ase_editor.route_tools import RouteNode, checkpoint_text, compact_route, suggest_checkpoint


def test_airway_transitions_and_repeated_fixes():
    nodes = (RouteNode("WIII", 0, 0), RouteNode("A", 0, 1),
             RouteNode("B", 0, 2, "G1", "AWY-HI"), RouteNode("A", 0, 3, "G1", "AWY-HI"),
             RouteNode("C", 0, 4, "G2", "AWY-HI"), RouteNode("WADD", 0, 5))
    assert compact_route(nodes) == "WIII DCT A G1 A G2 C DCT WADD"
    assert checkpoint_text(nodes, 1) == "A B A C WADD"
    assert checkpoint_text(nodes, 3) == "A C WADD"


def test_procedures_and_tracks_keep_all_nodes():
    nodes = (RouteNode("WIII", 0, 0), RouteNode("UNKNOWN", 0, 1, "SID1", "SID"),
             RouteNode("50N020W", 50, -20, "A", "NAT"), RouteNode("WADD", 0, 2))
    assert compact_route(nodes) == "WIII DCT UNKNOWN DCT 50N020W DCT WADD"


@pytest.mark.parametrize("longitude,index", [(-1, 1), (0.5, 1), (1.5, 2), (3, 2)])
def test_downstream_checkpoint(longitude, index):
    nodes = tuple(RouteNode(ident, 0, lon) for ident, lon in (("A", 0), ("B", 1), ("C", 2)))
    assert suggest_checkpoint(nodes, 0, longitude, 90)[0] == index


def test_heading_disambiguates_crossing():
    nodes = (RouteNode("A", -1, 0), RouteNode("B", 1, 0),
             RouteNode("C", 0, -1), RouteNode("D", 0, 1))
    assert suggest_checkpoint(nodes, 0, 0, 0)[0] == 1
    assert suggest_checkpoint(nodes, 0, 0, 90)[0] == 3


def test_dateline_and_degenerate_segment():
    nodes = (RouteNode("A", 0, 179), RouteNode("A", 0, 179), RouteNode("B", 0, -179))
    index, distance = suggest_checkpoint(nodes, 0, 180, 90)
    assert index == 2
    assert distance == pytest.approx(0, abs=1e-8)


def test_invalid_start():
    with pytest.raises(ValueError):
        checkpoint_text((RouteNode("A", 0, 0),), -1)
