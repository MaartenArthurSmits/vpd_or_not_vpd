"""Endpoint tests for the local calculation API. Numbers are checked against the production functions."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
import vpd  # noqa: E402

pytestmark = pytest.mark.unit

client = TestClient(api.app)


def post(body, **kwargs):
    return client.post("/v1/calculate", json=body, **kwargs)


def test_normal_calculation_matches_the_production_functions_at_full_precision():
    res = post({"air_temperature_c": 22.34, "relative_humidity_percent": 60.25})
    assert res.status_code == 200
    body = res.json()
    ref = vpd.calculate_vpd(22.34, 60.25)
    r = body["results"]
    assert r["air_vpd_kpa"] == ref.vpd_air and r["leaf_vpd_kpa"] == ref.vpd_leaf       # exact, not rounded
    assert r["leaf_temperature_c"] == 22.34 and r["saturation_vapour_pressure_air_kpa"] == ref.es_air
    assert r["saturation_vapour_pressure_leaf_kpa"] == ref.es_leaf and r["actual_vapour_pressure_kpa"] == ref.ea
    assert body["inputs"] == {"air_temperature_c": 22.34, "relative_humidity_percent": 60.25,
                              "leaf_temperature_offset_c": 0.0, "measured_leaf_temperature_c": None,
                              "leaf_input": "default_zero_offset"}
    assert body["possible_condensation"] is False and body["warnings"] == []
    assert "FAO-56" in body["equation"]["source"] and body["equation"]["url"].startswith("https://www.fao.org/")


def test_leaf_offset_input_and_negative_leaf_vpd_are_preserved():
    body = post({"air_temperature_c": 22, "relative_humidity_percent": 100, "leaf_temperature_offset_c": -3}).json()
    ref = vpd.calculate_vpd(22, 100, -3)
    assert body["inputs"]["leaf_input"] == "offset" and body["results"]["leaf_temperature_c"] == 19
    assert body["results"]["leaf_vpd_kpa"] == ref.vpd_leaf < 0                       # negative value is not clipped
    assert body["possible_condensation"] is True and any("condensation" in w for w in body["warnings"])


def test_measured_leaf_temperature_input():
    body = post({"air_temperature_c": 22, "relative_humidity_percent": 60, "measured_leaf_temperature_c": 20}).json()
    ref = vpd.calculate_vpd(22, 60, measured_leaf=20)
    assert body["inputs"]["leaf_input"] == "measured" and body["inputs"]["measured_leaf_temperature_c"] == 20
    assert body["inputs"]["leaf_temperature_offset_c"] == -2                          # derived from the measurement
    assert body["results"]["leaf_temperature_c"] == 20 and body["results"]["leaf_vpd_kpa"] == ref.vpd_leaf
    assert body["results"]["air_vpd_kpa"] == ref.vpd_air


def test_conflicting_leaf_inputs_are_rejected_with_a_clear_message():
    res = post({"air_temperature_c": 22, "relative_humidity_percent": 60, "leaf_temperature_offset_c": -2,
                "measured_leaf_temperature_c": 20})
    assert res.status_code == 422
    assert "not both" in res.text and "leaf_temperature_offset_c" in res.text


@pytest.mark.parametrize("body", [
    {"relative_humidity_percent": 60},                                                   # missing field
    {"air_temperature_c": 22},
    {"air_temperature_c": 61, "relative_humidity_percent": 60},                          # outside the calculator limits
    {"air_temperature_c": 22, "relative_humidity_percent": 100.5},
    {"air_temperature_c": 22, "relative_humidity_percent": 60, "leaf_temperature_offset_c": 11},
    {"air_temperature_c": 22, "relative_humidity_percent": 60, "measured_leaf_temperature_c": 51},
    {"air_temperature_c": "22", "relative_humidity_percent": 60},                        # strings and booleans
    {"air_temperature_c": True, "relative_humidity_percent": 60},
    {"air_temperature_c": 22, "relative_humidity_percent": 60, "colour": "red"},         # unknown field
])
def test_invalid_inputs_are_rejected(body):
    res = post(body)
    assert res.status_code == 422 and res.json()["detail"]


@pytest.mark.parametrize("raw", [
    b'{"air_temperature_c": NaN, "relative_humidity_percent": 60}',
    b'{"air_temperature_c": 22, "relative_humidity_percent": Infinity}',
    b'{"air_temperature_c": 22, "relative_humidity_percent": 60, "leaf_temperature_offset_c": -Infinity}',
    b'{"air_temperature_c": 22, "relative_humidity_percent": 60',                        # malformed JSON
])
def test_non_finite_and_malformed_json_are_rejected(raw):
    res = client.post("/v1/calculate", content=raw, headers={"Content-Type": "application/json"})
    assert res.status_code == 422
