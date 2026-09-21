import math

import pytest

from antsim.domain import (
    Point3D,
    SimulationRequest,
    VoltageSource,
    Wire,
)


def create_valid_wire() -> Wire:
    return Wire(
        tag=1,
        start=Point3D(-5.0, 0.0, 0.0),
        end=Point3D(5.0, 0.0, 0.0),
        radius_m=0.001,
        segments=101,
    )


def test_wire_rejects_identical_endpoints():
    point = Point3D(0.0, 0.0, 0.0)

    with pytest.raises(ValueError):
        Wire(
            tag=1,
            start=point,
            end=point,
            radius_m=0.001,
            segments=11,
        )


def test_wire_rejects_invalid_radius():
    with pytest.raises(ValueError):
        Wire(
            tag=1,
            start=Point3D(0.0, 0.0, 0.0),
            end=Point3D(1.0, 0.0, 0.0),
            radius_m=0.0,
            segments=11,
        )


def test_request_requires_at_least_one_wire():
    with pytest.raises(ValueError):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(),
            source=VoltageSource(
                wire_tag=1,
                segment=1,
            ),
        )


def test_request_rejects_unknown_source_wire():
    with pytest.raises(ValueError):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(create_valid_wire(),),
            source=VoltageSource(
                wire_tag=99,
                segment=51,
            ),
        )


def test_request_rejects_unknown_source_segment():
    with pytest.raises(ValueError):
        SimulationRequest(
            frequency_mhz=14.15,
            wires=(create_valid_wire(),),
            source=VoltageSource(
                wire_tag=1,
                segment=200,
            ),
        )


def test_point_rejects_non_finite_coordinate():
    with pytest.raises(ValueError):
        Point3D(math.inf, 0.0, 0.0)
        