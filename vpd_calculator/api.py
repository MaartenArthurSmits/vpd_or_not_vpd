"""Local HTTP API for the VPD calculation (forward calculation only). Independent of Streamlit.

Run from this folder:  uvicorn api:app --reload      (interactive docs at http://127.0.0.1:8000/docs)
Local use only: the API is not publicly deployed.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

import share
import vpd

# Same input limits as the calculator inputs and shared links.
T_MIN, T_MAX = share._NUMERIC["t"][1:]
RH_MIN, RH_MAX = share._NUMERIC["rh"][1:]
OFFSET_MIN, OFFSET_MAX = share._NUMERIC["off"][1:]
LEAF_MIN, LEAF_MAX = share._NUMERIC["lm"][1:]

EQUATION = {
    "saturation_vapour_pressure": "es(T) = 0.6108 * exp(17.27 * T / (T + 237.3))  [kPa, T in degC]",
    "vpd": "VPD_air = es(T_air) - ea; VPD_leaf = es(T_leaf) - ea; ea = es(T_air) * RH / 100",
    "source": "FAO-56, Allen et al. (1998), Eq. 11",
    "url": "https://www.fao.org/4/x0490e/x0490e07.htm",
}

app = FastAPI(title="VPD Calculator API", version="0.1.0",
              description="Forward VPD calculation. Local use only; not publicly deployed.")


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 with the problem location and message only (the offending value, e.g. NaN, is not echoed back)."""
    detail = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": detail})


class CalculateRequest(BaseModel):
    """Numbers must be JSON numbers (not strings or booleans) and finite."""

    model_config = ConfigDict(extra="forbid", strict=True)

    air_temperature_c: float = Field(allow_inf_nan=False, ge=T_MIN, le=T_MAX, description="Air temperature (degC)")
    relative_humidity_percent: float = Field(allow_inf_nan=False, ge=RH_MIN, le=RH_MAX,
                                             description="Relative humidity (%)")
    leaf_temperature_offset_c: Optional[float] = Field(
        default=None, allow_inf_nan=False, ge=OFFSET_MIN, le=OFFSET_MAX,
        description="Leaf minus air temperature (degC). Use this or measured_leaf_temperature_c, not both.")
    measured_leaf_temperature_c: Optional[float] = Field(
        default=None, allow_inf_nan=False, ge=LEAF_MIN, le=LEAF_MAX,
        description="Measured leaf temperature (degC). Use this or leaf_temperature_offset_c, not both.")

    @model_validator(mode="after")
    def _one_leaf_input(self):
        if self.leaf_temperature_offset_c is not None and self.measured_leaf_temperature_c is not None:
            raise ValueError("Provide either leaf_temperature_offset_c or measured_leaf_temperature_c, not both.")
        return self


class Inputs(BaseModel):
    air_temperature_c: float
    relative_humidity_percent: float
    leaf_temperature_offset_c: float
    measured_leaf_temperature_c: Optional[float]
    leaf_input: Literal["offset", "measured", "default_zero_offset"]


class Results(BaseModel):
    leaf_temperature_c: float
    air_vpd_kpa: float
    leaf_vpd_kpa: float
    saturation_vapour_pressure_air_kpa: float
    saturation_vapour_pressure_leaf_kpa: float
    actual_vapour_pressure_kpa: float


class CalculateResponse(BaseModel):
    inputs: Inputs
    results: Results
    possible_condensation: bool
    warnings: list[str]
    equation: dict[str, str]


@app.post("/v1/calculate", response_model=CalculateResponse)
def calculate(req: CalculateRequest) -> CalculateResponse:
    """Air and leaf VPD for one air temperature, relative humidity and leaf-temperature input (full precision)."""
    if req.measured_leaf_temperature_c is not None:
        leaf_input = "measured"
    elif req.leaf_temperature_offset_c is not None:
        leaf_input = "offset"
    else:
        leaf_input = "default_zero_offset"
    r = vpd.calculate_vpd(req.air_temperature_c, req.relative_humidity_percent,
                          req.leaf_temperature_offset_c or 0.0, req.measured_leaf_temperature_c)
    return CalculateResponse(
        inputs=Inputs(air_temperature_c=r.t_air, relative_humidity_percent=r.rh,
                      leaf_temperature_offset_c=r.t_leaf - r.t_air,
                      measured_leaf_temperature_c=req.measured_leaf_temperature_c, leaf_input=leaf_input),
        results=Results(leaf_temperature_c=r.t_leaf, air_vpd_kpa=r.vpd_air, leaf_vpd_kpa=r.vpd_leaf,
                        saturation_vapour_pressure_air_kpa=r.es_air,
                        saturation_vapour_pressure_leaf_kpa=r.es_leaf, actual_vapour_pressure_kpa=r.ea),
        possible_condensation=r.vpd_leaf < 0, warnings=r.warnings, equation=EQUATION)
